import { useState, useCallback, useRef } from "react";
import { getChapter, parseVerseId } from "@/lib/api";
import type { ChapterResponse } from "@/types/api";
import { useAppState } from "./useAppState";

export function useChapter() {
  const [chapterData, setChapterData] = useState<ChapterResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  
  const { openChapterModal, closeChapterModal } = useAppState();

  const fetchChapter = useCallback(
    async (verseId: string) => {
      const { book, chapter } = parseVerseId(verseId);

      // Cancel any pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);
      openChapterModal(book, chapter, verseId);

      try {
        const data = await getChapter(
          book,
          chapter,
          abortControllerRef.current.signal
        );
        setChapterData(data);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          setError(err.message || "Failed to load chapter");
        }
      } finally {
        setIsLoading(false);
      }
    },
    [openChapterModal]
  );

  const close = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    closeChapterModal();
    setChapterData(null);
    setError(null);
  }, [closeChapterModal]);

  return { chapterData, isLoading, error, fetchChapter, close };
}
