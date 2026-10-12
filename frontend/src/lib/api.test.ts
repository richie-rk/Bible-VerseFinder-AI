// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  getChapter,
  getErrorMessage,
  isAbortError,
  parseVerseId,
  searchVerses,
  summarizeVerses,
} from "./api";
import {
  jsonResponse,
  makeChapterResponse,
  makeSearchResponse,
  makeSummaryResponse,
} from "@/test/fixtures";

type FetchImpl = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function stubFetch(impl: FetchImpl) {
  const fetchMock = vi.fn(impl);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** Like a real fetch that never gets a response: it only settles when its signal aborts. */
function stubHangingFetch() {
  return stubFetch(
    (_input, init) =>
      new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal;
        const rejectWithReason = () =>
          reject(signal?.reason ?? new DOMException("This operation was aborted", "AbortError"));
        if (signal?.aborted) return rejectWithReason();
        signal?.addEventListener("abort", rejectWithReason, { once: true });
      })
  );
}

async function captureError(promise: Promise<unknown>): Promise<unknown> {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  throw new Error("Expected the promise to reject");
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const originalAbortSignalAny = AbortSignal.any;

describe.each([
  { name: "with AbortSignal.any", withAny: true },
  { name: "without AbortSignal.any (fallback)", withAny: false },
])("cancellation and timeouts ($name)", ({ withAny }) => {
  beforeEach(() => {
    if (!withAny) {
      Object.defineProperty(AbortSignal, "any", { value: undefined, configurable: true, writable: true });
    }
  });

  afterEach(() => {
    Object.defineProperty(AbortSignal, "any", {
      value: originalAbortSignalAny,
      configurable: true,
      writable: true,
    });
  });

  it("aborts the fetch and rejects with an AbortError when the caller aborts", async () => {
    const fetchMock = stubHangingFetch();
    const controller = new AbortController();

    const promise = searchVerses("grace", "hybrid", 50, 0, controller.signal);
    controller.abort();
    const error = await captureError(promise);

    expect(isAbortError(error)).toBe(true);
    expect(error).not.toBeInstanceOf(ApiError);
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });

  it("rejects without fetching when the signal is already aborted", async () => {
    const fetchMock = stubHangingFetch();
    const controller = new AbortController();
    controller.abort();

    const error = await captureError(searchVerses("grace", "hybrid", 50, 0, controller.signal));

    expect(isAbortError(error)).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("times out even when the caller passes a signal", async () => {
    vi.useFakeTimers();
    const fetchMock = stubHangingFetch();
    const controller = new AbortController();

    const promise = captureError(searchVerses("grace", "hybrid", 50, 0, controller.signal));
    await vi.advanceTimersByTimeAsync(10_000);
    const error = await promise;

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      kind: "timeout",
      message: "The request timed out. Please try again.",
    });
    expect(isAbortError(error)).toBe(false);
    expect(controller.signal.aborted).toBe(false);
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });

  it("uses a longer, summary-specific timeout for /summarize", async () => {
    vi.useFakeTimers();
    stubHangingFetch();

    const promise = captureError(summarizeVerses({ query: "grace" }, new AbortController().signal));
    await vi.advanceTimersByTimeAsync(10_000);
    expect(vi.getTimerCount()).toBe(1); // still waiting
    await vi.advanceTimersByTimeAsync(20_000);

    expect(await promise).toMatchObject({
      kind: "timeout",
      message: "The AI summary took too long to generate. Please try again.",
    });
  });

  it("rejects with an AbortError when the caller aborts while the body is being read", async () => {
    const controller = new AbortController();
    stubFetch(async () => {
      const response = jsonResponse(makeSearchResponse(["John_3:16"]));
      // Simulates a fetch implementation that resolves although the caller has cancelled.
      controller.abort();
      return response;
    });

    const error = await captureError(searchVerses("grace", "hybrid", 50, 0, controller.signal));

    expect(isAbortError(error)).toBe(true);
  });

  it("clears the timer and its abort listener once the request settles", async () => {
    vi.useFakeTimers();
    stubFetch(async () => jsonResponse(makeSearchResponse(["John_3:16"])));
    const controller = new AbortController();
    const addListener = vi.spyOn(controller.signal, "addEventListener");
    const removeListener = vi.spyOn(controller.signal, "removeEventListener");

    await searchVerses("grace", "hybrid", 50, 0, controller.signal);

    expect(vi.getTimerCount()).toBe(0);
    if (!withAny) {
      expect(addListener).toHaveBeenCalledWith("abort", expect.any(Function), { once: true });
      expect(removeListener).toHaveBeenCalledWith("abort", addListener.mock.calls[0]?.[1]);
    }
  });
});

describe("error responses", () => {
  it("uses the backend's string detail as the message", async () => {
    stubFetch(async () => jsonResponse({ detail: "Unknown verse ID: Hezekiah_1:1" }, 422));

    const error = await captureError(summarizeVerses({ query: "grace" }));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      kind: "http",
      status: 422,
      message: "Unknown verse ID: Hezekiah_1:1",
    });
  });

  it("formats FastAPI validation errors", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          detail: [
            {
              loc: ["query", "query"],
              msg: "String should have at most 500 characters",
              type: "string_too_long",
            },
            {
              loc: ["body", "verses", 0, "verse_id"],
              msg: "Value error, verse_id must not be blank",
              type: "value_error",
            },
          ],
        },
        422
      )
    );

    const error = await captureError(searchVerses("x".repeat(600)));

    expect(error).toMatchObject({
      status: 422,
      message:
        "query: String should have at most 500 characters; verses.0.verse_id: verse_id must not be blank",
    });
  });

  it("explains rate limiting using Retry-After", async () => {
    stubFetch(async () => jsonResponse({ detail: "Rate limit exceeded" }, 429, { "Retry-After": "30" }));

    const error = await captureError(searchVerses("grace"));

    expect(error).toMatchObject({
      status: 429,
      retryAfterSeconds: 30,
      message: "Too many requests. Please wait 30 seconds and try again.",
    });
  });

  it("rounds long Retry-After values up to minutes", async () => {
    stubFetch(async () => jsonResponse({ detail: "Rate limit exceeded" }, 429, { "Retry-After": "61" }));

    const error = await captureError(searchVerses("grace"));

    expect(error).toMatchObject({ message: "Too many requests. Please wait 2 minutes and try again." });
  });

  it("handles a 429 without Retry-After", async () => {
    stubFetch(async () => jsonResponse({ detail: "Rate limit exceeded" }, 429));

    const error = await captureError(searchVerses("grace"));

    expect(error).toMatchObject({
      retryAfterSeconds: null,
      message: "Too many requests. Please wait a moment and try again.",
    });
  });

  it("shows the backend's detail for 503 responses", async () => {
    const detail = "AI summarization is temporarily unavailable. Please try again later.";
    stubFetch(async () => jsonResponse({ detail }, 503));

    const error = await captureError(summarizeVerses({ query: "grace" }));

    expect(error).toMatchObject({ status: 503, message: detail });
  });

  it("falls back to a generic message when the error body isn't JSON", async () => {
    stubFetch(async () => new Response("<html>Bad Gateway</html>", { status: 502 }));

    const error = await captureError(searchVerses("grace"));

    expect(error).toMatchObject({
      status: 502,
      message: "The server ran into a problem (HTTP 502). Please try again.",
    });
  });

  it("reports network failures", async () => {
    stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });

    const error = await captureError(searchVerses("grace"));

    expect(error).toMatchObject({
      kind: "network",
      status: null,
      message: "Could not reach the server. Check your connection and try again.",
    });
  });

  it("reports a success response that isn't valid JSON", async () => {
    stubFetch(async () => new Response("not json", { status: 200 }));

    const error = await captureError(searchVerses("grace"));

    expect(error).toMatchObject({ kind: "invalid_response", status: 200 });
  });
});

