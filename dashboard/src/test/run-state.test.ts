import { describe, expect, it } from "vitest";
import { eventSchema, snapshotSchema } from "@/lib/contracts";
import { initialRunState, projectRun, runReducer } from "@/lib/run-state";
import { event, snapshot } from "./fixtures";

describe("Live state projection", () => {
  it("keeps parallel workers independent and deduplicates replay", () => {
    let state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    state = runReducer(state, { type: "event", event: event(2) });
    state = runReducer(state, { type: "event", event: event(3, { worker_id: "table-1", stage: "analyze_table" }) });
    const finished = event(4, { type: "worker.completed", status: "completed", duration_ms: 1000, data: { findings_count: 0 } });
    state = runReducer(state, { type: "event", event: finished });
    state = runReducer(state, { type: "event", event: finished });
    const view = projectRun(state)!;
    expect(view.workers.map(w => w.status)).toEqual(["completed", "running"]);
    expect(view.metrics.completed_workers).toBe(1);
    expect(view.metrics.raw_findings).toBe(0);
    expect(state.events).toHaveLength(3);
  });
  it("replays newer events over a delayed roster snapshot without rolling back", () => {
    let state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    state = runReducer(state, { type: "event", event: event(5, { type: "worker.completed", data: { findings_count: 3 } }) });
    const roster = snapshot({ last_event_id: 3, workers: [{ id: "chunk-1", stage: "analyze_chunk", label: "Real section label", status: "running", started_at: null, finished_at: null, duration_ms: null, findings_count: null }] });
    state = runReducer(state, { type: "snapshot", snapshot: roster });
    expect(projectRun(state)!.workers[0]).toMatchObject({ label: "Real section label", status: "completed", findings_count: 3 });
    const stale = snapshot({ last_event_id: 2 });
    expect(runReducer(state, { type: "snapshot", snapshot: stale })).toBe(state);
  });
  it("does not count events already included in an authoritative snapshot", () => {
    let state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    state = runReducer(state, { type: "event", event: event(4, { type: "worker.completed", data: { findings_count: 2 } }) });
    const base = snapshot({ last_event_id: 4 }); base.metrics.completed_workers = 1; base.metrics.raw_findings = 2;
    state = runReducer(state, { type: "snapshot", snapshot: base });
    expect(projectRun(state)!.metrics.raw_findings).toBe(2);
  });
  it("keeps worker completion separate from final report completion", () => {
    let state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    state = runReducer(state, { type: "event", event: event(4, { type: "worker.completed", data: { findings_count: 3 } }) });
    expect(projectRun(state)!.status).toBe("running");
    expect(projectRun(state)!.stages.find(s => s.id === "generate_report")!.status).toBe("pending");
  });
  it("handles failed and skipped work without inventing completion", () => {
    let state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    state = runReducer(state, { type: "event", event: event(2, { type: "stage.skipped", stage: "analyze_table", worker_id: null }) });
    state = runReducer(state, { type: "event", event: event(3, { type: "worker.failed" }) });
    expect(projectRun(state)!.stages.find(s => s.id === "analyze_table")!.status).toBe("skipped");
    expect(projectRun(state)!.workers[0].status).toBe("failed");
  });
  it("ignores future event types and another run's updates", () => {
    const state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    expect(runReducer(state, { type: "event", event: event(2, { type: "future.event" }) })).toBe(state);
    expect(runReducer(state, { type: "event", event: event(2, { run_id: "other-run" }) })).toBe(state);
  });
  it("rejects malformed model payloads and missing worker result counts", () => {
    expect(snapshotSchema.safeParse({ ...snapshot(), output: { tender_analysis: { categories: [] }, decision_support_report: null } }).success).toBe(false);
    expect(eventSchema.safeParse(event(3, { type: "worker.completed" })).success).toBe(false);
  });
});
