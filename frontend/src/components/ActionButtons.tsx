import { Sparkles, BookOpen } from "lucide-react";
import type { ActiveView } from "@/types/api";

interface ActionButtonsProps {
  activeView: ActiveView;
  onSummarize: () => void;
  onExplore: () => void;
  isSummarizing?: boolean;
  isSearching?: boolean;
}

export function ActionButtons({
  activeView,
  onSummarize,
  onExplore,
  isSummarizing,
  isSearching,
}: ActionButtonsProps) {
  return (
    <div className="flex flex-col sm:flex-row items-center justify-center gap-3 w-full max-w-md mx-auto">
      <button
        onClick={onSummarize}
        disabled={isSummarizing}
        className="w-full sm:w-auto flex items-center justify-center gap-2 h-12 px-6 rounded-lg font-semibold text-sm text-primary-foreground transition-all duration-200 disabled:opacity-50"
        style={{ background: "var(--gradient-primary)" }}
        aria-current={activeView === "summarize" ? "page" : undefined}
      >
        <Sparkles className="h-5 w-5" aria-hidden="true" />
        {isSummarizing ? "Summarizing..." : "Summarize Answer"}
      </button>

      <button
        onClick={onExplore}
        disabled={isSearching}
        className={`w-full sm:w-auto flex items-center justify-center gap-2 h-12 px-6 rounded-lg font-semibold text-sm border-2 border-primary transition-all duration-200 disabled:opacity-50 ${
          activeView === "explore"
            ? "bg-primary text-primary-foreground"
            : "bg-card text-primary hover:bg-primary hover:text-primary-foreground"
        }`}
        aria-current={activeView === "explore" ? "page" : undefined}
      >
        <BookOpen className="h-5 w-5" aria-hidden="true" />
        {isSearching ? "Searching..." : "Explore Verses"}
      </button>
    </div>
  );
}
