import React from "react";
import { render, screen } from "@testing-library/react";
import { AppShell } from "../app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/operations",
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("AppShell", () => {
  it("shows the active navigation item and viewer session details", () => {
    render(
      <AppShell
        session={{
          auth_mode: "single_user_local",
          environment: "development",
          requires_approval_checkpoints: true,
          user: {
            email: "creatoros-local@example.com",
            id: "viewer-1",
            name: "CreatorOS Local User",
          },
        }}
        sessionError={null}
      >
        <div>Workspace body</div>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "Operations" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("CreatorOS Local User")).toBeInTheDocument();
    expect(screen.getByText("creatoros-local@example.com")).toBeInTheDocument();
    expect(screen.getByText("Workspace body")).toBeInTheDocument();
  });

  it("surfaces session check warnings when the API session cannot be loaded", () => {
    render(
      <AppShell session={null} sessionError="API session is currently unavailable.">
        <div>Workspace body</div>
      </AppShell>,
    );

    expect(screen.getByText("Session check needs attention.")).toBeInTheDocument();
    expect(screen.getByText("API session is currently unavailable.")).toBeInTheDocument();
  });
});
