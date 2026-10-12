import { beforeEach, describe, expect, it, vi } from "vitest";
import { makeSearchResponse } from "@/test/fixtures";

const STORE_KEY = "versefinder-search-preferences";

/** Loads the store module from scratch, as on a fresh page load. */
async function loadStore() {
  vi.resetModules();
  const { useSearchStore } = await import("./useSearchStore");
  return useSearchStore;
}

beforeEach(() => {
  localStorage.clear();
});

describe("appendSearchResults", () => {
  it("adds the next page without repeating verses and keeps the notice", async () => {
    const store = await loadStore();
    store.getState().setSearchResults(
      makeSearchResponse(["John_3:16", "Romans_8:28"], { notice: "Showing keyword results." })
    );

    store.getState().appendSearchResults(
      makeSearchResponse(["Romans_8:28", "1_John_4:8"], { notice: null })
    );

    const results = store.getState().searchResults;
    expect(results?.results.map((verse) => verse.verse_id)).toEqual([
      "John_3:16",
      "Romans_8:28",
      "1_John_4:8",
    ]);
    expect(results?.notice).toBe("Showing keyword results.");
  });
});

describe("persisted search preferences", () => {
  it("saves only the default mode and depth", async () => {
    const store = await loadStore();

    store.getState().setSearchMode("keyword");
    store.getState().setDepth("comprehensive");
    store.getState().setSearchResults(makeSearchResponse(["John_3:16"]));
    store.getState().setError("boom");

    const saved = JSON.parse(localStorage.getItem(STORE_KEY) ?? "null") as { state: unknown };
    expect(saved.state).toEqual({ searchMode: "keyword", depth: "comprehensive" });
  });

  it("restores saved preferences on load", async () => {
    localStorage.setItem(
      STORE_KEY,
      JSON.stringify({ state: { searchMode: "semantic", depth: "quick" }, version: 0 })
    );

    const store = await loadStore();

    expect(store.getState()).toMatchObject({ searchMode: "semantic", depth: "quick" });
  });

  it("ignores invalid saved values", async () => {
    localStorage.setItem(
      STORE_KEY,
      JSON.stringify({ state: { searchMode: "telepathy", depth: 7 }, version: 0 })
    );

    const store = await loadStore();

    expect(store.getState()).toMatchObject({ searchMode: "hybrid", depth: "balanced" });
  });
});
