import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SearchHistoryItem } from "@/types/api";

const MAX_HISTORY = 20;

interface HistoryState {
  history: SearchHistoryItem[];

  addToHistory: (query: string) => void;
  removeFromHistory: (query: string) => void;
  clearHistory: () => void;
}

export const useHistoryStore = create<HistoryState>()(
  persist(
    (set) => ({
      history: [],

      addToHistory: (query) => {
        if (!query.trim()) return;
        set((state) => {
          const filtered = state.history.filter(
            (item) => item.query.toLowerCase() !== query.toLowerCase()
          );
          return {
            history: [
              { query: query.trim(), timestamp: Date.now() },
              ...filtered,
            ].slice(0, MAX_HISTORY),
          };
        });
      },

      removeFromHistory: (query) =>
        set((state) => ({
          history: state.history.filter(
            (item) => item.query.toLowerCase() !== query.toLowerCase()
          ),
        })),

      clearHistory: () => set({ history: [] }),
    }),
    { name: "versefinder-history" }
  )
);
