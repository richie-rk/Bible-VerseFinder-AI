import { useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Sparkles, Lightbulb, Network, BookOpen, Copy, RefreshCw } from "lucide-react";
import { useSummaryStore } from "@/stores/useSummaryStore";
import { useSearchStore } from "@/stores/useSearchStore";
import { summarizeVerses } from "@/lib/api";
import { parseVerseId } from "@/lib/api";
import { SkeletonCard } from "@/components/SkeletonCard";

export default function SummaryPage() {
  const { query } = useParams<{ query: string }>();
  const navigate = useNavigate();
  const abortRef = useRef<AbortController | null>(null);

  const { summarizeResults, isSummarizing, setSummarizeResults, setIsSummarizing, resetSummary } = useSummaryStore();
  const { searchMode, depth, setError } = useSearchStore();

  const runSummarize = async (term: string) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    resetSummary();
    setIsSummarizing(true);

    try {
      const results = await summarizeVerses(
        { query: term, depth, mode: searchMode },
        abortRef.current.signal
      );
      setSummarizeResults(results);
    } catch (err) {
      if (err instanceof Error && err.name !== "AbortError") {
        setError(err.message || "Summarization failed.");
      }
    } finally {
      setIsSummarizing(false);
    }
  };

  useEffect(() => {
    const decoded = query ? decodeURIComponent(query) : "";
    if (decoded) runSummarize(decoded);
    return () => { abortRef.current?.abort(); };
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCitationClick = (verseId: string) => {
    const { book, chapter, verse } = parseVerseId(verseId);
    navigate(`/read/${encodeURIComponent(book)}/${chapter}?highlight=${verse}`);
  };

  const decodedQuery = query ? decodeURIComponent(query) : "";

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
        <Link to="/" className="hover:text-foreground">Home</Link>
        <span>/</span>
        <Link to={`/search/${query}`} className="hover:text-foreground">Search</Link>
        <span>/</span>
        <span className="text-foreground">&lsquo;{decodedQuery}&rsquo;</span>
      </nav>

      {/* Loading */}
      {isSummarizing && (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {summarizeResults && (
        <>
          {/* AI Summary Card */}
          <div
            className="bg-surface-lowest dark:bg-card rounded-lg p-8 mb-8 border-t-[3px] border-t-gold"
            style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.06)" }}
          >
            <div className="flex items-center gap-3 mb-4">
              <Sparkles className="w-5 h-5 text-gold" />
              <h2 className="font-sans font-semibold text-lg">AI Summary</h2>
              <span className="ml-auto px-3 py-0.5 rounded-full bg-gold/15 text-gold-dark dark:text-gold text-xs font-medium">
                {Math.round(summarizeResults.confidence * 100)}% confidence
              </span>
            </div>
            <p className="text-scripture text-base leading-relaxed text-foreground mb-4">
              {summarizeResults.summary}
            </p>
            <p className="text-xs text-muted-foreground">
              Powered by {summarizeResults.llm_model} &middot; {summarizeResults.tokens_used} tokens &middot; {summarizeResults.timing.total_ms}ms
            </p>
          </div>

          {/* Key Insights */}
          {summarizeResults.key_points.length > 0 && (
            <section className="mb-8">
              <div className="flex items-center gap-2 mb-4">
                <Lightbulb className="w-5 h-5 text-gold" />
                <h3 className="font-sans font-semibold text-lg">Key Insights</h3>
              </div>
              <ul className="space-y-3">
                {summarizeResults.key_points.map((point, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="mt-1.5 w-2 h-2 rounded-full bg-gold shrink-0" />
                    <p className="text-sm text-foreground leading-relaxed">{point}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Thematic Connections */}
          {summarizeResults.thematic_connections.length > 0 && (
            <section className="mb-8">
              <div className="flex items-center gap-2 mb-4">
                <Network className="w-5 h-5 text-gold" />
                <h3 className="font-sans font-semibold text-lg">Related Themes</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {summarizeResults.thematic_connections.map((theme) => (
                  <div
                    key={theme.theme}
                    className="bg-surface-low dark:bg-card rounded-lg p-5"
                    style={{ border: "1px solid rgba(199, 197, 206, 0.15)" }}
                  >
                    <h4 className="font-sans font-semibold text-sm mb-2">{theme.theme}</h4>
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {theme.verses.map((v) => (
                        <button
                          key={v}
                          onClick={() => handleCitationClick(v)}
                          className="px-2 py-0.5 text-xs rounded-full bg-gold/10 text-gold-dark dark:text-gold font-medium hover:bg-gold/20 transition-colors"
                        >
                          {v.replace(/_/g, " ")}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {theme.explanation}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Cited Verses */}
          {summarizeResults.citations.length > 0 && (
            <section className="mb-8">
              <div className="flex items-center gap-2 mb-4">
                <BookOpen className="w-5 h-5 text-gold" />
                <h3 className="font-sans font-semibold text-lg">Cited Verses</h3>
              </div>
              <div className="space-y-3">
                {summarizeResults.citations.map((citation) => (
                  <div
                    key={citation.verse_id}
                    className="bg-surface-lowest dark:bg-card rounded-lg p-5"
                    style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.04)" }}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <button
                        onClick={() => handleCitationClick(citation.verse_id)}
                        className="font-serif font-semibold text-sm link-burgundy"
                      >
                        {citation.verse_id.replace(/_/g, " ")}
                      </button>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        citation.relevance === "primary"
                          ? "bg-gold/15 text-gold-dark dark:text-gold"
                          : citation.relevance === "supporting"
                          ? "bg-navy/10 text-navy dark:bg-cream/10 dark:text-cream"
                          : "bg-muted text-muted-foreground"
                      }`}>
                        {citation.relevance}
                      </span>
                    </div>
                    <p className="text-scripture text-sm text-foreground leading-relaxed">
                      {citation.text}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Footer actions */}
          <div className="flex items-center gap-3 pt-4 border-t border-border">
            <button
              onClick={() => runSummarize(decodedQuery)}
              className="btn-ghost flex items-center gap-2 text-sm"
            >
              <RefreshCw className="w-4 h-4" /> Regenerate
            </button>
            <button
              onClick={() => navigator.clipboard.writeText(summarizeResults.summary)}
              className="btn-ghost flex items-center gap-2 text-sm"
            >
              <Copy className="w-4 h-4" /> Copy Summary
            </button>
          </div>
        </>
      )}
    </div>
  );
}
