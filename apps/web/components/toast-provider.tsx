"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

type ToastTone = "error" | "info" | "success";

type ToastInput = {
  description?: string;
  durationMs?: number;
  title: string;
  tone?: ToastTone;
};

type ToastRecord = Required<Pick<ToastInput, "title">> &
  Pick<ToastInput, "description"> & {
    durationMs: number;
    id: number;
    tone: ToastTone;
  };

type ToastContextValue = {
  pushToast: (toast: ToastInput) => void;
};

const DEFAULT_DURATION_MS = 4800;

const ToastContext = createContext<ToastContextValue | null>(null);

function toastCardClassName(tone: ToastTone): string {
  switch (tone) {
    case "error":
      return "border-rose-300/30 bg-rose-500/12 text-rose-50";
    case "success":
      return "border-emerald-300/30 bg-emerald-500/12 text-emerald-50";
    default:
      return "border-cyan-300/30 bg-cyan-500/12 text-cyan-50";
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const nextIdRef = useRef(0);
  const timeoutIdsRef = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismissToast = useCallback((toastId: number) => {
    const timeoutId = timeoutIdsRef.current.get(toastId);
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutIdsRef.current.delete(toastId);
    }
    setToasts((currentToasts) => currentToasts.filter((toast) => toast.id !== toastId));
  }, []);

  const pushToast = useCallback(
    ({ description, durationMs = DEFAULT_DURATION_MS, title, tone = "info" }: ToastInput) => {
      nextIdRef.current += 1;
      const id = nextIdRef.current;
      setToasts((currentToasts) => [...currentToasts, { description, durationMs, id, title, tone }]);
      const timeoutId = setTimeout(() => {
        dismissToast(id);
      }, durationMs);
      timeoutIdsRef.current.set(id, timeoutId);
    },
    [dismissToast],
  );

  useEffect(() => {
    const timeoutIds = timeoutIdsRef.current;
    return () => {
      for (const timeoutId of timeoutIds.values()) {
        clearTimeout(timeoutId);
      }
      timeoutIds.clear();
    };
  }, []);

  const value = useMemo<ToastContextValue>(() => ({ pushToast }), [pushToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-atomic="true"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 top-20 z-50 mx-auto flex w-full max-w-md flex-col gap-3 px-4"
      >
        {toasts.map((toast) => (
          <section
            className={`pointer-events-auto rounded-3xl border px-4 py-4 shadow-2xl shadow-slate-950/40 backdrop-blur ${toastCardClassName(toast.tone)}`}
            key={toast.id}
            role={toast.tone === "error" ? "alert" : "status"}
          >
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">{toast.title}</p>
                {toast.description ? (
                  <p className="mt-1 text-sm leading-6 text-white/80">{toast.description}</p>
                ) : null}
              </div>
              <button
                aria-label="Dismiss toast"
                className="rounded-full border border-white/10 px-2 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-white/70 transition hover:border-white/20 hover:bg-white/10 hover:text-white"
                onClick={() => dismissToast(toast.id)}
                type="button"
              >
                Close
              </button>
            </div>
          </section>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider.");
  }
  return context;
}
