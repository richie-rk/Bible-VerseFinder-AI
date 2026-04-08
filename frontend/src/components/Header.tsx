import { Sun, Moon, BookOpen } from "lucide-react";
import { useAppState } from "@/hooks/useAppState";

export function Header() {
  const { darkMode, toggleDarkMode } = useAppState();

  return (
    <header
      className="sticky top-0 z-40 h-[60px] flex items-center justify-between px-4 md:px-6"
      style={{ background: "var(--gradient-primary)" }}
    >
      <div className="flex items-center gap-2">
        <BookOpen className="h-6 w-6 text-white" aria-hidden="true" />
        <h1 className="text-xl font-bold text-white">VerseFinder AI</h1>
      </div>

      <button
        onClick={toggleDarkMode}
        className="p-2 rounded-lg text-white hover:bg-white/10 transition-colors duration-200"
        aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
      >
        {darkMode ? (
          <Sun className="h-6 w-6" aria-hidden="true" />
        ) : (
          <Moon className="h-6 w-6" aria-hidden="true" />
        )}
      </button>
    </header>
  );
}
