import { fireEvent, render, screen } from "@testing-library/react";
import { ApprovalFeedbackPanel } from "../approval-feedback-panel";

describe("ApprovalFeedbackPanel", () => {
  it("renders the empty state when no approval exists", () => {
    render(
      <ApprovalFeedbackPanel
        approval={null}
        emptyDescription="Reject something first to capture reusable notes."
        emptyTitle="No review yet."
        title="Latest review"
      />,
    );

    expect(screen.getByText("No review yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Reject something first to capture reusable notes."),
    ).toBeInTheDocument();
  });

  it("shows approval feedback and applies it through the action callback", () => {
    const applyFeedback = vi.fn();

    render(
      <ApprovalFeedbackPanel
        approval={{
          id: "approval-1",
          user_id: "user-1",
          project_id: "project-1",
          target_type: "script",
          target_id: "script-1",
          stage: "script",
          decision: "rejected",
          feedback_notes: "Make the opening hook shorter and more concrete.",
          created_at: "2026-04-25T00:00:00.000Z",
        }}
        applyFeedbackLabel="Apply to notes"
        emptyDescription="Unused in this test."
        emptyTitle="Unused in this test."
        onApplyFeedback={applyFeedback}
        title="Latest rejected script feedback"
      />,
    );

    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(
      screen.getByText("Make the opening hook shorter and more concrete."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Apply to notes" }));

    expect(applyFeedback).toHaveBeenCalledWith(
      "Make the opening hook shorter and more concrete.",
    );
  });
});