describe("requests", () => {
  it("builds the search URL from its arguments", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(makeSearchResponse(["John_3:16"])));

    const result = await searchVerses("born again", "keyword", 20, 40);

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    const parsed = new URL(String(url));
    expect(parsed.pathname).toBe("/search");
    expect(Object.fromEntries(parsed.searchParams)).toEqual({
      query: "born again",
      mode: "keyword",
      limit: "20",
      offset: "40",
    });
    expect(init?.credentials).toBeUndefined();
    expect(result.results[0]?.verse_id).toBe("John_3:16");
  });

  it("posts summarize requests as JSON", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(makeSummaryResponse()));

    await summarizeVerses({
      query: "grace",
      depth: "quick",
      mode: "hybrid",
      verses: [{ verse_id: "Ephesians_2:8" }],
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toMatch(/\/summarize$/);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      query: "grace",
      depth: "quick",
      mode: "hybrid",
      verses: [{ verse_id: "Ephesians_2:8" }],
    });
  });

  it("leaves verses out of the summarize body when there are none", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(makeSummaryResponse()));

    await summarizeVerses({ query: "grace", depth: "balanced", verses: undefined });

    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body).not.toHaveProperty("verses");
  });

  it("caches chapters regardless of book-name spelling", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(makeChapterResponse("1 John", 4)));

    const first = await getChapter("1 John", 4);
    const second = await getChapter("1_john", 4);

    expect(second).toEqual(first);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/chapters\/1%20John\/4$/);
  });
});

describe("parseVerseId", () => {
  it.each([
    ["John_3:16", { book: "John", chapter: 3, verse: 16 }],
    ["1_John_4:8", { book: "1 John", chapter: 4, verse: 8 }],
    ["1 John_4:8", { book: "1 John", chapter: 4, verse: 8 }],
    ["Romans_8:28-30", { book: "Romans", chapter: 8, verse: 28 }],
  ])("parses %s", (verseId, expected) => {
    expect(parseVerseId(verseId)).toEqual(expected);
  });

  it.each(["", "John", "John_3", "John_3:x", "3:16"])("returns null for %j", (verseId) => {
    expect(parseVerseId(verseId)).toBeNull();
  });
});

describe("getErrorMessage", () => {
  it("returns API error messages and hides unexpected errors", () => {
    expect(getErrorMessage(new ApiError("Verse not found", { kind: "http", status: 404 }))).toBe(
      "Verse not found"
    );
    expect(getErrorMessage(new TypeError("x is undefined"), "Fallback")).toBe("Fallback");
  });
});
