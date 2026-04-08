// VerseFinder AI API Client

import type {
  SearchResponse,
  SummarizationResponse,
  ChapterResponse,
  HealthResponse,
  SearchMode,
  AnalysisDepth,
  VerseInput,
} from "@/types/api";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Chapter cache to avoid redundant API calls
const chapterCache = new Map<string, ChapterResponse>();

interface FetchOptions {
  signal?: AbortSignal;
  timeout?: number;
}

async function fetchWithTimeout<T>(
  url: string,
  options: RequestInit & FetchOptions = {}
): Promise<T> {
  const { timeout = 10000, signal, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // Combine signals if one is provided
  const combinedSignal = signal
    ? new AbortController().signal
    : controller.signal;

  if (signal) {
    signal.addEventListener("abort", () => controller.abort());
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: combinedSignal,
    });

    if (!response.ok) {
      if (response.status === 503) {
        throw new Error("SERVICE_UNAVAILABLE");
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("REQUEST_TIMEOUT");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function searchVerses(
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

  return fetchWithTimeout<SearchResponse>(`${API_URL}/search?${params}`, {
    timeout: 10000,
    signal,
  });
}

export interface SummarizeOptions {
  query: string;
  depth: AnalysisDepth;
  mode?: SearchMode;
  verses?: VerseInput[];
  provider?: string;
  top_k?: number;
}

export async function summarizeVerses(
  options: SummarizeOptions,
  signal?: AbortSignal
): Promise<SummarizationResponse> {
  return fetchWithTimeout<SummarizationResponse>(`${API_URL}/summarize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(options),
    timeout: 30000,
    signal,
  });
}

export async function getChapter(
  book: string,
  chapter: number,
  signal?: AbortSignal
): Promise<ChapterResponse> {
  const cacheKey = `${book}:${chapter}`;

  // Check cache first
  if (chapterCache.has(cacheKey)) {
    return chapterCache.get(cacheKey)!;
  }

  const response = await fetchWithTimeout<ChapterResponse>(
    `${API_URL}/chapters/${encodeURIComponent(book)}/${chapter}`,
    {
      timeout: 10000,
      signal,
    }
  );

  // Cache the response
  chapterCache.set(cacheKey, response);

  return response;
}

export async function checkHealth(): Promise<HealthResponse> {
  return fetchWithTimeout<HealthResponse>(`${API_URL}/health`, {
    timeout: 5000,
  });
}

// Utility to parse verse_id into book and chapter
export function parseVerseId(verseId: string): { book: string; chapter: number; verse: number } {
  // Format: "John_3:16" or "1_John_3:16"
  const colonIndex = verseId.lastIndexOf(":");
  const verse = parseInt(verseId.slice(colonIndex + 1), 10);
  
  const beforeColon = verseId.slice(0, colonIndex);
  const underscoreIndex = beforeColon.lastIndexOf("_");
  
  const chapter = parseInt(beforeColon.slice(underscoreIndex + 1), 10);
  const book = beforeColon.slice(0, underscoreIndex).replace(/_/g, " ");
  
  return { book, chapter, verse };
}

// Clear chapter cache if needed
export function clearChapterCache(): void {
  chapterCache.clear();
}
