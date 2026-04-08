import { create } from "zustand";
import type {
  SearchMode,
  AnalysisDepth,
  ActiveView,
  SearchResponse,
  SummarizationResponse,
  ChapterModalState,
} from "@/types/api";

interface AppState {
  // Search state
  searchQuery: string;
  searchMode: SearchMode;
  activeView: ActiveView;
  depth: AnalysisDepth;
  
  // Results
  searchResults: SearchResponse | null;
  summarizeResults: SummarizationResponse | null;
  
  // Loading states
  isSearching: boolean;
  isSummarizing: boolean;
  
  // Error state
  error: string | null;
  
  // Modal state
  chapterModal: ChapterModalState | null;
  
  // Theme
  darkMode: boolean;
  
  // Actions
  setSearchQuery: (query: string) => void;
  setSearchMode: (mode: SearchMode) => void;
  setActiveView: (view: ActiveView) => void;
  setDepth: (depth: AnalysisDepth) => void;
  setSearchResults: (results: SearchResponse | null) => void;
  appendSearchResults: (results: SearchResponse) => void;
  setSummarizeResults: (results: SummarizationResponse | null) => void;
  setIsSearching: (loading: boolean) => void;
  setIsSummarizing: (loading: boolean) => void;
  setError: (error: string | null) => void;
  openChapterModal: (book: string, chapter: number, highlightVerse: string) => void;
  closeChapterModal: () => void;
  setDarkMode: (dark: boolean) => void;
  toggleDarkMode: () => void;
  reset: () => void;
}

// Get initial dark mode from localStorage or system preference
const getInitialDarkMode = (): boolean => {
  if (typeof window === "undefined") return false;
  
  const stored = localStorage.getItem("theme");
  if (stored) {
    return stored === "dark";
  }
  
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
};

export const useAppState = create<AppState>((set, get) => ({
  // Initial state
  searchQuery: "",
  searchMode: "hybrid",
  activeView: "explore",
  depth: "balanced",
  searchResults: null,
  summarizeResults: null,
  isSearching: false,
  isSummarizing: false,
  error: null,
  chapterModal: null,
  darkMode: getInitialDarkMode(),
  
  // Actions
  setSearchQuery: (query) => set({ searchQuery: query }),
  
  setSearchMode: (mode) => set({ searchMode: mode }),
  
  setActiveView: (view) => set({ activeView: view }),
  
  setDepth: (depth) => set({ depth: depth }),
  
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
  
  setSummarizeResults: (results) => set({ summarizeResults: results }),
  
  setIsSearching: (loading) => set({ isSearching: loading }),
  
  setIsSummarizing: (loading) => set({ isSummarizing: loading }),
  
  setError: (error) => set({ error: error }),
  
  openChapterModal: (book, chapter, highlightVerse) =>
    set({
      chapterModal: {
        open: true,
        book,
        chapter,
        highlightVerse,
      },
    }),
  
  closeChapterModal: () => set({ chapterModal: null }),
  
  setDarkMode: (dark) => {
    localStorage.setItem("theme", dark ? "dark" : "light");
    if (dark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    set({ darkMode: dark });
  },
  
  toggleDarkMode: () => {
    const current = get().darkMode;
    get().setDarkMode(!current);
  },
  
  reset: () =>
    set({
      searchQuery: "",
      searchResults: null,
      summarizeResults: null,
      isSearching: false,
      isSummarizing: false,
      error: null,
    }),
}));

// Initialize dark mode on load
if (typeof window !== "undefined") {
  const dark = getInitialDarkMode();
  if (dark) {
    document.documentElement.classList.add("dark");
  }
}
