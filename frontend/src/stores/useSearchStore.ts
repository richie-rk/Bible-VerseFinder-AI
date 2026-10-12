import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SearchMode, AnalysisDepth, SearchResponse } from "@/types/api";
import { isAnalysisDepth, isSearchMode } from "@/lib/search";

interface SearchPreferences {
  searchMode: SearchMode;
  depth: AnalysisDepth;
}

interface SearchState extends SearchPreferences {
  searchResults: SearchResponse | null;
  isSearching: boolean;
  error: string | null;

  setSearchMode: (mode: SearchMode) => void;
  setDepth: (depth: AnalysisDepth) => void;
  setSearchResults: (results: SearchResponse | null) => void;
  appendSearchResults: (results: SearchResponse) => void;
  setIsSearching: (loading: boolean) => void;
  setError: (error: string | null) => void;
  resetSearch: () => void;
}

export const useSearchStore = create<SearchState>()(
  persist(
    (set, get) => ({
      searchMode: "hybrid",
      depth: "balanced",
      searchResults: null,
      isSearching: false,
      error: null,

      setSearchMode: (mode) => set({ searchMode: mode }),
      setDepth: (depth) => set({ depth }),
      setSearchResults: (results) => set({ searchResults: results }),

      appendSearchResults: (page) => {
        const current = get().searchResults;
        if (!current) {
          set({ searchResults: page });
          return;
        }
        // Rankings can shift between page requests; never show the same verse twice.
        const seen = new Set(current.results.map((verse) => verse.verse_id));
        set({
          searchResults: {
            ...page,
            notice: page.notice || current.notice || null,
            results: [
              ...current.results,
              ...page.results.filter((verse) => !seen.has(verse.verse_id)),
            ],
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
    }),
    {
      name: "versefinder-search-preferences",
      // Only the user's defaults (Settings page) are persisted, not results or loading state.
      partialize: (state): SearchPreferences => ({
        searchMode: state.searchMode,
        depth: state.depth,
      }),
      merge: (persisted, current) => {
        const saved = (persisted ?? {}) as Partial<Record<keyof SearchPreferences, unknown>>;
        return {
          ...current,
          searchMode: isSearchMode(saved.searchMode) ? saved.searchMode : current.searchMode,
          depth: isAnalysisDepth(saved.depth) ? saved.depth : current.depth,
        };
      },
    }
  )
);
