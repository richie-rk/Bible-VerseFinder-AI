import { useEffect, useCallback, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Info, SlidersHorizontal, Sparkles } from "lucide-react";
import { useSearchStore } from "@/stores/useSearchStore";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { getErrorMessage, isAbortError, parseVerseId, searchVerses } from "@/lib/api";
import SearchBar from "@/components/search/SearchBar";
import SearchSidebar, { SearchFilters } from "@/components/search/SearchSidebar";
import { VerseCard } from "@/components/VerseCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import type { SearchMode, VerseResult } from "@/types/api";

const PAGE_SIZE = 50;

export default function SearchResultsPage() {
  // React Router already decodes route params.
  const { query } = useParams<{ query: string }>();
  const term = query?.trim() ?? "";

  return term ? <SearchResults query={term} /> : <SearchPrompt />;
}

/** Shown for "/search" without a query, e.g. from the header's search button. */
function SearchPrompt() {
  const navigate = useNavigate();

  return (
    <div className="max-w-2xl mx-auto px-4 py-16">
      <h1 className="font-serif text-3xl font-medium text-foreground mb-2">Search the Scriptures</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Search for a topic, verse, or question
      </p>
      <SearchBar autoFocus onSearch={(q) => navigate(`/search/${encodeURIComponent(q)}`)} />
    </div>
  );
}

function SearchResults({ query }: { query: string }) {
  const navigate = useNavigate();
  const abortRef = useRef<AbortController | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const {
    searchMode, searchResults,
    isSearching, error,
    setSearchResults, appendSearchResults,
    setIsSearching, setError, resetSearch,
  } = useSearchStore();

  const { addToHistory } = useHistoryStore();

  const runSearch = useCallback(async (term: string, mode: SearchMode, offset: number) => {
    // Cancel the previous request so a late response can't overwrite newer results.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    if (offset === 0) resetSearch();
    setIsSearching(true);
    setError(null);

    try {
      const results = await searchVerses(term, mode, PAGE_SIZE, offset, controller.signal);
      if (controller.signal.aborted) return;
      if (offset === 0) {
        setSearchResults(results);
        addToHistory(term);
      } else {
        appendSearchResults(results);
      }
    } catch (err) {
      if (controller.signal.aborted || isAbortError(err)) return;
      setError(getErrorMessage(err));
    } finally {
      // Only the latest request may clear the loading flag.
      if (abortRef.current === controller) {
        abortRef.current = null;
        setIsSearching(false);
      }
    }
  }, [resetSearch, setIsSearching, setError, setSearchResults, appendSearchResults, addToHistory]);

  // New search whenever the query or the search mode changes
  useEffect(() => {
    runSearch(query, searchMode, 0);
    return () => abortRef.current?.abort();
  }, [query, searchMode, runSearch]);

  // Reads the store directly so a stale render can't trigger a load for old results.
  // After a failed page the user retries explicitly (force) instead of the observer looping.
  const loadMore = useCallback((force = false) => {
    const { searchResults: current, isSearching: busy, error: failed } = useSearchStore.getState();
    if (!current || busy || (failed && !force)) return;
    const { has_more, next_offset } = current.pagination;
    if (!has_more || next_offset === null) return;
    runSearch(current.query, current.mode, next_offset);
  }, [runSearch]);

  // Infinite scroll
  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (!sentinel || !searchResults?.pagination.has_more || isSearching) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadMore();
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [searchResults, isSearching, loadMore]);

  const handleRetry = () => {
    if (searchResults) loadMore(true);
    else runSearch(query, searchMode, 0);
  };

  const handleVerseClick = (verse: VerseResult) => {
    const ref = parseVerseId(verse.verse_id);
    if (!ref) return;
    navigate(`/read/${encodeURIComponent(verse.book)}/${ref.chapter}?highlight=${ref.verse}`);
  };

  const handleSummarize = () => navigate(`/summary/${encodeURIComponent(query)}`);

  const totalResults = searchResults?.pagination.total_results ?? 0;

  return (
    <div className="flex min-h-[calc(100vh-64px)]">
      {/* Sidebar (md and up) */}
      <SearchSidebar onSummarize={handleSummarize} />

      {/* Main Content */}
      <div className="flex-1 px-4 md:px-8 py-6 max-w-4xl">
        {/* Mobile: filters toggle and summarize action */}
        <div className="md:hidden flex items-center justify-between gap-3 mb-4">
          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            aria-controls="mobile-search-filters"
            className="flex items-center gap-2 text-sm text-muted-foreground"
          >
            <SlidersHorizontal className="w-4 h-4" />
            Filters
          </button>
          <button
            type="button"
            onClick={handleSummarize}
            className="btn-scriptorium flex items-center gap-2 px-4 py-2"
          >
            <Sparkles className="w-4 h-4" />
            Summarize with AI
          </button>
        </div>

        <div
          id="mobile-search-filters"
          hidden={!filtersOpen}
          className="md:hidden bg-surface-low dark:bg-card rounded-lg p-4 mb-6"
        >
          <SearchFilters />
        </div>

        {/* Results header */}
        {searchResults && (
          <div className="flex items-center justify-between mb-6">
            <p className="font-sans text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">{totalResults}</span>{" "}
              verses found for &lsquo;{searchResults.query}&rsquo;
            </p>
          </div>
        )}

        {/* Notice from the backend (e.g. a fallback was used) */}
        {searchResults?.notice && (
          <div
            role="status"
            className="flex items-start gap-2 bg-gold/10 border-l-4 border-l-gold rounded-lg p-4 mb-6 text-sm text-foreground"
          >
            <Info className="w-4 h-4 mt-0.5 shrink-0 text-gold-dark dark:text-gold" aria-hidden="true" />
            <p>{searchResults.notice}</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            role="alert"
            className="flex items-start justify-between gap-3 bg-destructive/10 text-destructive rounded-lg p-4 mb-6 text-sm"
          >
            <p>{error}</p>
            <button
              type="button"
              onClick={handleRetry}
              disabled={isSearching}
              className="shrink-0 font-medium underline underline-offset-2 disabled:opacity-50"
            >
              Try again
            </button>
          </div>
        )}

        {/* Loading skeletons */}
        {isSearching && !searchResults && (
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        )}

        {/* Results */}
        {searchResults && (
          <div className="space-y-4">
            {searchResults.results.map((verse) => (
              <VerseCard
                key={verse.verse_id}
                verse={verse}
                onClick={() => handleVerseClick(verse)}
              />
            ))}
          </div>
        )}

        {/* Infinite scroll trigger */}
        <div ref={loadMoreRef} className="h-10 flex items-center justify-center mt-4">
          {isSearching && searchResults && (
            <p className="text-sm text-muted-foreground animate-pulse">
              Loading more verses...
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
