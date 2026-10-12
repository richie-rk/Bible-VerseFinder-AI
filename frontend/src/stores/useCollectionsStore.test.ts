import { beforeEach, describe, expect, it, vi } from "vitest";

const STORE_KEY = "versefinder-collections";
const LEGACY_KEY = "favorites";

/** Loads the store module from scratch, as on a fresh page load. */
async function loadStore() {
  vi.resetModules();
  const { useCollectionsStore } = await import("./useCollectionsStore");
  return useCollectionsStore;
}

function persistedFavorites(): unknown {
  const raw = localStorage.getItem(STORE_KEY);
  return raw ? (JSON.parse(raw) as { state: { favorites: unknown } }).state.favorites : undefined;
}

describe("legacy favorites migration", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("moves favorites from the legacy key into the collections store", async () => {
    localStorage.setItem(LEGACY_KEY, JSON.stringify(["John_3:16", "Romans_8:28"]));

    const store = await loadStore();

    expect(store.getState().favorites).toEqual(["John_3:16", "Romans_8:28"]);
    expect(store.getState().isFavorite("Romans_8:28")).toBe(true);
    expect(persistedFavorites()).toEqual(["John_3:16", "Romans_8:28"]);
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it("merges with existing favorites without duplicates", async () => {
    localStorage.setItem(STORE_KEY, JSON.stringify({ state: { favorites: ["John_3:16"] }, version: 0 }));
    localStorage.setItem(LEGACY_KEY, JSON.stringify(["1_John_4:8", "John_3:16"]));

    const store = await loadStore();

    expect(store.getState().favorites).toEqual(["John_3:16", "1_John_4:8"]);
  });

  it("only runs once", async () => {
    localStorage.setItem(LEGACY_KEY, JSON.stringify(["John_3:16"]));
    const firstLoad = await loadStore();
    firstLoad.getState().toggleFavorite("John_3:16"); // the user un-favorites it

    const secondLoad = await loadStore();

    expect(secondLoad.getState().favorites).toEqual([]);
  });

  it("keeps only verse ID strings", async () => {
    localStorage.setItem(LEGACY_KEY, JSON.stringify(["John_3:16", 42, null, "", { id: "x" }]));

    const store = await loadStore();

    expect(store.getState().favorites).toEqual(["John_3:16"]);
  });

  it("drops unreadable legacy data", async () => {
    localStorage.setItem(LEGACY_KEY, "{not json");

    const store = await loadStore();

    expect(store.getState().favorites).toEqual([]);
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it("does nothing when there are no legacy favorites", async () => {
    localStorage.setItem(STORE_KEY, JSON.stringify({ state: { favorites: ["Jude_1:24"] }, version: 0 }));

    const store = await loadStore();

    expect(store.getState().favorites).toEqual(["Jude_1:24"]);
  });
});
