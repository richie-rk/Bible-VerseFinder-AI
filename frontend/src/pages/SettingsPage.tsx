import { Sun, Moon } from "lucide-react";
import { useUIStore } from "@/stores/useUIStore";
import { useSearchStore } from "@/stores/useSearchStore";
import { DEPTH_VERSE_COUNT, SEARCH_MODES, SUMMARY_DEPTHS } from "@/lib/search";

export default function SettingsPage() {
  const { darkMode, setDarkMode } = useUIStore();
  const { searchMode, depth, setSearchMode, setDepth } = useSearchStore();

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="font-serif text-3xl font-medium text-foreground mb-2">Settings</h1>
      <p className="text-sm text-muted-foreground mb-8">Customize your study experience</p>

      {/* Theme */}
      <section className="mb-8">
        <h2 className="font-sans font-semibold text-sm uppercase tracking-wider text-muted-foreground mb-4">
          Appearance
        </h2>
        <div className="flex gap-3">
          {[
            { label: "Light", icon: Sun, value: false },
            { label: "Dark", icon: Moon, value: true },
          ].map(({ label, icon: Icon, value }) => (
            <button
              key={label}
              onClick={() => setDarkMode(value)}
              className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                darkMode === value
                  ? "bg-navy text-gold-light"
                  : "bg-surface-low dark:bg-card text-foreground hover:bg-surface-high"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* Search defaults */}
      <section className="mb-8">
        <h2 className="font-sans font-semibold text-sm uppercase tracking-wider text-muted-foreground mb-4">
          Default Search Mode
        </h2>
        <div className="flex gap-2">
          {SEARCH_MODES.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setSearchMode(value)}
              aria-pressed={searchMode === value}
              className={`pill-button ${
                searchMode === value ? "pill-button-active" : "pill-button-inactive"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* Depth defaults */}
      <section className="mb-8">
        <h2 className="font-sans font-semibold text-sm uppercase tracking-wider text-muted-foreground mb-1">
          Default Summary Depth
        </h2>
        <p className="text-sm text-muted-foreground mb-4">
          How many top verses an AI summary analyzes. It doesn&rsquo;t change search results.
        </p>
        <div className="flex flex-wrap gap-2">
          {SUMMARY_DEPTHS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setDepth(value)}
              aria-pressed={depth === value}
              className={`pill-button ${
                depth === value ? "pill-button-active" : "pill-button-inactive"
              }`}
            >
              {label} &middot; {DEPTH_VERSE_COUNT[value]} verses
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
