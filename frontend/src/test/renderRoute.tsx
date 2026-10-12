import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import type { NavigateFunction } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";

export interface RouteTestHandle {
  /** Navigates like the app would (e.g. clicking a link elsewhere). */
  navigate: NavigateFunction;
  /** The current pathname + search. */
  location: () => string;
}

/** Renders `element` at `initialPath` inside a router; other paths render a placeholder. */
export function renderRoute(element: ReactElement, routePaths: string[], initialPath: string) {
  const handle: RouteTestHandle = {
    navigate: () => {
      throw new Error("Router not mounted");
    },
    location: () => "",
  };

  function RouterProbe() {
    const navigate = useNavigate();
    const location = useLocation();
    handle.navigate = navigate;
    handle.location = () => `${location.pathname}${location.search}`;
    return null;
  }

  const result = render(
    <TooltipProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <RouterProbe />
        <Routes>
          {routePaths.map((path) => (
            <Route key={path} path={path} element={element} />
          ))}
          <Route path="*" element={<p>Other page</p>} />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>
  );

  return { ...result, router: handle };
}
