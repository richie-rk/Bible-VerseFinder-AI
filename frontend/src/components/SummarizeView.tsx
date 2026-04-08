import { useCallback } from "react";
import { Sparkles, CheckCircle, Link2, BookOpen, Loader2 } from "lucide-react";
import type { SummarizationResponse, Citation } from "@/types/api";

interface SummarizeViewProps {
  results: SummarizationResponse | null;
  isLoading: boolean;
  onCitationClick: (verseId: string) => void;
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 90) return "bg-green-500";
  if (confidence >= 70) return "bg-primary";
  if (confidence >= 50) return "bg-orange-500";
  return "bg-red-500";
}

function getRelevanceBadgeStyle(relevance: Citation["relevance"]): string {
  switch (relevance) {
    case "primary":
      return "bg-primary text-primary-foreground";
    case "supporting":
      return "bg-blue-500 text-white";
    case "contextual":
      return "bg-muted text-muted-foreground";
  }
}

// Parse [verse_id] citations in text and render as clickable links
function parseCitations(
  text: string,
  onCitationClick: (verseId: string) => void
): React.ReactNode[] {
  const parts = text.split(/(\[[^\]]+\])/g);

  return parts.map((part, index) => {
    const match = part.match(/^\[([^\]]+)\]$/);
    if (match) {
      const verseId = match[1];
      return (
        <button
          key={index}
          onClick={() => onCitationClick(verseId)}
          className="text-primary hover:underline font-medium"
        >
          [{verseId}]
        </button>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

export function SummarizeView({
  results,
  isLoading,
  onCitationClick,
}: SummarizeViewProps) {
  const scrollToCitation = useCallback((verseId: string) => {
    const element = document.getElementById(verseId);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
      element.classList.add("ring-2", "ring-primary");
      setTimeout(() => {
        element.classList.remove("ring-2", "ring-primary");
      }, 2000);
    }
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div
        className="space-y-4"
        aria-busy="true"
        aria-label="Generating summary"
      >
        {/* Skeleton for summary */}
        <div className="bg-primary/5 border border-primary/20 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Loader2 className="h-5 w-5 text-primary spinner" />
            <span className="text-primary font-medium">
              Analyzing verses with AI...
            </span>
          </div>
          <div className="space-y-2">
            <div className="h-4 w-full bg-muted rounded skeleton-pulse" />
            <div className="h-4 w-5/6 bg-muted rounded skeleton-pulse" />
            <div className="h-4 w-4/6 bg-muted rounded skeleton-pulse" />
          </div>
        </div>

        {/* Skeleton for key points */}
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-4 bg-muted rounded skeleton-pulse"
              style={{ width: `${80 - i * 10}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (!results) {
    return null;
  }

  const confidencePercent = Math.round(results.confidence * 100);

  return (
    <div className="space-y-6" aria-live="polite">
      {/* AI Summary Card */}
      <section className="bg-primary/5 border border-primary/20 rounded-xl p-5">
        <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">
              AI Summary
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`px-2.5 py-1 rounded-full text-xs font-medium text-white ${getConfidenceColor(
                confidencePercent
              )}`}
            >
              {confidencePercent}%
            </span>
            <span className="text-xs text-muted-foreground">
              {results.verses_analyzed} verses analyzed
            </span>
          </div>
        </div>

        <p className="text-base leading-relaxed text-foreground">
          {parseCitations(results.summary, scrollToCitation)}
        </p>

        <p className="text-xs text-muted-foreground mt-4">
          Powered by {results.llm_provider} ({results.llm_model}) |{" "}
          {results.tokens_used} tokens | {results.timing.total_ms}ms
        </p>
      </section>

      {/* Key Points */}
      {results.key_points.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="h-5 w-5 text-primary" />
            <h3 className="text-base font-semibold text-foreground">
              Key Points
            </h3>
          </div>
          <ul className="space-y-2">
            {results.key_points.map((point, index) => (
              <li
                key={index}
                className="flex items-start gap-3 p-3 bg-card border-l-[3px] border-l-primary rounded-r-lg"
              >
                <span className="text-primary font-bold">•</span>
                <span className="text-[15px] leading-relaxed">
                  {parseCitations(point, scrollToCitation)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Thematic Connections */}
      {results.thematic_connections && results.thematic_connections.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Link2 className="h-5 w-5 text-primary" />
            <h3 className="text-base font-semibold text-foreground">
              Thematic Connections
            </h3>
          </div>
          <div className="space-y-3">
            {results.thematic_connections.map((connection, index) => (
              <div
                key={index}
                className="bg-card border border-border rounded-lg p-4"
              >
                <h4 className="font-semibold text-foreground mb-2">
                  {connection.theme}
                </h4>
                <div className="flex flex-wrap gap-2 mb-2">
                  {connection.verses.map((verseId) => (
                    <button
                      key={verseId}
                      onClick={() => scrollToCitation(verseId)}
                      className="px-2.5 py-1 rounded-full text-xs font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
                    >
                      {verseId}
                    </button>
                  ))}
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {connection.explanation}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Cited Verses */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="h-5 w-5 text-primary" />
          <h3 className="text-base font-semibold text-foreground">
            Referenced Verses ({results.citations.length})
          </h3>
        </div>
        <div className="space-y-3">
          {results.citations.map((citation) => (
            <article
              key={citation.verse_id}
              id={citation.verse_id}
              onClick={() => onCitationClick(citation.verse_id)}
              className="bg-card border border-border rounded-lg p-4 cursor-pointer hover:shadow-md transition-all duration-200"
              role="button"
              tabIndex={0}
              onKeyDown={(e) =>
                e.key === "Enter" && onCitationClick(citation.verse_id)
              }
            >
              <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                <span className="text-primary font-bold">
                  {citation.verse_id.replace(/_/g, " ")}
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${getRelevanceBadgeStyle(
                    citation.relevance
                  )}`}
                >
                  {citation.relevance}
                </span>
              </div>
              <p className="text-[15px] leading-relaxed text-foreground">
                {citation.text}
              </p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
