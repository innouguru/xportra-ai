import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import {
  ARTIFACT,
  CANDIDATE,
  SID,
  CID,
  backend,
  jobRow,
  renderAt,
} from "./regulatoryTestKit";

/**
 * The review forms follow the server-resolved staff grants. This only
 * spares a person a pointless 403; the server still authorizes every
 * decision, and unknown identity hides nothing.
 */

const identityState = vi.hoisted(() => ({
  value: { identity: null, status: "idle", error: null, refetch: () => undefined } as {
    identity: { staff_permissions: string[] } | null;
    status: string;
    error: null;
    refetch: () => void;
  },
}));

vi.mock("../../app/IdentityContext", () => ({
  useIdentity: () => identityState.value,
}));

function signedInAs(staffPermissions: string[]) {
  identityState.value = {
    identity: { staff_permissions: staffPermissions },
    status: "ready",
    error: null,
    refetch: () => undefined,
  };
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    backend({
      artifacts: [ARTIFACT],
      jobs: () => [jobRow({ status: "completed" })],
      candidates: [CANDIDATE],
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  identityState.value = { identity: null, status: "idle", error: null, refetch: () => undefined };
});

const reviewPath = `/regulatory/${SID}/candidates/${CID}`;

describe("candidate review follows the staff grants", () => {
  it("offers only the Stage A form to a Stage A verifier", async () => {
    signedInAs(["grant_manage", "stage_a_verify"]);
    renderAt(reviewPath);
    expect(await screen.findByRole("button", { name: "Record Stage A verification" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Record Stage B approval" })).toBeNull();
    expect(screen.getByText(/does not hold the Stage B approval grant/)).toBeTruthy();
    expect(screen.queryByText(/does not hold the Stage A verification grant/)).toBeNull();
  });

  it("offers only the Stage B form to a Stage B approver", async () => {
    signedInAs(["grant_manage", "stage_b_approve"]);
    renderAt(reviewPath);
    expect(await screen.findByRole("button", { name: "Record Stage B approval" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Record Stage A verification" })).toBeNull();
    expect(screen.getByText(/does not hold the Stage A verification grant/)).toBeTruthy();
  });

  it("still shows the recorded facts and history when neither form is offered", async () => {
    signedInAs(["grant_manage"]);
    renderAt(reviewPath);
    expect(
      await screen.findByText("Stage A — source traceability and wording verification"),
    ).toBeTruthy();
    expect(screen.getByText("Stage B — pilot-scope applicability approval")).toBeTruthy();
    expect(screen.getByText(CANDIDATE.requirement_text)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Record Stage A verification" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Record Stage B approval" })).toBeNull();
  });

  it("hides nothing while identity is unknown, leaving the server as the authority", async () => {
    identityState.value = { identity: null, status: "loading", error: null, refetch: () => undefined };
    renderAt(reviewPath);
    expect(await screen.findByRole("button", { name: "Record Stage A verification" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Record Stage B approval" })).toBeTruthy();
  });

  it("offers both forms to someone holding both grants", async () => {
    signedInAs(["grant_manage", "stage_a_verify", "stage_b_approve"]);
    renderAt(reviewPath);
    expect(await screen.findByRole("button", { name: "Record Stage A verification" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Record Stage B approval" })).toBeTruthy();
  });
});
