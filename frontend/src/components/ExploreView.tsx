import { useEffect, useRef, useCallback } from "react";
import type { SearchResponse } from "@/types/api";
import { VerseCard } from "./VerseCard";
import { SkeletonCard } from "./SkeletonCard";
import { ResultsHeader } from "./ResultsHeader";
import { Loader2, SearchX } from "lucide-react";

interface ExploreViewProps {
  results: SearchResponse | null;
  isLoading: boolean;
  onLoadMore: () => void;
  onVerseClick: (verseId: string) => void;
  query?: string;
}

export function ExploreView({
  results,
  isLoading,
  onLoadMore,
  onVerseClick,
  query,
}: ExploreViewProps) {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  // Infinite scroll
  const handleObserver = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const [entry] = entries;
      if (
        entry.isIntersecting &&
        results?.pagination.has_more &&
        !isLoading
      ) {
        onLoadMore();
      }
    },
    [results?.pagination.has_more, isLoading, onLoadMore]
  );

  useEffect(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    observerRef.current = new IntersectionObserver(handleObserver, {
      rootMargin: "200px",
    });

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [handleObserver]);

  // Loading state (initial)
  if (isLoading && !results) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Loading results">
        <div className="text-center text-muted-foreground mb-4">
          Searching verses...
        </div>
        {[1, 2, 3, 4].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  // No results
  if (results && results.results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <SearchX className="h-16 w-16 text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold text-foreground mb-2">
          No verses found for "{query}"
        </h3>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li>• Try different keywords</li>
          <li>• Use semantic search for concepts</li>
          <li>• Check spelling</li>
        </ul>
      </div>
    );
  }

  if (!results) {
    return null;
  }

  return (
    <div aria-live="polite">
      <ResultsHeader results={results} />

      <div className="space-y-3">
        {results.results.map((verse) => (
          <VerseCard
            key={`${verse.verse_id}-${verse.rank}`}
            verse={verse}
            onClick={() => onVerseClick(verse.verse_id)}
          />
        ))}
      </div>

      {/* Infinite scroll trigger */}
      <div ref={loadMoreRef} className="h-4" />

      {/* Loading more */}
      {isLoading && results && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-6 w-6 text-primary spinner" />
        </div>
      )}

      {/* End of results */}
      {!results.pagination.has_more && results.results.length > 0 && (
        <p className="text-center text-sm text-muted-foreground py-4">
          End of results
        </p>
      )}
    </div>
  );
}
