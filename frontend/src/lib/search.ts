import type {
  AnalysisDepth,
  SearchMode,
  SearchResponse,
  SummarizeVerseInput,
} from "@/types/api";

export const SEARCH_MODES: readonly { value: SearchMode; label: string; description: string }[] = [
  { value: "semantic", label: "Semantic", description: "AI meaning" },
  { value: "keyword", label: "Keyword", description: "Exact match" },
  { value: "hybrid", label: "Hybrid", description: "Combined" },
];

export const SUMMARY_DEPTHS: readonly { value: AnalysisDepth; label: string }[] = [
  { value: "quick", label: "Quick" },
  { value: "balanced", label: "Balanced" },
  { value: "comprehensive", label: "Comprehensive" },
];

/** Number of verses an AI summary analyzes at each depth (matches the backend). */
export const DEPTH_VERSE_COUNT: Record<AnalysisDepth, number> = {
  quick: 7,
  balanced: 12,
  comprehensive: 20,
};

export function isSearchMode(value: unknown): value is SearchMode {
  return SEARCH_MODES.some((mode) => mode.value === value);
}

export function isAnalysisDepth(value: unknown): value is AnalysisDepth {
  return SUMMARY_DEPTHS.some((depth) => depth.value === value);
}

/**
 * The verses to send to /summarize so the summary covers the results the user just saw:
 * the top N results (N by depth) when `searchResults` belong to the same query, else undefined
 * (the backend then runs its own search).
 */
export function selectSummaryVerses(
  searchResults: SearchResponse | null,
  query: string,
  depth: AnalysisDepth
): SummarizeVerseInput[] | undefined {
  if (!searchResults || searchResults.query.trim() !== query.trim()) return undefined;
  const verses = searchResults.results
    .slice(0, DEPTH_VERSE_COUNT[depth])
    .map((verse) => ({ verse_id: verse.verse_id }));
  return verses.length > 0 ? verses : undefined;
}
