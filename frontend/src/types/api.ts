// VerseFinder AI API Types
// These types match the backend Pydantic models

export type SearchMode = "semantic" | "keyword" | "hybrid";
export type AnalysisDepth = "quick" | "balanced" | "comprehensive";
export type ActiveView = "explore" | "summarize";
export type RelevanceType = "primary" | "supporting" | "contextual";
export type QueryType =
  | "named_entity"
  | "exact_phrase"
  | "single_concept"
  | "multi_concept"
  | "general_topic"
  | "comparative"
  | "verse_reference"
  | "default";

// Search Response Types (matches backend SearchResponse)
export interface VerseResult {
  rank: number;
  verse_id: string;
  book: string;
  text: string;
  score: number;
  faiss_score: number | null;
  faiss_rank: number | null;
  bm25_score: number | null;
  bm25_rank: number | null;
}

export interface Pagination {
  total_results: number;
  limit: number;
  offset: number;
  returned: number;
  has_more: boolean;
  next_offset: number | null;
  suggested_batch_size: number;
  auto_load_until: number;
}

export interface ThresholdsApplied {
  faiss: number;
  bm25: number;
  rrf: number;
}

export interface TimingInfo {
  search_ms: number;
  total_ms: number;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  query_type: QueryType;
  alpha: number | null;
  timing: TimingInfo;
  thresholds_applied: ThresholdsApplied;
  pagination: Pagination;
  results: VerseResult[];
}

// Summarization Response Types (matches backend SummarizationResponse)
export interface Citation {
  verse_id: string;
  text: string;
  relevance: RelevanceType;
}

export interface ThematicConnection {
  theme: string;
  verses: string[];
  explanation: string;
}

export interface SummarizationResponse {
  query: string;
  summary: string;
  key_points: string[];
  citations: Citation[];
  thematic_connections: ThematicConnection[];
  confidence: number;
  verses_analyzed: number;
  llm_provider: string;
  llm_model: string;
  tokens_used: number;
  depth: AnalysisDepth;
  timing: TimingInfo;
}

// Chapter Response Types (matches backend /chapters/{book}/{chapter})
export interface ChapterVerse {
  verse_id: string;
  verse_num: number;
  text: string;
}

export interface ChapterResponse {
  book: string;
  chapter: number;
  total_verses: number;
  verses: ChapterVerse[];
}

// Health Response (matches backend HealthResponse)
export interface HealthResponse {
  status: string;
  version: string;
  indices_loaded: boolean;
  total_verses: number;
}

// App State Types
export interface ChapterModalState {
  open: boolean;
  book: string;
  chapter: number;
  highlightVerse: string;
}

export interface AppState {
  searchQuery: string;
  searchMode: SearchMode;
  activeView: ActiveView;
  depth: AnalysisDepth;
  searchResults: SearchResponse | null;
  summarizeResults: SummarizationResponse | null;
  isSearching: boolean;
  isSummarizing: boolean;
  error: string | null;
  chapterModal: ChapterModalState | null;
  darkMode: boolean;
}

// Favorite and History Types
export interface SearchHistoryItem {
  query: string;
  timestamp: number;
}

// API Request Types
export interface SummarizeRequest {
  query: string;
  verses?: VerseInput[];
  mode?: SearchMode;
  depth?: AnalysisDepth;
  top_k?: number;
  provider?: string;
}

export interface VerseInput {
  verse_id: string;
  book: string;
  text: string;
}
