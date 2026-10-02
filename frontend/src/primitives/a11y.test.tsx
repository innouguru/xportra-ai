import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useEscapeKey, useFocusRestore } from "./a11y";

function EscapeHarness({ onEscape }: { onEscape: () => void }) {
  useEscapeKey(onEscape);
  return <p>Open surface</p>;
}

function FocusHarness() {
  useFocusRestore();
  return <p>Temporary surface</p>;
}

describe("accessibility primitives", () => {
  it("invokes the handler on Escape and ignores other keys", () => {
    const onEscape = vi.fn();
    render(<EscapeHarness onEscape={onEscape} />);
    fireEvent.keyDown(document, { key: "Enter" });
    expect(onEscape).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it("restores focus to the previously focused element on unmount", () => {
    render(<button type="button">Trigger</button>);
    const trigger = screen.getByRole("button", { name: "Trigger" });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);
    const { unmount } = render(<FocusHarness />);
    unmount();
    expect(document.activeElement).toBe(trigger);
  });
});
