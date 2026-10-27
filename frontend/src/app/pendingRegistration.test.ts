import { afterEach, describe, expect, it } from "vitest";
import {
  clearPendingRegistration,
  readPendingRegistration,
  savePendingRegistration,
} from "./pendingRegistration";

afterEach(() => window.localStorage.clear());

describe("pending organization registration", () => {
  it("persists only validated profile fields across tabs (localStorage)", () => {
    savePendingRegistration({
      email: "owner@example.com",
      organizationName: "Rift Valley Produce",
      organizationType: "exporter",
      countryCode: "ke",
      region: null,
      contactName: null,
      password: "must-not-persist",
      access_token: "must-not-persist",
    } as never);
    const raw = window.localStorage.getItem("xportra.pending-registration.v1");
    expect(raw).toContain('"countryCode":"KE"');
    expect(raw).not.toMatch(/password|token|tenant|role/i);
    expect(readPendingRegistration()).toEqual({
      email: "owner@example.com",
      organizationName: "Rift Valley Produce",
      organizationType: "exporter",
      countryCode: "KE",
      region: null,
      contactName: null,
    });
  });

  it("rejects and clears malformed profile data without throwing", () => {
    window.localStorage.setItem("xportra.pending-registration.v1", "{bad json");
    expect(readPendingRegistration()).toBeNull();
    expect(window.localStorage.getItem("xportra.pending-registration.v1")).toBeNull();
    expect(() => clearPendingRegistration()).not.toThrow();
  });
});
