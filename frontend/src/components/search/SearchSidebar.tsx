import { Sparkles } from "lucide-react";
import { useSearchStore } from "@/stores/useSearchStore";
import { DEPTH_VERSE_COUNT, SEARCH_MODES, SUMMARY_DEPTHS } from "@/lib/search";

/** Search mode and summary depth controls (desktop sidebar and mobile filter panel). */
export function SearchFilters() {
  const { searchMode, depth, setSearchMode, setDepth } = useSearchStore();

  return (
    <>
      {/* Search Mode */}
      <div className="mb-6">
        <h3 className="font-sans text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Search Mode
        </h3>
        <div className="space-y-1.5">
          {SEARCH_MODES.map(({ value, label, description }) => (
            <button
              key={value}
              type="button"
              onClick={() => setSearchMode(value)}
              aria-pressed={searchMode === value}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                searchMode === value
                  ? "bg-navy text-gold-light"
                  : "text-foreground hover:bg-surface-high dark:hover:bg-muted"
              }`}
            >
              <span className="font-medium">{label}</span>
              <span className="text-xs opacity-70 ml-1">({description})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Summary depth (only affects AI summaries, not the search results) */}
      <div className="mb-6">
        <h3 className="font-sans text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
          Summary Depth
        </h3>
        <p className="text-xs text-muted-foreground mb-3">Applies to AI summaries only</p>
        <div className="space-y-1.5">
          {SUMMARY_DEPTHS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => setDepth(value)}
              aria-pressed={depth === value}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                depth === value
                  ? "bg-navy text-gold-light"
                  : "text-foreground hover:bg-surface-high dark:hover:bg-muted"
              }`}
            >
              <span className="font-medium">{label}</span>
              <span className="text-xs opacity-70 ml-1">({DEPTH_VERSE_COUNT[value]} verses)</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

interface SearchSidebarProps {
  onSummarize: () => void;
}

/** Desktop sidebar; below the md breakpoint the results page shows its own filter panel. */
export default function SearchSidebar({ onSummarize }: SearchSidebarProps) {
  return (
    <aside className="hidden md:block w-[280px] shrink-0 bg-surface-low dark:bg-card p-6 min-h-[calc(100vh-64px)]">
      <SearchFilters />

      {/* Summarize button */}
      <button
        type="button"
        onClick={onSummarize}
        className="btn-scriptorium w-full flex items-center justify-center gap-2"
      >
        <Sparkles className="w-4 h-4" />
        Summarize with AI
      </button>
    </aside>
  );
}
