import { useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { SlidersHorizontal } from "lucide-react";
import { useSearchStore } from "@/stores/useSearchStore";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { useUIStore } from "@/stores/useUIStore";
import { searchVerses } from "@/lib/api";
// SearchBar imported for future header integration
// import SearchBar from "@/components/search/SearchBar";
import SearchSidebar from "@/components/search/SearchSidebar";
import { VerseCard } from "@/components/VerseCard";
import { SkeletonCard } from "@/components/SkeletonCard";

export default function SearchResultsPage() {
  const { query } = useParams<{ query: string }>();
  const navigate = useNavigate();
  const abortRef = useRef<AbortController | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const {
    searchQuery, searchMode, searchResults,
    isSearching, error,
    setSearchQuery, setSearchResults, appendSearchResults,
    setIsSearching, setError, resetSearch,
  } = useSearchStore();

  const { addToHistory } = useHistoryStore();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  // Run search when query param changes
  const runSearch = useCallback(async (term: string, offset = 0) => {
    if (!term.trim()) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    if (offset === 0) resetSearch();
    setIsSearching(true);
    setError(null);

    try {
      const results = await searchVerses(
        term, searchMode, 50, offset, abortRef.current.signal
      );
      if (offset === 0) {
        setSearchResults(results);
        addToHistory(term);
      } else {
        appendSearchResults(results);
      }
    } catch (err) {
      if (err instanceof Error && err.name !== "AbortError") {
        if (err.message === "REQUEST_TIMEOUT") setError("Request timed out. Please try again.");
        else if (err.message === "SERVICE_UNAVAILABLE") setError("Search service starting up...");
        else setError(err.message || "Something went wrong.");
      }
    } finally {
      setIsSearching(false);
    }
  }, [searchMode, resetSearch, setIsSearching, setError, setSearchResults, appendSearchResults, addToHistory]);

  useEffect(() => {
    const decoded = query ? decodeURIComponent(query) : "";
    if (decoded) {
      setSearchQuery(decoded);
      runSearch(decoded);
    }
    return () => { abortRef.current?.abort(); };
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  // Infinite scroll
  useEffect(() => {
    if (!loadMoreRef.current) return;
    observerRef.current?.disconnect();
    observerRef.current = new IntersectionObserver(([entry]) => {
      if (
        entry.isIntersecting &&
        searchResults?.pagination.has_more &&
        searchResults.pagination.next_offset &&
        !isSearching
      ) {
        runSearch(searchResults.query, searchResults.pagination.next_offset);
      }
    });
    observerRef.current.observe(loadMoreRef.current);
    return () => { observerRef.current?.disconnect(); };
  }, [searchResults, isSearching, runSearch]);

  const handleNewSearch = (newQuery: string) => {
    navigate(`/search/${encodeURIComponent(newQuery)}`);
  };

  const handleVerseClick = (book: string, chapter: number, verseId: string) => {
    const verse = verseId.split(":").pop() || "";
    navigate(`/read/${encodeURIComponent(book)}/${chapter}?highlight=${verse}`);
  };

  const totalResults = searchResults?.pagination.total_results ?? 0;

  return (
    <div className="flex min-h-[calc(100vh-64px)]">
      {/* Sidebar */}
      <SearchSidebar
        open={sidebarOpen}
        onSummarize={() => navigate(`/summary/${encodeURIComponent(searchQuery)}`)}
      />

      {/* Main Content */}
      <main className="flex-1 px-4 md:px-8 py-6 max-w-4xl">
        {/* Mobile filter toggle */}
        <button
          onClick={toggleSidebar}
          className="md:hidden flex items-center gap-2 text-sm text-muted-foreground mb-4"
        >
          <SlidersHorizontal className="w-4 h-4" />
          Filters
        </button>

        {/* Results header */}
        {searchResults && !isSearching && (
          <div className="flex items-center justify-between mb-6">
            <p className="font-sans text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">{totalResults}</span>{" "}
              verses found for &lsquo;{searchResults.query}&rsquo;
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-destructive/10 text-destructive rounded-lg p-4 mb-6 text-sm">
            {error}
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
            {searchResults.results.map((verse, idx) => (
              <VerseCard
                key={verse.verse_id}
                verse={verse}
                onClick={() => {
                  const parts = verse.verse_id.split("_");
                  const chapterVerse = parts.pop()!;
                  const chapter = parseInt(chapterVerse.split(":")[0]);
                  const book = parts.join(" ");
                  handleVerseClick(book, chapter, verse.verse_id);
                }}
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
      </main>
    </div>
  );
}
