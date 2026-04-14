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
