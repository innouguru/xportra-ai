import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { AnalysisProvider } from "../../app/AnalysisContext";
import { AssessmentProvider } from "../../app/AssessmentContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ConversationProvider } from "../conversation/ConversationContext";
import { DocumentsPage } from "./DocumentsPage";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "evidence_pending",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPage() {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(RECORD));
  render(
    <MemoryRouter initialEntries={["/workspace/documents"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <ConversationProvider>
            <AnalysisProvider>
              <AssessmentProvider>
                <Routes>
                  <Route path="/workspace/documents" element={<DocumentsPage />} />
                </Routes>
              </AssessmentProvider>
            </AnalysisProvider>
          </ConversationProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("DocumentsPage", () => {
  it("asks for a shipment when no workflow record exists", () => {
    sessionStorage.clear();
    render(
      <MemoryRouter initialEntries={["/workspace/documents"]}>
        <AuthProvider>
          <WorkflowProvider>
            <ConversationProvider>
              <AnalysisProvider>
                <AssessmentProvider>
                  <Routes>
                    <Route path="/workspace/documents" element={<DocumentsPage />} />
                  </Routes>
                </AssessmentProvider>
              </AnalysisProvider>
            </ConversationProvider>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: "No active shipment" }),
    ).toBeInTheDocument();
  });

  it("presents documents, needed, and requested as tabs", () => {
    renderPage();
    const tablist = screen.getByRole("tablist", { name: "Document areas" });
    expect(tablist).toBeInTheDocument();
    for (const name of ["Documents", "Needed", "Requested"]) {
      expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    }
    // Documents tab is selected first and shows the upload workspace.
    expect(screen.getByRole("tab", { name: "Documents" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("heading", { name: "Upload evidence" }),
    ).toBeInTheDocument();
  });

  it("switches areas without losing the upload capability", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Needed" }));
    expect(screen.getByRole("tab", { name: "Needed" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("heading", { name: "Evidence coverage" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Requested" }));
    expect(
      screen.getByRole("heading", { name: "Why additional evidence was requested" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Documents" }));
    expect(
      screen.getByRole("heading", { name: "Upload evidence" }),
    ).toBeInTheDocument();
  });

  it("moves between tabs with arrow keys", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Needed" }));
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Requested" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(document.activeElement?.getAttribute("role")).toBe("tab");
  });
});
