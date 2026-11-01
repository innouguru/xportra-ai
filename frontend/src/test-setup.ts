// Minimal sessionStorage mock for vitest/jsdom compatibility.
const sessionMock = {
  _store: {} as Record<string, string>,
  getItem(key: string) { return this._store[key] ?? null; },
  setItem(key: string, value: string) { this._store[key] = value; },
  removeItem(key: string) { delete this._store[key]; },
  clear() { this._store = {}; },
};
Object.defineProperty(global, "sessionStorage", { value: sessionMock, writable: true });
Object.defineProperty(globalThis, "sessionStorage", { value: sessionMock, writable: true });

import "@testing-library/jest-dom/vitest";
