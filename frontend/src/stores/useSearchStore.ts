import { create } from "zustand";
import type { SearchMode, AnalysisDepth, SearchResponse } from "@/types/api";

interface SearchState {
  searchQuery: string;
  searchMode: SearchMode;
  depth: AnalysisDepth;
  searchResults: SearchResponse | null;
  isSearching: boolean;
  error: string | null;

  setSearchQuery: (query: string) => void;
  setSearchMode: (mode: SearchMode) => void;
  setDepth: (depth: AnalysisDepth) => void;
  setSearchResults: (results: SearchResponse | null) => void;
  appendSearchResults: (results: SearchResponse) => void;
  setIsSearching: (loading: boolean) => void;
  setError: (error: string | null) => void;
  resetSearch: () => void;
}

export const useSearchStore = create<SearchState>((set, get) => ({
  searchQuery: "",
  searchMode: "hybrid",
  depth: "balanced",
  searchResults: null,
  isSearching: false,
  error: null,

  setSearchQuery: (query) => set({ searchQuery: query }),
  setSearchMode: (mode) => set({ searchMode: mode }),
  setDepth: (depth) => set({ depth }),
  setSearchResults: (results) => set({ searchResults: results }),

  appendSearchResults: (results) => {
    const current = get().searchResults;
    if (!current) {
      set({ searchResults: results });
      return;
    }
    set({
      searchResults: {
        ...results,
        results: [...current.results, ...results.results],
      },
    });
  },

  setIsSearching: (loading) => set({ isSearching: loading }),
  setError: (error) => set({ error }),

  resetSearch: () =>
    set({
      searchResults: null,
      isSearching: false,
      error: null,
    }),
}));
