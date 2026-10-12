// @vitest-environment node
import { describe, expect, it } from "vitest";
import { selectSummaryVerses } from "./search";
import { makeSearchResponse } from "@/test/fixtures";

const verseIds = Array.from({ length: 25 }, (_, index) => `John_1:${index + 1}`);

describe("selectSummaryVerses", () => {
  it.each([
    ["quick", 7],
    ["balanced", 12],
    ["comprehensive", 20],
  ] as const)("sends the top verse IDs for %s depth", (depth, count) => {
    const searchResults = makeSearchResponse(verseIds, { query: "light" });

    const verses = selectSummaryVerses(searchResults, "light", depth);

    expect(verses).toEqual(verseIds.slice(0, count).map((verse_id) => ({ verse_id })));
  });

  it("sends every result when there are fewer than the depth allows", () => {
    const searchResults = makeSearchResponse(["John_3:16", "John_3:17"], { query: "love" });

    expect(selectSummaryVerses(searchResults, " love ", "comprehensive")).toEqual([
      { verse_id: "John_3:16" },
      { verse_id: "John_3:17" },
    ]);
  });

  it("returns undefined when the results are for another query", () => {
    const searchResults = makeSearchResponse(verseIds, { query: "light" });

    expect(selectSummaryVerses(searchResults, "darkness", "balanced")).toBeUndefined();
  });

  it("returns undefined without results", () => {
    expect(selectSummaryVerses(null, "light", "balanced")).toBeUndefined();
    expect(
      selectSummaryVerses(makeSearchResponse([], { query: "light" }), "light", "balanced")
    ).toBeUndefined();
  });
});
