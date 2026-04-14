import { useState } from "react";
import { Search } from "lucide-react";

interface SearchBarProps {
  initialQuery?: string;
  onSearch: (query: string) => void;
  compact?: boolean;
}

export default function SearchBar({ initialQuery = "", onSearch, compact }: SearchBarProps) {
  const [query, setQuery] = useState(initialQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for a topic, verse, or question..."
        className={`w-full pl-10 pr-4 bg-surface-lowest dark:bg-card text-foreground placeholder:text-muted-foreground rounded-lg search-glow transition-shadow focus:outline-none ${
          compact ? "py-2 text-sm" : "py-3 text-base"
        }`}
      />
    </form>
  );
}
