import type {
  ChapterResponse,
  SearchResponse,
  SummarizationResponse,
  VerseResult,
} from "@/types/api";

export function makeVerse(verseId: string, rank = 1): VerseResult {
  const book = verseId.slice(0, verseId.lastIndexOf("_")).replace(/_/g, " ");
  return {
    rank,
    verse_id: verseId,
    book,
    text: `Text of ${verseId}`,
    score: 0.9,
    faiss_score: null,
    faiss_rank: null,
    bm25_score: null,
    bm25_rank: null,
  };
}

export function makeSearchResponse(
  verseIds: string[],
  overrides: Partial<SearchResponse> = {}
): SearchResponse {
  return {
    query: "grace",
    mode: "hybrid",
    query_type: "single_concept",
    alpha: 0.65,
    timing: { search_ms: 1, total_ms: 2 },
    thresholds_applied: { faiss: 0.2, bm25: 0.1, rrf: 0.15 },
    pagination: {
      total_results: verseIds.length,
      limit: 50,
      offset: 0,
      returned: verseIds.length,
      has_more: false,
      next_offset: null,
      suggested_batch_size: 50,
      auto_load_until: 150,
    },
    results: verseIds.map((id, index) => makeVerse(id, index + 1)),
    notice: null,
    ...overrides,
  };
}

export function makeSummaryResponse(
  overrides: Partial<SummarizationResponse> = {}
): SummarizationResponse {
  return {
    query: "grace",
    summary: "Grace is God's unearned favor [Ephesians_2:8].",
    key_points: ["Salvation is by grace through faith [Ephesians_2:8]"],
    citations: [
      { verse_id: "Ephesians_2:8", text: "For by grace you have been saved through faith", relevance: "primary" },
    ],
    thematic_connections: [],
    confidence: 0.9,
    verses_analyzed: 1,
    llm_provider: "openai",
    llm_model: "gpt-4o-mini",
    tokens_used: 120,
    depth: "balanced",
    timing: { search_ms: 0, total_ms: 450 },
    ...overrides,
  };
}

export function makeChapterResponse(
  book: string,
  chapter: number,
  overrides: Partial<ChapterResponse> = {}
): ChapterResponse {
  const id = book.replace(/ /g, "_");
  return {
    book,
    chapter,
    total_chapters: 21,
    total_verses: 2,
    verses: [
      { verse_id: `${id}_${chapter}:1`, verse_num: 1, text: `${book} ${chapter}:1 text` },
      { verse_id: `${id}_${chapter}:2`, verse_num: 2, text: `${book} ${chapter}:2 text` },
    ],
    ...overrides,
  };
}

export function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {}
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

/** A promise plus its resolve function, for responses that arrive when the test says so. */
export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}
