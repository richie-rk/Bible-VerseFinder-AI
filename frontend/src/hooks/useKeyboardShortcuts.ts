import { useEffect, useCallback } from "react";
import { useAppState } from "./useAppState";

interface UseKeyboardShortcutsOptions {
  onFocusSearch?: () => void;
}

export function useKeyboardShortcuts(options: UseKeyboardShortcutsOptions = {}) {
  const { chapterModal, closeChapterModal } = useAppState();
  const { onFocusSearch } = options;

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // "/" key to focus search
      if (
        event.key === "/" &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey
      ) {
        const activeElement = document.activeElement;
        const isInputFocused =
          activeElement instanceof HTMLInputElement ||
          activeElement instanceof HTMLTextAreaElement;

        if (!isInputFocused) {
          event.preventDefault();
          onFocusSearch?.();
        }
      }

      // Escape to close modal
      if (event.key === "Escape" && chapterModal?.open) {
        event.preventDefault();
        closeChapterModal();
      }
    },
    [chapterModal, closeChapterModal, onFocusSearch]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleKeyDown]);
}
