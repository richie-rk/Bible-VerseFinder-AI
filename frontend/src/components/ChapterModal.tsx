import { useEffect, useRef, useCallback } from "react";
import { X, Loader2 } from "lucide-react";
import type { ChapterResponse } from "@/types/api";
import { parseVerseId } from "@/lib/api";

interface ChapterModalProps {
  isOpen: boolean;
  book: string;
  chapter: number;
  highlightVerse: string;
  chapterData: ChapterResponse | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}

export function ChapterModal({
  isOpen,
  book,
  chapter,
  highlightVerse,
  chapterData,
  isLoading,
  error,
  onClose,
}: ChapterModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);

  // Parse highlighted verse number
  const highlightVerseNum = highlightVerse
    ? parseVerseId(highlightVerse).verse
    : null;

  // Scroll to highlighted verse
  useEffect(() => {
    if (chapterData && highlightRef.current) {
      setTimeout(() => {
        highlightRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 100);
    }
  }, [chapterData]);

  // Focus trap and body scroll lock
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
      modalRef.current?.focus();
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  // Handle overlay click
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay flex items-center justify-center p-4"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        ref={modalRef}
        className="modal-content bg-card rounded-xl shadow-xl w-full max-w-[600px] max-h-[80vh] flex flex-col overflow-hidden"
        tabIndex={-1}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-border">
          <div>
            <h2
              id="modal-title"
              className="text-xl font-semibold text-foreground"
            >
              {book} Chapter {chapter}
            </h2>
            {chapterData && (
              <p className="text-sm text-muted-foreground mt-1">
                {chapterData.total_verses} verses
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted transition-colors text-primary"
            aria-label="Close modal"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 text-primary spinner" />
            </div>
          )}

          {error && (
            <div className="text-center py-12">
              <p className="text-destructive mb-4">{error}</p>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg"
              >
                Close
              </button>
            </div>
          )}

          {chapterData && (
            <div className="space-y-4">
              {chapterData.verses.map((verse) => {
                const isHighlighted = verse.verse_num === highlightVerseNum;
                return (
                  <div
                    key={verse.verse_num}
                    ref={isHighlighted ? highlightRef : null}
                    className={`flex gap-3 p-3 rounded-lg transition-colors ${
                      isHighlighted
                        ? "bg-[hsl(var(--highlight))]"
                        : "hover:bg-muted/50"
                    }`}
                  >
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-semibold flex items-center justify-center">
                      {verse.verse_num}
                    </span>
                    <p className="text-[15px] leading-relaxed text-foreground">
                      {verse.text}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-border">
          <button
            onClick={onClose}
            className="w-full h-12 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-secondary/80 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
