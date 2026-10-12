import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { VerseCard } from "./VerseCard";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useCollectionsStore } from "@/stores/useCollectionsStore";
import { makeVerse } from "@/test/fixtures";

function renderCard(onClick = vi.fn()) {
  render(
    <TooltipProvider>
      <VerseCard verse={makeVerse("1_John_4:8")} onClick={onClick} />
    </TooltipProvider>
  );
  return onClick;
}

beforeEach(() => {
  localStorage.clear();
  useCollectionsStore.setState({ favorites: [] });
});

describe("VerseCard", () => {
  it("shows a readable reference", () => {
    renderCard();

    expect(screen.getByText("1 John 4:8")).toBeInTheDocument();
  });

  it("saves favorites to the collections store used by the Collections page", () => {
    const onClick = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "Add to favorites" }));

    expect(useCollectionsStore.getState().favorites).toEqual(["1_John_4:8"]);
    expect(screen.getByRole("button", { name: "Remove from favorites" })).toBeInTheDocument();
    expect(onClick).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Remove from favorites" }));

    expect(useCollectionsStore.getState().favorites).toEqual([]);
  });

  it("opens the verse with Enter on the card but not on its action buttons", () => {
    const onClick = renderCard();

    fireEvent.keyDown(screen.getByRole("button", { name: "Add to favorites" }), { key: "Enter" });
    expect(onClick).not.toHaveBeenCalled();

    fireEvent.keyDown(screen.getByRole("button", { name: /^1 John 4:8:/ }), { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
