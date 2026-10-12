import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import ReaderPage from "./ReaderPage";
import { deferred, jsonResponse, makeChapterResponse } from "@/test/fixtures";
import { renderRoute } from "@/test/renderRoute";
import { useCollectionsStore } from "@/stores/useCollectionsStore";

const ROUTES = ["/read/:book/:chapter"];

type FetchImpl = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function stubFetch(impl: FetchImpl) {
  const fetchMock = vi.fn(impl);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

// Each test uses a different book/chapter because lib/api caches chapters per module.
describe("ReaderPage", () => {
  it("disables Next on the book's last chapter", async () => {
    stubFetch(async () => jsonResponse(makeChapterResponse("Jude", 1, { total_chapters: 1 })));

    renderRoute(<ReaderPage />, ROUTES, "/read/Jude/1");

    expect(await screen.findByRole("heading", { name: "Jude 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next chapter" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous chapter" })).toBeDisabled();
  });

  it("uses the canonical book name and enables Next when more chapters follow", async () => {
    stubFetch(async () => jsonResponse(makeChapterResponse("1 John", 2, { total_chapters: 5 })));
    const { router } = renderRoute(<ReaderPage />, ROUTES, "/read/1_john/2");

    expect(await screen.findByRole("heading", { name: "1 John 2" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next chapter" }));

    expect(router.location()).toBe("/read/1%20John/3");
  });

  it("reports an invalid chapter instead of loading forever", () => {
    const fetchMock = stubFetch(async () => jsonResponse(makeChapterResponse("John", 1)));

    renderRoute(<ReaderPage />, ROUTES, "/read/John/abc");

    expect(screen.getByRole("alert")).toHaveTextContent("That chapter reference isn't valid.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("hides the previous chapter while the next one loads and when it fails", async () => {
    const next = deferred<Response>();
    stubFetch((input) =>
      String(input).endsWith("/chapters/Mark/16")
        ? Promise.resolve(jsonResponse(makeChapterResponse("Mark", 16, { total_chapters: 17 })))
        : next.promise
    );
    renderRoute(<ReaderPage />, ROUTES, "/read/Mark/16");
    expect(await screen.findByRole("heading", { name: "Mark 16" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next chapter" }));

    expect(screen.queryByRole("heading", { name: "Mark 16" })).not.toBeInTheDocument();
    expect(screen.queryByText("Mark 16:1 text")).not.toBeInTheDocument();

    await act(async () => {
      next.resolve(jsonResponse({ detail: "Chapter not found: Mark 17" }, 404));
    });

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Chapter not found: Mark 17")
    );
    expect(screen.queryByText("Mark 16:1 text")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next chapter" })).toBeDisabled();
  });

  it("shows a verse's favorite button after a tap and toggles the favorite", async () => {
    useCollectionsStore.setState({ favorites: [] });
    stubFetch(async () => jsonResponse(makeChapterResponse("Titus", 2, { total_chapters: 3 })));
    renderRoute(<ReaderPage />, ROUTES, "/read/Titus/2");
    expect(await screen.findByRole("heading", { name: "Titus 2" })).toBeInTheDocument();

    // jsdom has no Tailwind CSS, so check the class that hides the actions until hover or tap.
    const actions = () => screen.getByRole("button", { name: "Favorite Titus 2:1" }).parentElement;
    expect(actions()).toHaveClass("hidden");

    fireEvent.click(screen.getByText("Titus 2:1 text"));
    expect(actions()).toHaveClass("inline-flex");
    expect(actions()).not.toHaveClass("hidden");

    const favorite = screen.getByRole("button", { name: "Favorite Titus 2:1" });
    expect(favorite).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(favorite);
    expect(useCollectionsStore.getState().favorites).toContain("Titus_2:1");
    expect(screen.getByRole("button", { name: "Favorite Titus 2:1" })).toHaveAttribute("aria-pressed", "true");
    // The button click doesn't bubble up and close the actions again.
    expect(actions()).toHaveClass("inline-flex");
  });

  it("opens a verse's actions from the keyboard", async () => {
    stubFetch(async () => jsonResponse(makeChapterResponse("Philemon", 1, { total_chapters: 1 })));
    renderRoute(<ReaderPage />, ROUTES, "/read/Philemon/1");
    expect(await screen.findByRole("heading", { name: "Philemon 1" })).toBeInTheDocument();

    fireEvent.keyDown(screen.getByText("Philemon 1:2 text"), { key: "Enter" });
    expect(screen.getByRole("button", { name: "Favorite Philemon 1:2" }).parentElement).toHaveClass("inline-flex");
  });
});
