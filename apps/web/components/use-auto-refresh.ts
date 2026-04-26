"use client";

import { useRouter } from "next/navigation";
import { startTransition, useEffect } from "react";

type UseAutoRefreshOptions = {
  enabled: boolean;
  intervalMs?: number;
};

export function useAutoRefresh({
  enabled,
  intervalMs = 8000,
}: UseAutoRefreshOptions): void {
  const router = useRouter();

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      startTransition(() => {
        router.refresh();
      });
    }, intervalMs);

    return () => window.clearInterval(intervalId);
  }, [enabled, intervalMs, router]);
}
