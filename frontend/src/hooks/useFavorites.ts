import { useState, useCallback, useEffect } from "react";

const STORAGE_KEY = "favorites";

export function useFavorites() {
  const [favorites, setFavorites] = useState<Set<string>>(new Set());

  // Load favorites from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setFavorites(new Set(JSON.parse(stored)));
      }
    } catch {
      // Ignore parse errors
    }
  }, []);

  const toggleFavorite = useCallback((verseId: string) => {
    setFavorites((prev) => {
      const newFavorites = new Set(prev);
      
      if (newFavorites.has(verseId)) {
        newFavorites.delete(verseId);
      } else {
        newFavorites.add(verseId);
      }

      // Persist to localStorage
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify([...newFavorites]));
      } catch {
        // Ignore storage errors
      }

      return newFavorites;
    });
  }, []);

  const isFavorite = useCallback(
    (verseId: string) => favorites.has(verseId),
    [favorites]
  );

  const clearFavorites = useCallback(() => {
    setFavorites(new Set());
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore storage errors
    }
  }, []);

  return { favorites, toggleFavorite, isFavorite, clearFavorites };
}
