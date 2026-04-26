import React from "react";
import { act, render } from "@testing-library/react";
import { useBackgroundJobEventRefresh } from "../use-background-job-event-refresh";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh,
  }),
}));

class MockEventSource {
  static instances: MockEventSource[] = [];

  close = vi.fn();
  listeners = new Map<string, Set<EventListener>>();
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  url: string;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: EventListener) {
    this.listeners.get(type)?.delete(listener);
  }

  dispatch(type: string, event = new MessageEvent(type)) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

function HookProbe({
  enabled,
  jobId,
  projectId,
}: {
  enabled: boolean;
  jobId?: string;
  projectId?: string;
}) {
  const { isLiveConnected } = useBackgroundJobEventRefresh({
    enabled,
    jobId,
    projectId,
  });

  return <div>{isLiveConnected ? "connected" : "disconnected"}</div>;
}

describe("useBackgroundJobEventRefresh", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    refresh.mockClear();
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("subscribes with project and job filters and refreshes on job events", () => {
    const { unmount } = render(
      <HookProbe enabled jobId="job-123" projectId="project-456" />,
    );

    expect(MockEventSource.instances).toHaveLength(1);
    const eventSource = MockEventSource.instances[0];
    expect(eventSource.url).toBe(
      "http://localhost:8000/api/events/background-jobs/stream?project_id=project-456&job_id=job-123",
    );

    act(() => {
      eventSource.onopen?.(new Event("open"));
      eventSource.dispatch(
        "job_event",
        new MessageEvent("job_event", {
          data: JSON.stringify({ background_job_id: "job-123" }),
        }),
      );
    });

    expect(refresh).toHaveBeenCalledTimes(1);

    unmount();
    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });

  it("does not create an EventSource connection when disabled", () => {
    render(<HookProbe enabled={false} />);

    expect(MockEventSource.instances).toHaveLength(0);
    expect(refresh).not.toHaveBeenCalled();
  });
});
