import { create } from "zustand";

interface UIState {
  darkMode: boolean;

  setDarkMode: (dark: boolean) => void;
  toggleDarkMode: () => void;
}

const THEME_STORAGE_KEY = "theme";

// Storage access can throw (e.g. blocked site data), so it must never break app start-up.
function readStoredTheme(): string | null {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeTheme(dark: boolean): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, dark ? "dark" : "light");
  } catch {
    // Ignore storage errors; the theme still applies for this session.
  }
}

const getInitialDarkMode = (): boolean => {
  if (typeof window === "undefined") return false;
  const stored = readStoredTheme();
  if (stored === "dark" || stored === "light") return stored === "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
};

const initialDarkMode = getInitialDarkMode();

export const useUIStore = create<UIState>((set, get) => ({
  darkMode: initialDarkMode,

  setDarkMode: (dark) => {
    storeTheme(dark);
    document.documentElement.classList.toggle("dark", dark);
    set({ darkMode: dark });
  },

  toggleDarkMode: () => {
    get().setDarkMode(!get().darkMode);
  },
}));

// Initialize dark mode class on load
if (typeof document !== "undefined") {
  document.documentElement.classList.toggle("dark", initialDarkMode);
}
