import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Star, BookOpen, Mic, Heart, Folder, Trash2, ChevronRight } from "lucide-react";
import { useCollectionsStore } from "@/stores/useCollectionsStore";
import type { Collection } from "@/stores/useCollectionsStore";

const ICON_MAP: Record<string, React.ReactNode> = {
  notebook: <BookOpen className="w-5 h-5 text-gold" />,
  mic: <Mic className="w-5 h-5 text-gold" />,
  heart: <Heart className="w-5 h-5 text-gold" />,
  folder: <Folder className="w-5 h-5 text-gold" />,
};

export default function CollectionsPage() {
  const navigate = useNavigate();
  const { collections, favorites, createCollection, deleteCollection } = useCollectionsStore();
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");

  const handleCreate = () => {
    if (!newName.trim()) return;
    createCollection(newName.trim());
    setNewName("");
    setShowNewForm(false);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h1 className="font-serif text-3xl font-medium text-foreground">My Collections</h1>
        <button
          onClick={() => setShowNewForm(true)}
          className="btn-scriptorium flex items-center gap-2 text-sm"
        >
          <Plus className="w-4 h-4" />
          New Collection
        </button>
      </div>
      <p className="text-sm text-muted-foreground mb-8">
        Your saved verses and study collections
      </p>

      {/* New collection form */}
      {showNewForm && (
        <div className="bg-surface-lowest dark:bg-card rounded-lg p-4 mb-6 flex gap-3" style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.06)" }}>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Collection name..."
            className="flex-1 px-3 py-2 rounded-md bg-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-gold"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <button onClick={handleCreate} className="btn-scriptorium text-sm">Create</button>
          <button onClick={() => setShowNewForm(false)} className="btn-ghost text-sm">Cancel</button>
        </div>
      )}

      {/* Favorites card */}
      <div
        className="bg-surface-lowest dark:bg-card rounded-lg p-6 border-l-4 border-l-gold mb-4 cursor-pointer hover:bg-surface-highest dark:hover:bg-muted transition-colors"
        style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.04)" }}
      >
        <div className="flex items-center gap-3 mb-2">
          <Star className="w-5 h-5 text-gold fill-gold" />
          <h3 className="font-serif font-semibold text-lg">Favorites</h3>
          <span className="ml-auto text-sm text-muted-foreground">{favorites.length} verses</span>
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        </div>
        {favorites.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {favorites.slice(0, 5).map((id) => (
              <span key={id} className="px-2 py-0.5 text-xs rounded-full bg-gold/10 text-gold-dark dark:text-gold font-medium">
                {id.replace(/_/g, " ")}
              </span>
            ))}
            {favorites.length > 5 && (
              <span className="text-xs text-muted-foreground">+{favorites.length - 5} more</span>
            )}
          </div>
        )}
        {favorites.length === 0 && (
          <p className="text-sm text-muted-foreground mt-1">
            Tap the bookmark icon on any verse to add it here
          </p>
        )}
      </div>

      {/* Collection cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {collections.map((collection) => (
          <CollectionCard
            key={collection.id}
            collection={collection}
            onDelete={() => deleteCollection(collection.id)}
          />
        ))}
      </div>

      {/* Empty state */}
      {collections.length === 0 && favorites.length === 0 && (
        <div className="text-center py-16">
          <BookOpen className="w-12 h-12 text-gold/40 mx-auto mb-4" />
          <h3 className="font-serif text-xl font-medium mb-2">Start Your Collection</h3>
          <p className="text-sm text-muted-foreground mb-6">
            Save your first verse by tapping the bookmark icon on any verse
          </p>
          <button
            onClick={() => navigate("/")}
            className="btn-scriptorium"
          >
            Explore Verses
          </button>
        </div>
      )}
    </div>
  );
}

function CollectionCard({ collection, onDelete }: { collection: Collection; onDelete: () => void }) {
  return (
    <div
      className="bg-surface-lowest dark:bg-card rounded-lg p-5 border-l-4 border-l-gold/50 cursor-pointer hover:bg-surface-highest dark:hover:bg-muted transition-colors group"
      style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.04)" }}
    >
      <div className="flex items-center gap-3 mb-2">
        {ICON_MAP[collection.icon] || <Folder className="w-5 h-5 text-gold" />}
        <h3 className="font-serif font-semibold">{collection.name}</h3>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="ml-auto p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-destructive/10 transition-all"
        >
          <Trash2 className="w-3.5 h-3.5 text-destructive" />
        </button>
      </div>
      <p className="text-sm text-muted-foreground">
        {collection.verseIds.length} verses
      </p>
      {collection.verseIds.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {collection.verseIds.slice(0, 3).map((id) => (
            <span key={id} className="px-2 py-0.5 text-xs rounded-full bg-gold/10 text-gold-dark dark:text-gold font-medium">
              {id.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
