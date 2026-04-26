"use client";

import { startTransition, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiBaseUrl } from "../lib/env";

type BackgroundJobEventRefreshOptions = {
  enabled: boolean;
  jobId?: string | null;
  projectId?: string | null;
  throttleMs?: number;
};

type BackgroundJobEventRefreshState = {
  isLiveConnected: boolean;
};

export function useBackgroundJobEventRefresh({
  enabled,
  jobId = null,
  projectId = null,
  throttleMs = 1000,
}: BackgroundJobEventRefreshOptions): BackgroundJobEventRefreshState {
  const router = useRouter();
  const [isLiveConnected, setIsLiveConnected] = useState(false);
  const canUseLiveEvents =
    enabled && typeof window !== "undefined" && typeof window.EventSource !== "undefined";

  useEffect(() => {
    if (!canUseLiveEvents) {
      return undefined;
    }

    const streamUrl = new URL("/api/events/background-jobs/stream", apiBaseUrl);
    if (projectId) {
      streamUrl.searchParams.set("project_id", projectId);
    }
    if (jobId) {
      streamUrl.searchParams.set("job_id", jobId);
    }

    const eventSource = new window.EventSource(streamUrl.toString());
    let cooldownTimer: number | null = null;
    let refreshLocked = false;

    const releaseRefreshLock = () => {
      refreshLocked = false;
      cooldownTimer = null;
    };

    const handleJobEvent = () => {
      setIsLiveConnected(true);
      if (refreshLocked) {
        return;
      }

      refreshLocked = true;
      startTransition(() => {
        router.refresh();
      });
      cooldownTimer = window.setTimeout(releaseRefreshLock, throttleMs);
    };

    const handleKeepalive = () => {
      setIsLiveConnected(true);
    };

    eventSource.onopen = () => {
      setIsLiveConnected(true);
    };
    eventSource.onerror = () => {
      setIsLiveConnected(false);
    };
    eventSource.addEventListener("job_event", handleJobEvent);
    eventSource.addEventListener("keepalive", handleKeepalive);

    return () => {
      eventSource.removeEventListener("job_event", handleJobEvent);
      eventSource.removeEventListener("keepalive", handleKeepalive);
      eventSource.close();
      if (cooldownTimer !== null) {
        window.clearTimeout(cooldownTimer);
      }
    };
  }, [canUseLiveEvents, jobId, projectId, router, throttleMs]);

  return { isLiveConnected: canUseLiveEvents ? isLiveConnected : false };
}
