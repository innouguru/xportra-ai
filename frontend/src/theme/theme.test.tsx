import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { ThemeControl, ThemeProvider, useTheme } from "./theme";

function probe() {
  let seen: ReturnType<typeof useTheme> | null = null;
  function Probe() {
    seen = useTheme();
    return null;
  }
  render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  );
  return () => {
    if (seen === null) {
      throw new Error("theme probe did not render");
    }
    return seen;
  };
}

function stubMatchMedia(matches: boolean) {
  window.matchMedia = ((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  vi.unstubAllGlobals();
});

describe("theme infrastructure", () => {
  it("defaults to the dark brand experience with no stored preference", () => {
    stubMatchMedia(false);
    const read = probe();
    expect(read().resolved).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("respects the system preference when nothing is stored", () => {
    stubMatchMedia(true);
    const read = probe();
    expect(read().mode).toBe("system");
    expect(read().resolved).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("restores the stored preference on startup", () => {
    stubMatchMedia(true);
    window.localStorage.setItem("xportra.theme.mode.v1", "dark");
    const read = probe();
    expect(read().mode).toBe("dark");
    expect(read().resolved).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("persists explicit choices and applies them to the document", () => {
    stubMatchMedia(false);
    const read = probe();
    act(() => {
      read().setMode("light");
    });
    expect(read().resolved).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("xportra.theme.mode.v1")).toBe("light");
  });

  it("falls back safely outside a provider", () => {
    function Outside() {
      const { resolved } = useTheme();
      return <p>{resolved}</p>;
    }
    render(<Outside />);
    expect(screen.getByText("dark")).toBeInTheDocument();
  });

  it("exposes an accessible theme selector that switches modes", () => {
    stubMatchMedia(false);
    render(
      <ThemeProvider>
        <ThemeControl />
      </ThemeProvider>,
    );
    const group = screen.getByRole("group", { name: "Theme" });
    expect(group).toBeInTheDocument();
    for (const name of ["Light", "Dark", "System"]) {
      expect(screen.getByRole("radio", { name })).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("radio", { name: "Light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(screen.getByRole("radio", { name: "Light" })).toBeChecked();
  });
});
