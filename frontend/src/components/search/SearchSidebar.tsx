import { Sparkles } from "lucide-react";
import { useSearchStore } from "@/stores/useSearchStore";
import type { SearchMode, AnalysisDepth } from "@/types/api";

interface SearchSidebarProps {
  open: boolean;
  onSummarize: () => void;
}

export default function SearchSidebar({ open, onSummarize }: SearchSidebarProps) {
  const { searchMode, depth, setSearchMode, setDepth } = useSearchStore();

  if (!open) return null;

  return (
    <aside className="hidden md:block w-[280px] shrink-0 bg-surface-low dark:bg-card p-6 min-h-[calc(100vh-64px)]">
      {/* Search Mode */}
      <div className="mb-6">
        <h3 className="font-sans text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Search Mode
        </h3>
        <div className="space-y-1.5">
          {([
            { value: "semantic", label: "Semantic", desc: "AI meaning" },
            { value: "keyword", label: "Keyword", desc: "Exact match" },
            { value: "hybrid", label: "Hybrid", desc: "Combined" },
          ] as { value: SearchMode; label: string; desc: string }[]).map(({ value, label, desc }) => (
            <button
              key={value}
              onClick={() => setSearchMode(value)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                searchMode === value
                  ? "bg-navy text-gold-light"
                  : "text-foreground hover:bg-surface-high dark:hover:bg-muted"
              }`}
            >
              <span className="font-medium">{label}</span>
              <span className="text-xs opacity-70 ml-1">({desc})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Depth */}
      <div className="mb-6">
        <h3 className="font-sans text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Search Depth
        </h3>
        <div className="space-y-1.5">
          {([
            { value: "quick", label: "Quick", desc: "Top 10" },
            { value: "balanced", label: "Balanced", desc: "Top 25" },
            { value: "comprehensive", label: "Comprehensive", desc: "Top 50" },
          ] as { value: AnalysisDepth; label: string; desc: string }[]).map(({ value, label, desc }) => (
            <button
              key={value}
              onClick={() => setDepth(value)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                depth === value
                  ? "bg-navy text-gold-light"
                  : "text-foreground hover:bg-surface-high dark:hover:bg-muted"
              }`}
            >
              <span className="font-medium">{label}</span>
              <span className="text-xs opacity-70 ml-1">({desc})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Summarize button */}
      <button onClick={onSummarize} className="btn-scriptorium w-full flex items-center justify-center gap-2">
        <Sparkles className="w-4 h-4" />
        Summarize with AI
      </button>
    </aside>
  );
}
