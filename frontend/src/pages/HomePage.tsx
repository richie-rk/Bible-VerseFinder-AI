import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, BookOpen, ArrowRight } from "lucide-react";
import { useHistoryStore } from "@/stores/useHistoryStore";

const TOPIC_PILLS = [
  "grace", "forgiveness", "love", "fear",
  "hope", "faith", "wisdom", "prayer",
];

const VERSE_OF_THE_DAY = {
  text: "And we know that in all things God works for the good of those who love him, who have been called according to his purpose.",
  reference: "Romans 8:28",
  translation: "ESV",
};

export default function HomePage() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const { history } = useHistoryStore();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search/${encodeURIComponent(query.trim())}`);
    }
  };

  const handleTopicClick = (topic: string) => {
    navigate(`/search/${encodeURIComponent(topic)}`);
  };

  return (
    <div className="min-h-[calc(100vh-64px)]">
      {/* Hero Section */}
      <section className="relative py-16 md:py-24 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="font-serif text-4xl md:text-5xl lg:text-6xl font-medium text-navy dark:text-cream tracking-tight mb-4">
            Discover what Scripture says
          </h1>
          <p className="text-lg text-muted-foreground mb-10">
            AI-powered Bible verse search and study
          </p>

          {/* Search Bar */}
          <form onSubmit={handleSearch} className="relative max-w-2xl mx-auto">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search for a topic, verse, or question..."
                className="w-full pl-12 pr-32 py-4 rounded-lg bg-surface-lowest dark:bg-card text-foreground placeholder:text-muted-foreground text-base search-glow transition-shadow focus:outline-none"
                style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.06)" }}
              />
              <button
                type="submit"
                className="btn-scriptorium absolute right-2 top-1/2 -translate-y-1/2"
              >
                Search
              </button>
            </div>
          </form>
        </div>
      </section>

      {/* Verse of the Day */}
      <section className="max-w-2xl mx-auto px-4 mb-12">
        <div
          className="bg-surface-lowest dark:bg-card rounded-lg p-8 border-l-4 border-l-gold"
          style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.06)" }}
        >
          <p className="text-xs font-sans font-medium uppercase tracking-wider text-gold-dark dark:text-gold mb-4">
            Verse of the Day
          </p>
          <blockquote className="text-scripture text-xl md:text-2xl text-foreground italic mb-4">
            &ldquo;{VERSE_OF_THE_DAY.text}&rdquo;
          </blockquote>
          <div className="flex items-center justify-between">
            <p className="font-serif text-sm text-muted-foreground">
              &mdash; {VERSE_OF_THE_DAY.reference} {VERSE_OF_THE_DAY.translation}
            </p>
            <button
              onClick={() => navigate("/read/Romans/8?highlight=28")}
              className="flex items-center gap-1.5 text-sm font-medium text-burgundy-text dark:text-burgundy-dim hover:underline"
            >
              <BookOpen className="w-4 h-4" />
              Read Chapter
            </button>
          </div>
        </div>
      </section>

      {/* Topic Pills */}
      <section className="max-w-2xl mx-auto px-4 mb-12">
        <h2 className="font-sans text-sm font-medium uppercase tracking-wider text-muted-foreground mb-4">
          Try These
        </h2>
        <div className="flex flex-wrap gap-2">
          {TOPIC_PILLS.map((topic) => (
            <button
              key={topic}
              onClick={() => handleTopicClick(topic)}
              className="pill-button pill-button-inactive capitalize"
            >
              {topic}
            </button>
          ))}
        </div>
      </section>

      {/* Recent Searches */}
      {history.length > 0 && (
        <section className="max-w-2xl mx-auto px-4 pb-16">
          <h2 className="font-sans text-sm font-medium uppercase tracking-wider text-muted-foreground mb-4">
            Recent Searches
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {history.slice(0, 3).map((item) => (
              <button
                key={item.query}
                onClick={() => navigate(`/search/${encodeURIComponent(item.query)}`)}
                className="bg-surface-lowest dark:bg-card rounded-lg p-4 text-left transition-colors hover:bg-surface-highest dark:hover:bg-muted group"
                style={{ boxShadow: "0 12px 40px rgba(27, 28, 23, 0.04)" }}
              >
                <p className="font-sans text-sm font-medium text-foreground truncate mb-1">
                  {item.query}
                </p>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">
                    {formatTimeAgo(item.timestamp)}
                  </p>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function formatTimeAgo(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return "Just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
