import { useCallback, useRef } from "react";
import { summarizeVerses } from "@/lib/api";
import { useAppState } from "./useAppState";

export function useSummarize() {
  const abortControllerRef = useRef<AbortController | null>(null);
  
  const {
    searchQuery,
    searchMode,
    depth,
    setSummarizeResults,
    setIsSummarizing,
    setError,
  } = useAppState();

  const summarize = useCallback(
    async (query?: string) => {
      const searchTerm = query ?? searchQuery;
      
      if (!searchTerm.trim()) {
        setError("Please enter a search query");
        return;
      }

      // Cancel any pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      setIsSummarizing(true);
      setError(null);
      setSummarizeResults(null);

      try {
        const results = await summarizeVerses(
          {
            query: searchTerm,
            depth,
            mode: searchMode,
          },
          abortControllerRef.current.signal
        );
        setSummarizeResults(results);
      } catch (error) {
        if (error instanceof Error) {
          if (error.message === "REQUEST_TIMEOUT") {
            setError("Request timed out. AI summarization may take longer for complex queries.");
          } else if (error.message === "SERVICE_UNAVAILABLE") {
            setError("Summarization service is starting up. Please wait...");
          } else if (error.name !== "AbortError") {
            setError(error.message || "Something went wrong. Please try again.");
          }
        }
      } finally {
        setIsSummarizing(false);
      }
    },
    [searchQuery, searchMode, depth, setSummarizeResults, setIsSummarizing, setError]
  );

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  return { summarize, cancel };
}
