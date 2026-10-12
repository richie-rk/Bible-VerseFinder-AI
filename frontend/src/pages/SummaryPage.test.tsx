import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import SummaryPage from "./SummaryPage";
import { Toaster } from "@/components/ui/toaster";
import { useSearchStore } from "@/stores/useSearchStore";
import { useSummaryStore } from "@/stores/useSummaryStore";
import { jsonResponse, makeSearchResponse, makeSummaryResponse } from "@/test/fixtures";
import { renderRoute } from "@/test/renderRoute";

const ROUTES = ["/summary/:query"];

type FetchImpl = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function stubFetch(impl: FetchImpl) {
  const fetchMock = vi.fn(impl);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function requestBody(fetchMock: ReturnType<typeof stubFetch>, call = 0): Record<string, unknown> {
  return JSON.parse(String(fetchMock.mock.calls[call]?.[1]?.body)) as Record<string, unknown>;
}

beforeEach(() => {
  localStorage.clear();
  useSearchStore.setState({
    searchMode: "hybrid",
    depth: "balanced",
    searchResults: null,
    isSearching: false,
    error: null,
  });
  useSummaryStore.setState({ summarizeResults: null, isSummarizing: false, error: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SummaryPage", () => {
  it("shows the backend's error message and can retry", async () => {
    const detail = "AI summarization is temporarily unavailable. Please try again later.";
    let calls = 0;
    stubFetch(async () => {
      calls += 1;
      return calls === 1 ? jsonResponse({ detail }, 503) : jsonResponse(makeSummaryResponse());
    });

    renderRoute(<SummaryPage />, ROUTES, "/summary/grace");

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
    // The error belongs to the summary, not to the search results page.
    expect(useSearchStore.getState().error).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Grace is God's unearned favor [Ephesians_2:8].")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("summarizes the verses from the matching search results, limited by depth", async () => {
    const verseIds = Array.from({ length: 15 }, (_, index) => `Romans_${index + 1}:1`);
    useSearchStore.setState({
      depth: "quick",
      searchResults: makeSearchResponse(verseIds, { query: "grace" }),
    });
    const fetchMock = stubFetch(async () => jsonResponse(makeSummaryResponse({ depth: "quick" })));

    renderRoute(<SummaryPage />, ROUTES, "/summary/grace");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock)).toEqual({
      query: "grace",
      depth: "quick",
      mode: "hybrid",
      verses: verseIds.slice(0, 7).map((verse_id) => ({ verse_id })),
    });
  });

  it("lets the backend search when the stored results are for another query", async () => {
    useSearchStore.setState({ searchResults: makeSearchResponse(["John_3:16"], { query: "love" }) });
    const fetchMock = stubFetch(async () => jsonResponse(makeSummaryResponse()));

    renderRoute(<SummaryPage />, ROUTES, "/summary/grace");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock)).not.toHaveProperty("verses");
  });

  it("keeps special characters in the query and encodes the breadcrumb link", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(makeSummaryResponse()));

    renderRoute(<SummaryPage />, ROUTES, "/summary/100%25%20grace%3F");

    expect(await screen.findByRole("link", { name: "Search" })).toHaveAttribute(
      "href",
      "/search/100%25%20grace%3F"
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock).query).toBe("100% grace?");
  });

  it("tells the user when copying fails", async () => {
    stubFetch(async () => jsonResponse(makeSummaryResponse()));
    const writeText = vi.fn().mockRejectedValue(new Error("Clipboard blocked"));
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    try {
      renderRoute(
        <>
          <SummaryPage />
          <Toaster />
        </>,
        ROUTES,
        "/summary/grace"
      );
      fireEvent.click(await screen.findByRole("button", { name: /Copy Summary/ }));

      expect(await screen.findByText("Couldn't copy the summary")).toBeInTheDocument();
      expect(writeText).toHaveBeenCalledWith("Grace is God's unearned favor [Ephesians_2:8].");
    } finally {
      Reflect.deleteProperty(navigator, "clipboard");
    }
  });
});
