import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "@/app/page";
import { runId, sample, snapshot, completedSnapshot, event } from "./fixtures";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners = new Map<string, (event: MessageEvent) => void>();
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  constructor(public url: string) { FakeEventSource.instances.push(this); }
  addEventListener(name: string, listener: (event: MessageEvent) => void) { this.listeners.set(name, listener); }
  emit(name: string, data: unknown) { this.listeners.get(name)?.(new MessageEvent(name, { data: JSON.stringify(data) })); }
}

let current = snapshot();
const fetchMock = vi.fn();
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
beforeEach(() => {
  current = snapshot(); FakeEventSource.instances = []; sessionStorage.clear();
  window.history.replaceState({}, "", "/");
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/api/demo-inputs")) return json([sample]);
    if (options?.method === "POST") return json({ run_id: runId, status: "queued", snapshot_url: `/api/runs/${runId}`, events_url: `/api/runs/${runId}/events` }, 202);
    return json(current);
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => vi.unstubAllGlobals());
const posts = () => fetchMock.mock.calls.filter(([, options]) => options?.method === "POST");

describe("Live dashboard behavior", () => {
  it("closes a failed run stream and retains the consolidated analysis for review", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`);
    render(<Dashboard />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0];
    current = completedSnapshot();
    current.status = "failed"; current.last_event_id = 9;
    current.output.decision_support_report = null;
    current.error = { code: "PROVIDER_FAILED", message: "The report provider failed." };
    act(() => source.emit("run.failed", event(9, { type: "run.failed", stage: null, worker_id: null, summary: "The report provider failed.", data: { code: "PROVIDER_FAILED" } })));
    expect(await screen.findByText("The decision-support report could not be completed.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Review available requirements" })).toBeEnabled();
    expect(source.close).toHaveBeenCalled();
    expect(posts()).toHaveLength(0);
  });
  it("starts once, receives named events, and closes on completion", async () => {
    render(<Dashboard />);
    const button = await screen.findByRole("button", { name: "Analyze Tender" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button); fireEvent.click(button);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    expect(posts()).toHaveLength(1);
    expect(window.location.search).toContain(runId);
    const source = FakeEventSource.instances[0];
    act(() => { source.onopen?.(); source.emit("worker.started", event(2)); });
    expect(await screen.findByText("chunk-1", { selector: ".worker-id" })).toBeInTheDocument();
    current = completedSnapshot();
    act(() => source.emit("run.completed", event(8, { type: "run.completed", stage: null, worker_id: null, duration_ms: 25000 })));
    expect(await screen.findByText("Synthetic test report. Human review required.")).toBeInTheDocument();
    expect(source.close).toHaveBeenCalled();
    expect(posts()).toHaveLength(1);
  });
  it("restores a run from its URL and reconnects without another POST", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`);
    render(<Dashboard />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0];
    expect(source.url).toContain("after_event_id=1");
    act(() => source.onerror?.());
    expect(await screen.findByText(/Reconnecting to this run/)).toBeInTheDocument();
    act(() => source.onopen?.());
    expect(posts()).toHaveLength(0);
  });
  it("restores a completed snapshot without opening a stream", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`); current = completedSnapshot();
    render(<Dashboard />);
    expect(await screen.findByText("Synthetic test report. Human review required.")).toBeInTheDocument();
    expect(FakeEventSource.instances).toHaveLength(0); expect(posts()).toHaveLength(0);
  });
  it("preserves the live snapshot and stream during section navigation", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`);
    render(<Dashboard />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0];
    act(() => source.emit("worker.started", event(2)));
    expect(await screen.findByText("chunk-1", { selector: ".worker-id" })).toBeInTheDocument();
    act(() => {
      window.history.pushState({}, "", `/?run=${runId}#workers`);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(screen.getByText("chunk-1", { selector: ".worker-id" })).toBeInTheDocument();
    expect(source.close).not.toHaveBeenCalled();
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(posts()).toHaveLength(0);
  });
  it("shows a restarted/expired run and never falls back to mock results", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`);
    fetchMock.mockImplementation(async (url: string) => url.endsWith("demo-inputs") ? json([sample]) : json({ error: { code: "RUN_NOT_FOUND", message: "This run expired or the demo server restarted." } }, 404));
    render(<Dashboard />);
    expect(await screen.findByText("Run no longer available")).toBeInTheDocument();
    expect(posts()).toHaveLength(0); expect(FakeEventSource.instances).toHaveLength(0);
    expect(screen.queryByText("Synthetic test report. Human review required.")).not.toBeInTheDocument();
  });
  it("uses the same idempotency key after an ambiguous start response", async () => {
    let fail = true;
    fetchMock.mockImplementation(async (url: string, options?: RequestInit) => {
      if (url.endsWith("demo-inputs")) return json([sample]);
      if (options?.method === "POST") {
        if (fail) { fail = false; throw new TypeError("network"); }
        return json({ run_id: runId, status: "running", snapshot_url: "x", events_url: "x" }, 202);
      }
      return json(current);
    });
    render(<Dashboard />);
    const button = await screen.findByRole("button", { name: "Analyze Tender" });
    await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button);
    fireEvent.click(await screen.findByRole("button", { name: "Recover run" }));
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[0][1].headers["Idempotency-Key"]).toBe(posts()[1][1].headers["Idempotency-Key"]);
  });
  it("rejects malformed events and disposes the subscription", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`);
    const view = render(<Dashboard />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0];
    act(() => source.emit("worker.completed", { invalid: true }));
    expect(await screen.findByText(/A live update could not be read/)).toBeInTheDocument();
    expect(source.close).toHaveBeenCalled();
    view.unmount(); expect(source.close).toHaveBeenCalledTimes(2);
  });
  it("shows an unavailable backend as an error, not example data", async () => {
    fetchMock.mockRejectedValue(new TypeError("network"));
    render(<Dashboard />);
    expect(await screen.findByText(/Cannot reach the backend/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze Tender" })).toBeDisabled();
    expect(posts()).toHaveLength(0);
  });
});
