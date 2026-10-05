import { describe, expect, it } from "vitest";
import { eventSchema, snapshotSchema } from "@/lib/contracts";
import { initialRunState, projectRun, runReducer } from "@/lib/run-state";
import { completedSnapshot, event, snapshot } from "./fixtures";

describe("Live state projection", () => {
  it("applies observed document and stage events once", () => {
    let state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    state = runReducer(state, { type: "event", event: event(2) });
    const completed = event(3, { type: "worker.completed", status: "completed", data: { findings_count: 3 } });
    state = runReducer(state, { type: "event", event: completed });
    state = runReducer(state, { type: "event", event: completed });
    state = runReducer(state, { type: "event", event: event(4, { type: "stage.started", stage: "reconcile", worker_id: null }) });
    const view = projectRun(state)!;
    expect(view.workers[0]).toMatchObject({ status: "completed", findings_count: 3 });
    expect(view.metrics.completed_workers).toBe(1);
    expect(view.stages.find(stage => stage.id === "reconcile")?.status).toBe("running");
    expect(state.events).toHaveLength(3);
  });
  it("preserves newer events over delayed snapshots", () => {
    let state = runReducer(initialRunState, { type: "snapshot", snapshot: snapshot() });
    state = runReducer(state, { type: "event", event: event(3, { type: "worker.completed", data: { findings_count: 2 } }) });
    const stale = snapshot({ last_event_id: 0 });
    expect(runReducer(state, { type: "snapshot", snapshot: stale })).toBe(state);
    expect(projectRun(state)?.metrics.raw_findings).toBe(2);
  });
  it("requires a download for a completed snapshot", () => {
    expect(snapshotSchema.safeParse(completedSnapshot()).success).toBe(true);
    expect(snapshotSchema.safeParse({ ...completedSnapshot(), output: { excel_url: null } }).success).toBe(false);
    expect(eventSchema.safeParse(event(2, { type: "worker.completed", worker_id: null })).success).toBe(false);
  });
});
