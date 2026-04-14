import { Sun, Moon, Monitor } from "lucide-react";
import { useUIStore } from "@/stores/useUIStore";
import { useSearchStore } from "@/stores/useSearchStore";
import type { SearchMode, AnalysisDepth } from "@/types/api";

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
          {(["semantic", "keyword", "hybrid"] as SearchMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setSearchMode(mode)}
              className={`pill-button capitalize ${
                searchMode === mode ? "pill-button-active" : "pill-button-inactive"
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </section>

      {/* Depth defaults */}
      <section className="mb-8">
        <h2 className="font-sans font-semibold text-sm uppercase tracking-wider text-muted-foreground mb-4">
          Default Search Depth
        </h2>
        <div className="flex gap-2">
          {(["quick", "balanced", "comprehensive"] as AnalysisDepth[]).map((d) => (
            <button
              key={d}
              onClick={() => setDepth(d)}
              className={`pill-button capitalize ${
                depth === d ? "pill-button-active" : "pill-button-inactive"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
