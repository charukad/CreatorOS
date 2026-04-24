"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ToastProvider } from "./toast-provider";
import type { ViewerSession } from "../types/api";

type AppShellProps = {
  children: ReactNode;
  session: ViewerSession | null;
  sessionError: string | null;
};

type NavigationItem = {
  href: string;
  isActive: (pathname: string) => boolean;
  label: string;
};

const navigationItems: NavigationItem[] = [
  {
    href: "/",
    isActive: (pathname) =>
      pathname === "/" ||
      pathname.startsWith("/projects/") ||
      pathname.startsWith("/brand-profiles/") ||
      pathname.startsWith("/jobs/"),
    label: "Workspace",
  },
  {
    href: "/operations",
    isActive: (pathname) => pathname === "/operations",
    label: "Operations",
  },
];

function navigationClassName(isActive: boolean): string {
  return isActive
    ? "border-cyan-300/40 bg-cyan-400/15 text-cyan-50"
    : "border-white/10 bg-white/5 text-slate-200 hover:border-cyan-300/30 hover:bg-cyan-400/10 hover:text-white";
}

function environmentLabel(environment: string | null): string {
  if (!environment) {
    return "Session unavailable";
  }

  return environment.replaceAll("_", " ");
}

export function AppShell({ children, session, sessionError }: AppShellProps) {
  const pathname = usePathname();

  return (
    <ToastProvider>
      <div className="min-h-screen">
        <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/70 backdrop-blur-xl">
          <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-1">
              <Link className="w-fit text-xl font-semibold tracking-[0.08em] text-white" href="/">
                CreatorOS
              </Link>
              <p className="text-sm text-slate-300">
                Personal workflow orchestration for idea, script, asset, media, publish, and analytics passes.
              </p>
            </div>

            <div className="flex flex-col gap-3 lg:items-end">
              <nav className="flex flex-wrap gap-3">
                {navigationItems.map((item) => {
                  const active = item.isActive(pathname);
                  return (
                    <Link
                      aria-current={active ? "page" : undefined}
                      className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition ${navigationClassName(active)}`}
                      href={item.href}
                      key={item.href}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </nav>

              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                  Personal session
                </p>
                {session ? (
                  <>
                    <p className="mt-2 font-medium text-white">{session.user.name}</p>
                    <p className="text-xs text-slate-400">{session.user.email}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                      <span className="rounded-full border border-white/10 px-2 py-1">
                        {session.auth_mode.replaceAll("_", " ")}
                      </span>
                      <span className="rounded-full border border-white/10 px-2 py-1">
                        {environmentLabel(session.environment)}
                      </span>
                      {session.requires_approval_checkpoints ? (
                        <span className="rounded-full border border-amber-300/20 px-2 py-1 text-amber-100">
                          approval gates on
                        </span>
                      ) : null}
                    </div>
                  </>
                ) : (
                  <>
                    <p className="mt-2 font-medium text-white">Unable to confirm the local operator.</p>
                    <p className="text-xs leading-5 text-slate-400">
                      Make sure the API is reachable so CreatorOS can attach actions to the configured personal account.
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>
        </header>

        {sessionError ? (
          <section className="mx-auto mt-4 max-w-7xl px-6">
            <div className="rounded-3xl border border-amber-300/25 bg-amber-400/10 px-5 py-4 text-sm text-amber-50">
              <p className="font-semibold">Session check needs attention.</p>
              <p className="mt-2 leading-6">{sessionError}</p>
            </div>
          </section>
        ) : null}

        <div className="pb-10">{children}</div>
      </div>
    </ToastProvider>
  );
}
