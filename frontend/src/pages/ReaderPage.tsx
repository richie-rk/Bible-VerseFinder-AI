import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight, Bookmark, Minus, Plus } from "lucide-react";
import { getChapter } from "@/lib/api";
import { useCollectionsStore } from "@/stores/useCollectionsStore";
import type { ChapterResponse } from "@/types/api";

export default function ReaderPage() {
  const { book, chapter } = useParams<{ book: string; chapter: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const highlightVerse = searchParams.get("highlight");
  const [chapterData, setChapterData] = useState<ChapterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fontSize, setFontSize] = useState(18);
  const highlightRef = useRef<HTMLSpanElement>(null);

  const { toggleFavorite, isFavorite } = useCollectionsStore();

  const bookName = book ? decodeURIComponent(book) : "";
  const chapterNum = chapter ? parseInt(chapter) : 1;

  useEffect(() => {
    if (!bookName || !chapterNum) return;

    setLoading(true);
    setError(null);

    const controller = new AbortController();
    getChapter(bookName, chapterNum, controller.signal)
      .then((data) => {
        setChapterData(data);
        setLoading(false);
      })
      .catch((err) => {
        if (err instanceof Error && err.name !== "AbortError") {
          setError(err.message || "Failed to load chapter.");
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [bookName, chapterNum]);

  // Scroll to highlighted verse
  useEffect(() => {
    if (highlightRef.current && !loading) {
      setTimeout(() => {
        highlightRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 300);
    }
  }, [loading, highlightVerse]);

  const goToChapter = (delta: number) => {
    navigate(`/read/${encodeURIComponent(bookName)}/${chapterNum + delta}`);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Compact header */}
      <header className="sticky top-0 z-30 bg-navy dark:bg-navy-deep text-white px-4 py-2 flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-cream/80 hover:text-cream"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>

        <div className="flex items-center gap-2 font-sans text-sm">
          <span className="font-medium">{bookName}</span>
          <span className="text-cream/60">Chapter {chapterNum}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => goToChapter(-1)}
            disabled={chapterNum <= 1}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => goToChapter(1)}
            className="p-1.5 rounded hover:bg-white/10"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Reading area */}
      <main className="flex-1 bg-surface-lowest dark:bg-background">
        <div className="max-w-[720px] mx-auto px-6 md:px-20 py-10">
          {loading && (
            <div className="space-y-4 animate-pulse">
              <div className="h-10 bg-muted rounded w-48" />
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-5 bg-muted rounded" style={{ width: `${70 + Math.random() * 30}%` }} />
              ))}
            </div>
          )}

          {error && (
            <div className="bg-destructive/10 text-destructive rounded-lg p-4 text-sm">
              {error}
            </div>
          )}

          {chapterData && (
            <>
              <h1 className="font-serif text-3xl md:text-4xl font-medium text-foreground mb-8">
                {chapterData.book} {chapterData.chapter}
              </h1>

              <div className="text-scripture" style={{ fontSize: `${fontSize}px`, lineHeight: 1.9 }}>
                {chapterData.verses.map((verse) => {
                  const isHighlighted = highlightVerse === String(verse.verse_num);
                  return (
                    <span
                      key={verse.verse_id}
                      ref={isHighlighted ? highlightRef : undefined}
                      className={`group relative inline ${
                        isHighlighted ? "bg-gold/15 rounded px-1 -mx-1" : ""
                      }`}
                    >
                      <sup className="text-gold font-sans text-xs font-semibold mr-1 select-none">
                        {verse.verse_num}
                      </sup>
                      {verse.text}{" "}

                      {/* Hover actions */}
                      <span className="hidden group-hover:inline-flex absolute -top-8 left-0 items-center gap-1 bg-navy dark:bg-card rounded-md px-2 py-1 shadow-lg z-10">
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleFavorite(verse.verse_id); }}
                          className="p-0.5"
                        >
                          <Bookmark
                            className={`w-3.5 h-3.5 ${
                              isFavorite(verse.verse_id) ? "fill-gold text-gold" : "text-cream/70"
                            }`}
                          />
                        </button>
                      </span>
                    </span>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </main>

      {/* Bottom bar */}
      <footer className="sticky bottom-0 bg-surface-low dark:bg-card border-t border-border px-4 py-2 flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <button onClick={() => setFontSize((s) => Math.max(14, s - 2))} className="p-1 rounded hover:bg-muted">
            <Minus className="w-4 h-4" />
          </button>
          <span className="text-xs text-muted-foreground w-8 text-center">{fontSize}</span>
          <button onClick={() => setFontSize((s) => Math.min(28, s + 2))} className="p-1 rounded hover:bg-muted">
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {chapterData && (
          <span className="text-xs text-muted-foreground">
            {chapterData.total_verses} verses
          </span>
        )}

        <div className="flex items-center gap-1">
          <button
            onClick={() => goToChapter(-1)}
            disabled={chapterNum <= 1}
            className="px-3 py-1 text-xs rounded hover:bg-muted disabled:opacity-30"
          >
            Prev
          </button>
          <button
            onClick={() => goToChapter(1)}
            className="px-3 py-1 text-xs rounded hover:bg-muted"
          >
            Next
          </button>
        </div>
      </footer>
    </div>
  );
}
