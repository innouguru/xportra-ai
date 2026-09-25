import { describe, expect, it } from "vitest";
import { historyKindLabel, readReference, referenceLabel } from "./history";

describe("history presentation helpers", () => {
  it("labels the recorded entry kinds without inventing new ones", () => {
    expect(historyKindLabel("workflow_created")).toBe("Workflow created");
    expect(historyKindLabel("shipment_bound")).toBe("Shipment bound");
    expect(historyKindLabel("evidence_supplied")).toBe("Evidence supplied");
    expect(historyKindLabel("analysis_completed")).toBe("Analysis completed");
    expect(historyKindLabel("final_package_ready")).toBe("Final package ready");
  });

  it("renders unknown kinds verbatim rather than guessing", () => {
    expect(historyKindLabel("some_future_kind")).toBe("some_future_kind");
  });

  it("expands reference labels for scanning only", () => {
    expect(referenceLabel("supply_position")).toBe("supply position");
    expect(referenceLabel("report_id")).toBe("report id");
  });

  it("reads only recorded label/value pairs", () => {
    expect(readReference({ label: "evidence_id", value: "e-1" })).toEqual({
      label: "evidence_id",
      value: "e-1",
    });
    expect(readReference({})).toEqual({ label: "", value: "" });
  });
});
