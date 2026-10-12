// VerseFinder AI API Client

import type {
  SearchResponse,
  SummarizationResponse,
  SummarizeRequest,
  ChapterResponse,
  SearchMode,
} from "@/types/api";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const DEFAULT_TIMEOUT_MS = 10_000;
const SUMMARIZE_TIMEOUT_MS = 30_000;
const MAX_CACHED_CHAPTERS = 50;

const TIMEOUT_MESSAGE = "The request timed out. Please try again.";
const NETWORK_MESSAGE = "Could not reach the server. Check your connection and try again.";
const INVALID_RESPONSE_MESSAGE = "The server sent an unexpected response. Please try again.";
const UNAVAILABLE_MESSAGE = "The service is temporarily unavailable. Please try again later.";

export type ApiErrorKind = "http" | "timeout" | "network" | "invalid_response";

/** Error thrown by the API client. Its `message` is always safe to show to users. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  /** HTTP status code, or null when no response was received. */
  readonly status: number | null;
  /** Seconds to wait before retrying (from the Retry-After header of a 429), if known. */
  readonly retryAfterSeconds: number | null;

  constructor(
    message: string,
    options: { kind: ApiErrorKind; status?: number | null; retryAfterSeconds?: number | null }
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = options.kind;
    this.status = options.status ?? null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
  }
}

/** True when `error` comes from a request that the caller cancelled. Callers should ignore it. */
export function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { name?: unknown }).name === "AbortError"
  );
}

/** A user-facing message for an error thrown by this client. */
export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again."
): string {
  return error instanceof ApiError && error.message ? error.message : fallback;
}

function createAbortError(): Error {
  const error = new Error("The request was cancelled.");
  error.name = "AbortError";
  return error;
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) return Number(trimmed);
  const date = Date.parse(trimmed);
  if (Number.isNaN(date)) return null;
  return Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

function rateLimitMessage(seconds: number | null): string {
  if (seconds === null || seconds <= 0) {
    return "Too many requests. Please wait a moment and try again.";
  }
  if (seconds < 60) {
    return `Too many requests. Please wait ${seconds} second${seconds === 1 ? "" : "s"} and try again.`;
  }
  const minutes = Math.ceil(seconds / 60);
  return `Too many requests. Please wait ${minutes} minute${minutes === 1 ? "" : "s"} and try again.`;
}

function formatValidationIssue(issue: unknown): string | null {
  if (typeof issue !== "object" || issue === null) return null;
  const { loc, msg } = issue as { loc?: unknown; msg?: unknown };
  if (typeof msg !== "string" || !msg.trim()) return null;
  const message = msg.replace(/^Value error,\s*/i, "").trim();
  // loc is e.g. ["query", "query"] or ["body", "verses", 0, "verse_id"]; drop the location part.
  const field = Array.isArray(loc)
    ? loc
        .slice(1)
        .filter((part) => typeof part === "string" || typeof part === "number")
        .join(".")
    : "";
  return field ? `${field}: ${message}` : message;
}

/** Extracts FastAPI's `detail` (a string, or a list of validation issues) from an error body. */
function formatErrorDetail(body: unknown): string | null {
  if (typeof body !== "object" || body === null) return null;
  const { detail } = body as { detail?: unknown };
  if (typeof detail === "string") return detail.trim() || null;
  if (Array.isArray(detail)) {
    const messages = detail
      .map(formatValidationIssue)
      .filter((message): message is string => message !== null);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  return null;
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const text = await response.text();
    return text ? formatErrorDetail(JSON.parse(text)) : null;
  } catch {
    // Not JSON (e.g. an HTML error page from a proxy) or the body could not be read.
    return null;
  }
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const { status } = response;

  if (status === 429) {
    const retryAfterSeconds = parseRetryAfter(response.headers.get("Retry-After"));
    return new ApiError(rateLimitMessage(retryAfterSeconds), {
      kind: "http",
      status,
      retryAfterSeconds,
    });
  }

  const detail = await readErrorDetail(response);
  if (detail) return new ApiError(detail, { kind: "http", status });
  if (status === 503) return new ApiError(UNAVAILABLE_MESSAGE, { kind: "http", status });
  if (status >= 500) {
    return new ApiError(`The server ran into a problem (HTTP ${status}). Please try again.`, {
      kind: "http",
      status,
    });
  }
  return new ApiError(`The request failed (HTTP ${status}).`, { kind: "http", status });
}

