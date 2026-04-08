import { useCallback, useRef } from "react";
import { searchVerses } from "@/lib/api";
import { useAppState } from "./useAppState";

export function useSearch() {
  const abortControllerRef = useRef<AbortController | null>(null);
  
  const {
    searchQuery,
    searchMode,
    searchResults,
    setSearchResults,
    appendSearchResults,
    setIsSearching,
    setError,
  } = useAppState();

  const search = useCallback(
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

      setIsSearching(true);
      setError(null);
      setSearchResults(null);

      try {
        const results = await searchVerses(
          searchTerm,
          searchMode,
          50,
          0,
          abortControllerRef.current.signal
        );
        setSearchResults(results);
      } catch (error) {
        if (error instanceof Error) {
          if (error.message === "REQUEST_TIMEOUT") {
            setError("Request timed out. Please try again.");
          } else if (error.message === "SERVICE_UNAVAILABLE") {
            setError("Search service is starting up. Please wait...");
          } else if (error.name !== "AbortError") {
            setError(error.message || "Something went wrong. Please try again.");
          }
        }
      } finally {
        setIsSearching(false);
      }
    },
    [searchQuery, searchMode, setSearchResults, setIsSearching, setError]
  );

  const loadMore = useCallback(async () => {
    if (!searchResults?.pagination.has_more) return;
    if (!searchResults.pagination.next_offset) return;

    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();

    setIsSearching(true);

    try {
      const results = await searchVerses(
        searchResults.query,
        searchMode,
        50,
        searchResults.pagination.next_offset,
        abortControllerRef.current.signal
      );
      appendSearchResults(results);
    } catch (error) {
      if (error instanceof Error && error.name !== "AbortError") {
        setError(error.message || "Failed to load more results.");
      }
    } finally {
      setIsSearching(false);
    }
  }, [searchResults, searchMode, appendSearchResults, setIsSearching, setError]);

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  return { search, loadMore, cancel };
}
