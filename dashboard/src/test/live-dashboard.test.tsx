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
  it("starts once, shows real steps, and offers Excel after completion", async () => {
    render(<Dashboard />);
    const button = await screen.findByRole("button", { name: "Generate compliance matrix" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button); fireEvent.click(button);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    expect(posts()).toHaveLength(1);
    const source = FakeEventSource.instances[0];
    act(() => source.emit("stage.started", event(2, { type: "stage.started", stage: "extract", worker_id: null })));
    expect(await screen.findByText("While this runs, explain")).toBeVisible();
    current = completedSnapshot();
    act(() => source.emit("run.completed", event(8, { type: "run.completed", stage: null, worker_id: null, duration_ms: 25000 })));
    expect(await screen.findByRole("link", { name: /Download Excel matrix/ })).toBeVisible();
    expect(source.close).toHaveBeenCalled();
  });
  it("restores a completed run without starting another analysis", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`); current = completedSnapshot();
    render(<Dashboard />);
    expect(await screen.findByRole("link", { name: /Download Excel matrix/ })).toBeVisible();
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(posts()).toHaveLength(0);
  });
  it("never offers a workbook for a failed run", async () => {
    window.history.replaceState({}, "", `/?run=${runId}`);
    current = snapshot({ status: "failed", error: { code: "PROVIDER_FAILED", message: "The provider failed." } });
    render(<Dashboard />);
    expect(await screen.findByText("Matrix unavailable")).toBeVisible();
    expect(screen.queryByRole("link", { name: /Download Excel matrix/ })).not.toBeInTheDocument();
  });
});
