import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Collection {
  id: string;
  name: string;
  icon: string;
  verseIds: string[];
  createdAt: number;
  updatedAt: number;
}

interface CollectionsState {
  collections: Collection[];
  favorites: string[];

  // Favorites
  toggleFavorite: (verseId: string) => void;
  isFavorite: (verseId: string) => boolean;

  // Collections
  createCollection: (name: string, icon?: string) => string;
  deleteCollection: (id: string) => void;
  renameCollection: (id: string, name: string) => void;
  addToCollection: (collectionId: string, verseId: string) => void;
  removeFromCollection: (collectionId: string, verseId: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 10);

export const useCollectionsStore = create<CollectionsState>()(
  persist(
    (set, get) => ({
      collections: [
        {
          id: "default-study",
          name: "Study Notes",
          icon: "notebook",
          verseIds: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
        {
          id: "default-sermon",
          name: "Sermon Prep",
          icon: "mic",
          verseIds: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
      ],
      favorites: [],

      toggleFavorite: (verseId) =>
        set((state) => {
          const idx = state.favorites.indexOf(verseId);
          if (idx >= 0) {
            return { favorites: state.favorites.filter((id) => id !== verseId) };
          }
          return { favorites: [...state.favorites, verseId] };
        }),

      isFavorite: (verseId) => get().favorites.includes(verseId),

      createCollection: (name, icon = "folder") => {
        const id = generateId();
        set((state) => ({
          collections: [
            ...state.collections,
            {
              id,
              name,
              icon,
              verseIds: [],
              createdAt: Date.now(),
              updatedAt: Date.now(),
            },
          ],
        }));
        return id;
      },

      deleteCollection: (id) =>
        set((state) => ({
          collections: state.collections.filter((c) => c.id !== id),
        })),

      renameCollection: (id, name) =>
        set((state) => ({
          collections: state.collections.map((c) =>
            c.id === id ? { ...c, name, updatedAt: Date.now() } : c
          ),
        })),

      addToCollection: (collectionId, verseId) =>
        set((state) => ({
          collections: state.collections.map((c) =>
            c.id === collectionId && !c.verseIds.includes(verseId)
              ? {
                  ...c,
                  verseIds: [...c.verseIds, verseId],
                  updatedAt: Date.now(),
                }
              : c
          ),
        })),

      removeFromCollection: (collectionId, verseId) =>
        set((state) => ({
          collections: state.collections.map((c) =>
            c.id === collectionId
              ? {
                  ...c,
                  verseIds: c.verseIds.filter((id) => id !== verseId),
                  updatedAt: Date.now(),
                }
              : c
          ),
        })),
    }),
    { name: "versefinder-collections" }
  )
);

/** localStorage key of the old standalone favorites hook (a JSON array of verse IDs). */
const LEGACY_FAVORITES_KEY = "favorites";

/**
 * One-time migration: merges favorites saved under the legacy "favorites" key into this store,
 * then removes the legacy key. Safe to call repeatedly (it is a no-op once the key is gone).
 */
function migrateLegacyFavorites(): void {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(LEGACY_FAVORITES_KEY);
  } catch {
    return;
  }
  if (raw === null) return;

  let legacy: unknown = null;
  try {
    legacy = JSON.parse(raw);
  } catch {
    // Unreadable legacy data: nothing to migrate, just drop it below.
  }

  const legacyIds = Array.isArray(legacy)
    ? legacy.filter((id): id is string => typeof id === "string" && id.length > 0)
    : [];
  if (legacyIds.length > 0) {
    useCollectionsStore.setState((state) => {
      const favorites = [...state.favorites];
      for (const id of legacyIds) {
        if (!favorites.includes(id)) favorites.push(id);
      }
      return { favorites };
    });
  }

  try {
    window.localStorage.removeItem(LEGACY_FAVORITES_KEY);
  } catch {
    // Ignore storage errors; the merge above is idempotent.
  }
}

if (typeof window !== "undefined") {
  if (useCollectionsStore.persist.hasHydrated()) {
    migrateLegacyFavorites();
  } else {
    const unsubscribe = useCollectionsStore.persist.onFinishHydration(() => {
      unsubscribe();
      migrateLegacyFavorites();
    });
  }
}
