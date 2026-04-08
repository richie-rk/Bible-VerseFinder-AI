import { useRef, useCallback, useEffect } from "react";
import { Header } from "@/components/Header";
import { SearchBar } from "@/components/SearchBar";
import { ModeSelector } from "@/components/ModeSelector";
import { ActionButtons } from "@/components/ActionButtons";
import { DepthSelector } from "@/components/DepthSelector";
import { EmptyState } from "@/components/EmptyState";
import { ExploreView } from "@/components/ExploreView";
import { SummarizeView } from "@/components/SummarizeView";
import { ChapterModal } from "@/components/ChapterModal";
import { ErrorBanner } from "@/components/ErrorBanner";
import { useAppState } from "@/hooks/useAppState";
import { useSearch } from "@/hooks/useSearch";
import { useSummarize } from "@/hooks/useSummarize";
import { useChapter } from "@/hooks/useChapter";
import { useSearchHistory } from "@/hooks/useSearchHistory";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

export default function Index() {
  const searchInputRef = useRef<HTMLInputElement>(null);

  const {
    searchQuery,
    searchMode,
    activeView,
    depth,
    searchResults,
    summarizeResults,
    isSearching,
    isSummarizing,
    error,
    chapterModal,
    setSearchQuery,
    setSearchMode,
    setActiveView,
    setDepth,
    setError,
  } = useAppState();

  const { search, loadMore } = useSearch();
  const { summarize } = useSummarize();
  const { chapterData, isLoading: isLoadingChapter, error: chapterError, fetchChapter, close: closeChapter } = useChapter();
  const { addToHistory } = useSearchHistory();

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onFocusSearch: () => searchInputRef.current?.focus(),
  });

  // Handle search action
  const handleExplore = useCallback(() => {
    if (!searchQuery.trim()) return;
    addToHistory(searchQuery);
    setActiveView("explore");
    search();
  }, [searchQuery, addToHistory, setActiveView, search]);

  // Handle summarize action
  const handleSummarize = useCallback(() => {
    if (!searchQuery.trim()) return;
    addToHistory(searchQuery);
    setActiveView("summarize");
    summarize();
  }, [searchQuery, addToHistory, setActiveView, summarize]);

  // Handle example chip click
  const handleExampleClick = useCallback(
    (query: string) => {
      setSearchQuery(query);
      addToHistory(query);
      setActiveView("explore");
      search(query);
    },
    [setSearchQuery, addToHistory, setActiveView, search]
  );

  // Handle history select
  const handleHistorySelect = useCallback(
    (query: string) => {
      setActiveView("explore");
      search(query);
    },
    [setActiveView, search]
  );

  // Handle verse click
  const handleVerseClick = useCallback(
    (verseId: string) => {
      fetchChapter(verseId);
    },
    [fetchChapter]
  );

  // Retry handler
  const handleRetry = useCallback(() => {
    setError(null);
    if (activeView === "explore") {
      search();
    } else {
      summarize();
    }
  }, [activeView, search, summarize, setError]);

  // Determine if we should show results
  const hasResults = activeView === "explore" ? !!searchResults : !!summarizeResults;
  const showEmptyState = !hasResults && !isSearching && !isSummarizing && !error;

  return (
    <div className="min-h-screen bg-background">
      {/* Skip link for accessibility */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <Header />

      <main id="main-content" className="container max-w-[800px] mx-auto px-4 py-6">
        {/* Search Section */}
        <section className="space-y-4 mb-6">
          <SearchBar
            ref={searchInputRef}
            value={searchQuery}
            onChange={setSearchQuery}
            onSearch={handleExplore}
            onSelectHistory={handleHistorySelect}
            disabled={isSearching || isSummarizing}
          />

          <ModeSelector
            value={searchMode}
            onChange={setSearchMode}
            disabled={isSearching || isSummarizing}
          />

          <ActionButtons
            activeView={activeView}
            onSummarize={handleSummarize}
            onExplore={handleExplore}
            isSummarizing={isSummarizing}
            isSearching={isSearching}
          />

          {/* Depth selector - only show for summarize view */}
          {activeView === "summarize" && (
            <div className="flex justify-center">
              <DepthSelector
                value={depth}
                onChange={setDepth}
                disabled={isSummarizing}
              />
            </div>
          )}
        </section>

        {/* Error Banner */}
        {error && (
          <ErrorBanner
            message={error}
            onRetry={handleRetry}
            isRetrying={isSearching || isSummarizing}
          />
        )}

        {/* Results Section */}
        <section>
          {showEmptyState && <EmptyState onExampleClick={handleExampleClick} />}

          {activeView === "explore" && (searchResults || isSearching) && (
            <ExploreView
              results={searchResults}
              isLoading={isSearching}
              onLoadMore={loadMore}
              onVerseClick={handleVerseClick}
              query={searchQuery}
            />
          )}

          {activeView === "summarize" && (summarizeResults || isSummarizing) && (
            <SummarizeView
              results={summarizeResults}
              isLoading={isSummarizing}
              onCitationClick={handleVerseClick}
            />
          )}
        </section>
      </main>

      {/* Chapter Modal */}
      {chapterModal && (
        <ChapterModal
          isOpen={chapterModal.open}
          book={chapterModal.book}
          chapter={chapterModal.chapter}
          highlightVerse={chapterModal.highlightVerse}
          chapterData={chapterData}
          isLoading={isLoadingChapter}
          error={chapterError}
          onClose={closeChapter}
        />
      )}
    </div>
  );
}