interface RequestOptions extends Omit<RequestInit, "signal"> {
  /** Cancels the request; the returned promise then rejects with an error named "AbortError". */
  signal?: AbortSignal;
  timeout?: number;
  timeoutMessage?: string;
}

async function fetchWithTimeout<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const {
    timeout = DEFAULT_TIMEOUT_MS,
    timeoutMessage = TIMEOUT_MESSAGE,
    signal: callerSignal,
    ...init
  } = options;

  if (callerSignal?.aborted) throw createAbortError();

  const timeoutController = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    timeoutController.abort();
  }, timeout);

  // Abort the fetch when either the caller cancels or the timeout fires.
  let signal = timeoutController.signal;
  let removeAbortListener = () => {};
  if (callerSignal) {
    if (typeof AbortSignal.any === "function") {
      signal = AbortSignal.any([callerSignal, timeoutController.signal]);
    } else {
      const forwardAbort = () => timeoutController.abort();
      callerSignal.addEventListener("abort", forwardAbort, { once: true });
      removeAbortListener = () => callerSignal.removeEventListener("abort", forwardAbort);
    }
  }

  try {
    const response = await fetch(url, { ...init, signal });
    if (!response.ok) throw await errorFromResponse(response);

    let data: T;
    try {
      data = (await response.json()) as T;
    } catch (error) {
      if (signal.aborted) throw error;
      throw new ApiError(INVALID_RESPONSE_MESSAGE, {
        kind: "invalid_response",
        status: response.status,
      });
    }
    // The caller may have cancelled while the body was being read.
    if (callerSignal?.aborted) throw createAbortError();
    return data;
  } catch (error) {
    // A cancellation by the caller wins, so callers can reliably ignore it.
    if (callerSignal?.aborted) throw createAbortError();
    if (timedOut) throw new ApiError(timeoutMessage, { kind: "timeout" });
    if (error instanceof ApiError) throw error;
    throw new ApiError(NETWORK_MESSAGE, { kind: "network" });
  } finally {
    clearTimeout(timer);
    removeAbortListener();
  }
}

export function searchVerses(
  query: string,
  mode: SearchMode = "hybrid",
  limit: number = 50,
  offset: number = 0,
  signal?: AbortSignal
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    query,
    mode,
    limit: limit.toString(),
    offset: offset.toString(),
  });

  return fetchWithTimeout<SearchResponse>(`${API_URL}/search?${params}`, { signal });
}

export function summarizeVerses(
  request: SummarizeRequest,
  signal?: AbortSignal
): Promise<SummarizationResponse> {
  return fetchWithTimeout<SummarizationResponse>(`${API_URL}/summarize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
    timeout: SUMMARIZE_TIMEOUT_MS,
    timeoutMessage: "The AI summary took too long to generate. Please try again.",
    signal,
  });
}

// Chapter cache to avoid redundant API calls (oldest entries are evicted first)
const chapterCache = new Map<string, ChapterResponse>();

export async function getChapter(
  book: string,
  chapter: number,
  signal?: AbortSignal
): Promise<ChapterResponse> {
  if (signal?.aborted) throw createAbortError();

  const cacheKey = `${book.trim().replace(/_/g, " ").toLowerCase()}:${chapter}`;
  const cached = chapterCache.get(cacheKey);
  if (cached) return cached;

  const response = await fetchWithTimeout<ChapterResponse>(
    `${API_URL}/chapters/${encodeURIComponent(book)}/${chapter}`,
    { signal }
  );

  if (chapterCache.size >= MAX_CACHED_CHAPTERS) {
    const oldestKey = chapterCache.keys().next().value;
    if (oldestKey !== undefined) chapterCache.delete(oldestKey);
  }
  chapterCache.set(cacheKey, response);

  return response;
}

export interface VerseReference {
  book: string;
  chapter: number;
  verse: number;
}

/**
 * Parses a verse ID such as "John_3:16" or "1_John_4:8" into book, chapter and verse.
 * Returns null when the ID is malformed (e.g. an unexpected citation from the LLM).
 */
export function parseVerseId(verseId: string): VerseReference | null {
  const match = /^(.+?)[_ ](\d+):(\d+)(?:-\d+)?$/.exec(verseId.trim());
  if (!match) return null;
  return {
    book: match[1].replace(/_/g, " "),
    chapter: Number(match[2]),
    verse: Number(match[3]),
  };
}
