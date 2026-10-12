import { create } from "zustand";
import type { SummarizationResponse } from "@/types/api";

interface SummaryState {
  summarizeResults: SummarizationResponse | null;
  isSummarizing: boolean;
  error: string | null;

  setSummarizeResults: (results: SummarizationResponse | null) => void;
  setIsSummarizing: (loading: boolean) => void;
  setError: (error: string | null) => void;
  resetSummary: () => void;
}

export const useSummaryStore = create<SummaryState>((set) => ({
  summarizeResults: null,
  isSummarizing: false,
  error: null,

  setSummarizeResults: (results) => set({ summarizeResults: results }),
  setIsSummarizing: (loading) => set({ isSummarizing: loading }),
  setError: (error) => set({ error }),
  resetSummary: () => set({ summarizeResults: null, isSummarizing: false, error: null }),
}));
