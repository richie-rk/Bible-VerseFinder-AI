import { forwardRef, useState, useCallback } from "react";
import { Search, X } from "lucide-react";
import { useSearchHistory } from "@/hooks/useSearchHistory";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  onSelectHistory?: (query: string) => void;
  disabled?: boolean;
}

export const SearchBar = forwardRef<HTMLInputElement, SearchBarProps>(
  function SearchBar(
    { value, onChange, onSearch, onSelectHistory, disabled },
    ref
  ) {
    const [isFocused, setIsFocused] = useState(false);
    const { history, clearHistory } = useSearchHistory();

    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !disabled) {
          onSearch();
        }
      },
      [onSearch, disabled]
    );

    const handleClear = useCallback(() => {
      onChange("");
    }, [onChange]);

    const handleSelectHistory = useCallback(
      (query: string) => {
        onChange(query);
        onSelectHistory?.(query);
        setIsFocused(false);
      },
      [onChange, onSelectHistory]
    );

    const showHistory = isFocused && !value && history.length > 0;

    return (
      <div className="relative w-full max-w-[700px] mx-auto">
        <div className="relative">
          <Search
            className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            ref={ref}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setTimeout(() => setIsFocused(false), 150)}
            placeholder="Ask about any Bible topic... (e.g., 'What does the Bible say about grace?')"
            disabled={disabled}
            className="w-full h-[52px] pl-11 pr-11 text-base rounded-xl border-2 border-primary bg-card text-foreground placeholder:text-muted-foreground search-glow transition-all duration-200 disabled:opacity-50"
            aria-label="Search Bible topics"
          />
          {value && (
            <button
              onClick={handleClear}
              className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-muted transition-colors"
              aria-label="Clear search"
            >
              <X className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            </button>
          )}
        </div>

        {/* Search History Dropdown */}
        {showHistory && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-border">
              <span className="text-sm font-medium text-muted-foreground">
                Recent Searches
              </span>
              <button
                onClick={clearHistory}
                className="text-xs text-primary hover:underline"
              >
                Clear
              </button>
            </div>
            <ul className="max-h-[200px] overflow-y-auto">
              {history.map((item) => (
                <li key={item.timestamp}>
                  <button
                    onClick={() => handleSelectHistory(item.query)}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-muted transition-colors flex items-center gap-2"
                  >
                    <Search className="h-3 w-3 text-muted-foreground" />
                    <span className="truncate">{item.query}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }
);
