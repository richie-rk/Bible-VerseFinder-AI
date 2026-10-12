import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import SearchResultsPage from "./SearchResultsPage";
import { useSearchStore } from "@/stores/useSearchStore";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { deferred, jsonResponse, makeSearchResponse } from "@/test/fixtures";
import { renderRoute } from "@/test/renderRoute";

const ROUTES = ["/search", "/search/:query"];

type FetchImpl = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function stubFetch(impl: FetchImpl) {
  const fetchMock = vi.fn(impl);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function searchParamsOf(input: RequestInfo | URL | undefined) {
  return new URL(String(input)).searchParams;
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
  useHistoryStore.setState({ history: [] });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SearchResultsPage", () => {
  it("shows a search box instead of an empty page when there is no query", async () => {
    const fetchMock = stubFetch(async (input) =>
      jsonResponse(makeSearchResponse(["Romans_5:5"], { query: searchParamsOf(input).get("query") ?? "" }))
    );
    const { router } = renderRoute(<SearchResultsPage />, ROUTES, "/search/");

    const input = screen.getByRole("textbox", { name: "Search the Bible" });
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { value: "hope?" } });
    fireEvent.submit(screen.getByRole("search"));

    expect(router.location()).toBe("/search/hope%3F");
    await screen.findByText("Text of Romans_5:5");
    expect(searchParamsOf(fetchMock.mock.calls[0]?.[0]).get("query")).toBe("hope?");
  });

  it("shows the backend's notice above the results", async () => {
    const notice = "The Old Testament isn't available yet; showing related New Testament verses.";
    stubFetch(async () =>
      jsonResponse(makeSearchResponse(["Hebrews_11:3"], { query: "Genesis 1:1", notice }))
    );

    renderRoute(<SearchResultsPage />, ROUTES, "/search/Genesis%201%3A1");

    expect(await screen.findByRole("status")).toHaveTextContent(notice);
    expect(screen.getByText("Text of Hebrews_11:3")).toBeInTheDocument();
  });

  it("handles a query containing % without crashing", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(makeSearchResponse(["John_3:16"], { query: "100% sure" }))
    );

    renderRoute(<SearchResultsPage />, ROUTES, "/search/100%25%20sure");

    await screen.findByText("Text of John_3:16");
    expect(searchParamsOf(fetchMock.mock.calls[0]?.[0]).get("query")).toBe("100% sure");
  });

  it("re-runs the search from the first page when the mode changes", async () => {
    const fetchMock = stubFetch(async (input) => {
      const mode = searchParamsOf(input).get("mode");
      const ids = mode === "keyword" ? ["Ephesians_2:8"] : ["Romans_3:24"];
      return jsonResponse(makeSearchResponse(ids, { query: "grace", mode: mode === "keyword" ? "keyword" : "hybrid" }));
    });
    renderRoute(<SearchResultsPage />, ROUTES, "/search/grace");
    await screen.findByText("Text of Romans_3:24");

    fireEvent.click(screen.getByRole("button", { name: /Keyword/ }));

    await screen.findByText("Text of Ephesians_2:8");
    expect(screen.queryByText("Text of Romans_3:24")).not.toBeInTheDocument();
    const lastParams = searchParamsOf(fetchMock.mock.calls[fetchMock.mock.calls.length - 1]?.[0]);
    expect(lastParams.get("mode")).toBe("keyword");
    expect(lastParams.get("offset")).toBe("0");
  });

  it("ignores a late response for a previous query and stays loading until the current one finishes", async () => {
    const pending = new Map<string, ReturnType<typeof deferred<Response>>>();
    const fetchMock = stubFetch((input) => {
      const query = searchParamsOf(input).get("query") ?? "";
      const response = deferred<Response>();
      pending.set(query, response);
      // Resolves when the test says so, even if the request was aborted.
      return response.promise;
    });
    const { router } = renderRoute(<SearchResultsPage />, ROUTES, "/search/love");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    act(() => {
      router.navigate("/search/grace");
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    // The old request finishes first: it must not show its results or end the loading state.
    await act(async () => {
      pending.get("love")?.resolve(jsonResponse(makeSearchResponse(["1_John_4:8"], { query: "love" })));
    });
    expect(screen.queryByText("Text of 1_John_4:8")).not.toBeInTheDocument();
    expect(useSearchStore.getState().isSearching).toBe(true);

    await act(async () => {
      pending.get("grace")?.resolve(jsonResponse(makeSearchResponse(["Ephesians_2:8"], { query: "grace" })));
    });

    expect(await screen.findByText("Text of Ephesians_2:8")).toBeInTheDocument();
    expect(screen.queryByText("Text of 1_John_4:8")).not.toBeInTheDocument();
    expect(useSearchStore.getState().isSearching).toBe(false);
    expect(useHistoryStore.getState().history.map((item) => item.query)).toEqual(["grace"]);
  });

  it("shows the backend's error message and can retry", async () => {
    const detail = "Semantic search is temporarily unavailable. Try keyword or hybrid mode.";
    let calls = 0;
    stubFetch(async () => {
      calls += 1;
      return calls === 1
        ? jsonResponse({ detail }, 503)
        : jsonResponse(makeSearchResponse(["John_1:5"], { query: "light" }));
    });
    renderRoute(<SearchResultsPage />, ROUTES, "/search/light");

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Text of John_1:5")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("offers the filters and the summarize action on small screens", async () => {
    stubFetch(async () => jsonResponse(makeSearchResponse(["John_3:16"], { query: "faith" })));
    const { router } = renderRoute(<SearchResultsPage />, ROUTES, "/search/faith");
    await screen.findByText("Text of John_3:16");

    const toggle = screen.getByRole("button", { name: "Filters" });
    const panel = document.getElementById("mobile-search-filters");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(panel).not.toBeVisible();

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(panel).toBeVisible();
    expect(panel).toHaveTextContent("Search Mode");
    expect(panel).toHaveTextContent("Summary Depth");

    // One summarize button in the desktop sidebar, one in the mobile toolbar.
    const summarizeButtons = screen.getAllByRole("button", { name: /Summarize with AI/ });
    expect(summarizeButtons).toHaveLength(2);
    fireEvent.click(summarizeButtons[1]!);
    expect(router.location()).toBe("/summary/faith");
  });
});
