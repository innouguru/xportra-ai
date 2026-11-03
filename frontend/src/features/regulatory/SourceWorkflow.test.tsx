import { afterEach, describe, expect, it, vi } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ARTIFACT,
  CANDIDATE,
  CID,
  SID,
  backend,
  jobRow,
  renderAt,
} from "./regulatoryTestKit";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const tab = (name: string) => screen.getByRole("link", { name: new RegExp(`^${name}`) });

describe("source page workflow", () => {
  it("shows the stepper and one clear next step for a freshly registered source", async () => {
    vi.stubGlobal("fetch", backend({
      artifacts: [],
      jobs: () => [jobRow({ artifact_id: null, status: "pending" })],
      candidates: [],
    }));
    renderAt(`/regulatory/${SID}/documents`);

    const progress = await screen.findByLabelText("Source progress");
    for (const label of ["Registered", "Document", "Extraction", "Review"]) {
      expect(within(progress).getByText(label)).toBeTruthy();
    }
    // Document is the current step.
    const current = progress.querySelector('[aria-current="step"]');
    expect(current?.textContent).toContain("Document");
    // Exactly one next step, and nothing about publication.
    const next = screen.getByLabelText("Next step");
    expect(next.textContent).toContain("Next: upload the original document");
    expect(progress.textContent).not.toMatch(/publi/i);
    expect(next.textContent).not.toMatch(/publi/i);
  });

  it("counts only real documents and ingestion attempts in the tabs", async () => {
    vi.stubGlobal("fetch", backend({
      artifacts: [],
      jobs: () => [jobRow({ artifact_id: null, status: "pending" })],
      candidates: [],
    }));
    renderAt(`/regulatory/${SID}/documents`);
    await screen.findByLabelText("Source progress");
    expect(tab("Documents").textContent).toBe("Documents0");
    // The registration placeholder is not counted as an ingestion attempt.
    expect(tab("Ingestion").textContent).toBe("Ingestion0");
    expect(tab("Candidates").textContent).toBe("Candidates0");
    expect(tab("Documents").getAttribute("aria-current")).toBe("page");
  });

  it("labels the registration placeholder instead of presenting it as an attempt", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", backend({
      artifacts: [],
      jobs: () => [jobRow({ artifact_id: null, status: "pending" })],
      candidates: [],
    }));
    renderAt(`/regulatory/${SID}/documents`);
    await screen.findByLabelText("Source progress");
    await user.click(tab("Ingestion"));
    expect(
      await screen.findByText(/Registration record — no document attached yet/),
    ).toBeTruthy();
    // No retry is offered for something that never ran.
    expect(screen.queryByRole("button", { name: "Retry failed job" })).toBeNull();
  });

  it("points at the candidates once extraction is complete", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", backend({
      artifacts: [ARTIFACT],
      jobs: () => [jobRow({ status: "completed" })],
      candidates: [CANDIDATE],
    }));
    renderAt(`/regulatory/${SID}/documents`);
    const next = await screen.findByLabelText("Next step");
    expect(next.textContent).toContain("Next: review 1 candidate");
    await user.click(within(next).getByRole("link", { name: "Review candidates" }));
    expect(await screen.findByText("Candidate requirements")).toBeTruthy();
    expect(tab("Candidates").getAttribute("aria-current")).toBe("page");
  });

  it("refreshes quietly while a job is running and stops once it finishes", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    let status = "processing";
    const stub = backend({
      artifacts: [ARTIFACT],
      jobs: () => [jobRow({ status })],
      candidates: [],
    });
    vi.stubGlobal("fetch", stub);
    renderAt(`/regulatory/${SID}/documents`);
    const next = await screen.findByLabelText("Next step");
    expect(next.textContent).toContain("Ingestion is running");

    const jobReads = () =>
      stub.mock.calls.filter(([url]) => String(url).endsWith("/ingestion-jobs")).length;
    const before = jobReads();

    status = "completed";
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    await waitFor(() => expect(jobReads()).toBeGreaterThan(before));
    // The page updated in place, without a loading flash.
    await waitFor(() =>
      expect(screen.getByLabelText("Next step").textContent).toContain(
        "No candidates were extracted",
      ),
    );
    expect(screen.queryByText("Loading source…")).toBeNull();

    // Finished: no further polling.
    const settled = jobReads();
    await act(async () => {
      vi.advanceTimersByTime(20000);
    });
    expect(jobReads()).toBe(settled);
  });

  it("opens the review of a candidate as its own page with a way back", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", backend({
      artifacts: [ARTIFACT],
      jobs: () => [jobRow({ status: "completed" })],
      candidates: [CANDIDATE],
    }));
    renderAt(`/regulatory/${SID}/candidates/${CID}`);
    expect(
      await screen.findByText("Stage A — source traceability and wording verification"),
    ).toBeTruthy();
    expect(screen.getByText("Stage B — pilot-scope applicability approval")).toBeTruthy();
    // The real Stage B rules are stated up front.
    expect(
      screen.getByText(/Stage B requires a verified Stage A decision, and the Stage B reviewer must be a different person/),
    ).toBeTruthy();
    // Both decisions stay distinct, separately recorded actions.
    expect(screen.getByRole("button", { name: "Record Stage A verification" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Record Stage B approval" })).toBeTruthy();
    // No publication or exporter-applicability control exists here.
    expect(screen.queryByText(/Mark as published/i)).toBeNull();
    expect(screen.queryByText(/Publish requirement/i)).toBeNull();

    await user.click(screen.getByRole("link", { name: "Back to candidates" }));
    expect(await screen.findByText("Candidate requirements")).toBeTruthy();
  });

  it("offers no next-step link to the tab the person is already on", async () => {
    vi.stubGlobal("fetch", backend({
      artifacts: [],
      jobs: () => [jobRow({ artifact_id: null, status: "pending" })],
      candidates: [],
    }));
    renderAt(`/regulatory/${SID}/documents`);
    const next = await screen.findByLabelText("Next step");
    expect(next.textContent).toContain("Next: upload the original document");
    // The upload form is right below; a second "Upload document" control
    // in the card would only duplicate it.
    expect(within(next).queryByRole("link")).toBeNull();
    expect(screen.getAllByRole("button", { name: "Upload document" })).toHaveLength(1);
  });

  it("links the next step from any other tab", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", backend({
      artifacts: [],
      jobs: () => [jobRow({ artifact_id: null, status: "pending" })],
      candidates: [],
    }));
    renderAt(`/regulatory/${SID}/details`);
    const next = await screen.findByLabelText("Next step");
    await user.click(within(next).getByRole("link", { name: "Upload document" }));
    expect(
      await screen.findByRole("heading", { name: "Upload original regulatory document" }),
    ).toBeTruthy();
  });

  it("sends an unknown staff path back to the source list", async () => {
    vi.stubGlobal("fetch", backend({ artifacts: [], jobs: () => [], candidates: [] }));
    renderAt("/regulatory/some/unknown/path/here");
    // The list page's own intro is what proves we landed there.
    expect(await screen.findByText("Regulatory administration")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Register source" })).toBeTruthy();
    expect(screen.queryByLabelText("Source progress")).toBeNull();
  });
});
