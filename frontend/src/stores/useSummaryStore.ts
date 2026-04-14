import { create } from "zustand";
import type { SummarizationResponse } from "@/types/api";

interface SummaryState {
  summarizeResults: SummarizationResponse | null;
  isSummarizing: boolean;

  setSummarizeResults: (results: SummarizationResponse | null) => void;
  setIsSummarizing: (loading: boolean) => void;
  resetSummary: () => void;
}

export const useSummaryStore = create<SummaryState>((set) => ({
  summarizeResults: null,
  isSummarizing: false,

  setSummarizeResults: (results) => set({ summarizeResults: results }),
  setIsSummarizing: (loading) => set({ isSummarizing: loading }),
  resetSummary: () => set({ summarizeResults: null, isSummarizing: false }),
}));
