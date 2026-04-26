import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider, useToast } from "../toast-provider";

function ToastTrigger() {
  const { pushToast } = useToast();

  return (
    <button
      onClick={() =>
        pushToast({
          description: "Project settings and metadata were saved.",
          title: "Project saved",
          tone: "success",
        })
      }
      type="button"
    >
      Show toast
    </button>
  );
}

describe("ToastProvider", () => {
  it("renders and dismisses success toasts", async () => {
    const user = userEvent.setup();

    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Show toast" }));

    expect(screen.getByRole("status")).toHaveTextContent("Project saved");
    expect(screen.getByText("Project settings and metadata were saved.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dismiss toast" }));

    expect(screen.queryByText("Project saved")).not.toBeInTheDocument();
  });
});
