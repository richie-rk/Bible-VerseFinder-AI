import type { SearchResponse } from "@/types/api";

interface ResultsHeaderProps {
  results: SearchResponse;
}

export function ResultsHeader({ results }: ResultsHeaderProps) {
  return (
    <div className="pb-4 mb-4 border-b border-border">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className="text-base font-semibold text-foreground">
          Found {results.pagination.total_results} verses
        </span>
        <span className="text-sm text-muted-foreground">
          {results.timing.total_ms}ms
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <span className="inline-block px-2 py-1 bg-muted text-muted-foreground text-xs rounded">
          Mode: {results.mode}
        </span>
        <span className="inline-block px-2 py-1 bg-muted text-muted-foreground text-xs rounded">
          Query type: {results.query_type.replace(/_/g, " ")}
        </span>
        <span className="inline-block px-2 py-1 bg-muted text-muted-foreground text-xs rounded">
          α: {results.alpha}
        </span>
      </div>
    </div>
  );
}
