import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight, Bookmark, Minus, Plus } from "lucide-react";
import { getChapter, getErrorMessage, isAbortError } from "@/lib/api";
import { useCollectionsStore } from "@/stores/useCollectionsStore";
import type { ChapterResponse } from "@/types/api";

// Fixed widths so the loading skeleton doesn't jump around on re-render
const SKELETON_WIDTHS = [92, 78, 85, 70, 96, 81, 74, 88];

/** The outcome of loading one chapter, tagged with the request it belongs to. */
interface ChapterResult {
  key: string;
  data: ChapterResponse | null;
  error: string | null;
}

export default function ReaderPage() {
  // React Router already decodes route params.
  const { book = "", chapter = "" } = useParams<{ book: string; chapter: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const highlightVerse = searchParams.get("highlight");
  const [result, setResult] = useState<ChapterResult | null>(null);
  const [fontSize, setFontSize] = useState(18);
  // Verse whose actions are shown after a tap or Enter (hover can't reach them on touch screens).
  const [selectedVerseId, setSelectedVerseId] = useState<string | null>(null);
  const highlightRef = useRef<HTMLSpanElement>(null);

  const { toggleFavorite, isFavorite } = useCollectionsStore();

  const bookName = book.trim();
  const chapterNum = /^\d+$/.test(chapter) ? Number(chapter) : NaN;
  const isValidReference = bookName.length > 0 && chapterNum >= 1;
  const requestKey = `${bookName}/${chapterNum}`;

  useEffect(() => {
    if (!isValidReference) return;

    const controller = new AbortController();
    getChapter(bookName, chapterNum, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setResult({ key: requestKey, data, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isAbortError(err)) return;
        setResult({
          key: requestKey,
          data: null,
          error: getErrorMessage(err, "Failed to load chapter."),
        });
      });

    return () => controller.abort();
  }, [bookName, chapterNum, requestKey, isValidReference]);

  // Only show data for the chapter in the URL: never a previous chapter while loading or on error.
  const current = result?.key === requestKey ? result : null;
  const chapterData = current?.data ?? null;
  const error = isValidReference
    ? current?.error ?? null
    : "That chapter reference isn't valid.";
  const loading = isValidReference && current === null;

  const displayBook = chapterData?.book ?? bookName.replace(/_/g, " ");
  const totalChapters = chapterData?.total_chapters;
  const hasPrevious = isValidReference && chapterNum > 1;
  // Next needs the loaded chapter to know whether this is the book's last chapter.
  const hasNext =
    chapterData !== null && (typeof totalChapters !== "number" || chapterNum < totalChapters);

  // Scroll to highlighted verse
  useEffect(() => {
    if (!chapterData || !highlightVerse) return;
    const timer = window.setTimeout(() => {
      highlightRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [chapterData, highlightVerse]);

  const goToChapter = (delta: number) => {
    navigate(`/read/${encodeURIComponent(chapterData?.book ?? bookName)}/${chapterNum + delta}`);
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
          <span className="font-medium">{displayBook}</span>
          <span className="text-cream/60">Chapter {isValidReference ? chapterNum : chapter}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => goToChapter(-1)}
            disabled={!hasPrevious}
            aria-label="Previous chapter"
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => goToChapter(1)}
            disabled={!hasNext}
            aria-label="Next chapter"
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30"
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
                <div key={i} className="h-5 bg-muted rounded" style={{ width: `${SKELETON_WIDTHS[i]}%` }} />
              ))}
            </div>
          )}

          {error && (
            <div role="alert" className="bg-destructive/10 text-destructive rounded-lg p-4 text-sm">
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
                  const isSelected = selectedVerseId === verse.verse_id;
                  const toggleSelected = () =>
                    setSelectedVerseId((id) => (id === verse.verse_id ? null : verse.verse_id));
                  return (
                    <span
                      key={verse.verse_id}
                      ref={isHighlighted ? highlightRef : undefined}
                      tabIndex={0}
                      onClick={toggleSelected}
                      onKeyDown={(e) => {
                        if (e.target !== e.currentTarget) return;
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          toggleSelected();
                        }
                      }}
                      className={`group relative inline cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 rounded ${
                        isHighlighted ? "bg-gold/15 px-1 -mx-1" : ""
                      }`}
                    >
                      <sup className="text-gold font-sans text-xs font-semibold mr-1 select-none">
                        {verse.verse_num}
                      </sup>
                      {verse.text}{" "}

                      {/* Verse actions: on hover, or after tapping / pressing Enter on the verse */}
                      <span
                        className={`${
                          isSelected ? "inline-flex" : "hidden"
                        } group-hover:inline-flex group-focus-within:inline-flex absolute -top-8 left-0 items-center gap-1 bg-navy dark:bg-card rounded-md px-2 py-1 shadow-lg z-10`}
                      >
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); toggleFavorite(verse.verse_id); }}
                          aria-label={`Favorite ${chapterData.book} ${chapterData.chapter}:${verse.verse_num}`}
                          aria-pressed={isFavorite(verse.verse_id)}
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
            disabled={!hasPrevious}
            className="px-3 py-1 text-xs rounded hover:bg-muted disabled:opacity-30"
          >
            Prev
          </button>
          <button
            onClick={() => goToChapter(1)}
            disabled={!hasNext}
            className="px-3 py-1 text-xs rounded hover:bg-muted disabled:opacity-30"
          >
            Next
          </button>
        </div>
      </footer>
    </div>
  );
}
