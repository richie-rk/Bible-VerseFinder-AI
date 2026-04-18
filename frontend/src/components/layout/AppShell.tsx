import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { Search, BookmarkIcon, Settings, Sun, Moon, Home, BookOpen, Library } from "lucide-react";
import { useUIStore } from "@/stores/useUIStore";

export default function AppShell() {
  const { darkMode, toggleDarkMode } = useUIStore();
  const location = useLocation();
  const navigate = useNavigate();

  // Reader page uses its own compact header
  const isReaderPage = location.pathname.startsWith("/read/");
  if (isReaderPage) return <Outlet />;

  return (
    <div className="min-h-screen bg-background">
      {/* Skip to content */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Top Navigation */}
      <header className="sticky top-0 z-40 bg-navy dark:bg-navy-deep">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 text-cream hover:text-white transition-colors">
            <BookOpen className="w-5 h-5 text-gold" />
            <span className="font-serif text-lg font-medium tracking-tight">
              Bible Verse Finder AI
            </span>
          </Link>

          {/* Right actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => navigate("/search/")}
              className="p-2 rounded-md text-cream/70 hover:text-cream hover:bg-white/10 transition-colors"
              aria-label="Search"
            >
              <Search className="w-5 h-5" />
            </button>
            <button
              onClick={() => navigate("/collections")}
              className="p-2 rounded-md text-cream/70 hover:text-cream hover:bg-white/10 transition-colors"
              aria-label="Collections"
            >
              <BookmarkIcon className="w-5 h-5" />
            </button>
            <button
              onClick={() => navigate("/settings")}
              className="p-2 rounded-md text-cream/70 hover:text-cream hover:bg-white/10 transition-colors"
              aria-label="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              onClick={toggleDarkMode}
              className="p-2 rounded-md text-cream/70 hover:text-cream hover:bg-white/10 transition-colors"
              aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
            >
              {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main id="main-content">
        <Outlet />
      </main>

      {/* Mobile Bottom Tab Bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface-lowest dark:bg-card border-t border-border">
        <div className="flex items-center justify-around h-14">
          <MobileTab to="/" icon={Home} label="Home" active={location.pathname === "/"} />
          <MobileTab to="/search/" icon={Search} label="Search" active={location.pathname.startsWith("/search")} />
          <MobileTab to="/collections" icon={Library} label="Library" active={location.pathname === "/collections"} />
          <MobileTab to="/settings" icon={Settings} label="Settings" active={location.pathname === "/settings"} />
        </div>
      </nav>

      {/* Spacer for mobile bottom nav */}
      <div className="md:hidden h-14" />
    </div>
  );
}

function MobileTab({
  to, icon: Icon, label, active,
}: {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      to={to}
      className={`flex flex-col items-center gap-0.5 px-3 py-1 text-xs transition-colors ${
        active ? "text-gold" : "text-muted-foreground"
      }`}
    >
      <Icon className="w-5 h-5" />
      <span>{label}</span>
    </Link>
  );
}
