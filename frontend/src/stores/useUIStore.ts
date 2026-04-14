import { create } from "zustand";

interface UIState {
  darkMode: boolean;
  sidebarOpen: boolean;

  setDarkMode: (dark: boolean) => void;
  toggleDarkMode: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
}

const getInitialDarkMode = (): boolean => {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem("theme");
  if (stored) return stored === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
};

export const useUIStore = create<UIState>((set, get) => ({
  darkMode: getInitialDarkMode(),
  sidebarOpen: true,

  setDarkMode: (dark) => {
    localStorage.setItem("theme", dark ? "dark" : "light");
    document.documentElement.classList.toggle("dark", dark);
    set({ darkMode: dark });
  },

  toggleDarkMode: () => {
    get().setDarkMode(!get().darkMode);
  },

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));

// Initialize dark mode class on load
if (typeof window !== "undefined") {
  const dark = getInitialDarkMode();
  document.documentElement.classList.toggle("dark", dark);
}
