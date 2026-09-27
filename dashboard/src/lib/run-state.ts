import { eventTypes, type RunEvent, type RunSnapshot, type TaskSnapshot } from "./contracts";

export interface RunState { base: RunSnapshot | null; events: RunEvent[] }
export const initialRunState: RunState = { base: null, events: [] };
export type RunAction = { type: "reset" } | { type: "snapshot"; snapshot: RunSnapshot } | { type: "event"; event: RunEvent };

/** Keep authoritative snapshots separate from events so a late fetch cannot undo live work. */
export function runReducer(state: RunState, action: RunAction): RunState {
  if (action.type === "reset") return initialRunState;
  if (action.type === "snapshot") {
    if (state.base && (action.snapshot.run_id !== state.base.run_id || action.snapshot.last_event_id < state.base.last_event_id)) return state;
    return { ...state, base: action.snapshot };
  }
  const { event } = action;
  if (!eventTypes.includes(event.type as typeof eventTypes[number]) ||
      (state.base && event.run_id !== state.base.run_id) || state.events.some(e => e.event_id === event.event_id)) return state;
  return { ...state, events: [...state.events, event].sort((a, b) => a.event_id - b.event_id) };
}

function updateTask(task: TaskSnapshot, event: RunEvent): TaskSnapshot {
  const suffix = event.type.split(".")[1];
  if (suffix === "started") return { ...task, status: "running", started_at: event.timestamp };
  return { ...task, status: suffix as TaskSnapshot["status"], finished_at: event.timestamp,
    duration_ms: event.duration_ms, findings_count: event.type === "worker.completed" ? event.data.findings_count as number : task.findings_count };
}

/** Project actual observations only; timers never advance execution state. */
export function projectRun(state: RunState): RunSnapshot | null {
  if (!state.base) return null;
  const view: RunSnapshot = structuredClone(state.base);
  for (const event of state.events) {
    if (event.event_id <= state.base.last_event_id || event.run_id !== view.run_id) continue;
    view.last_event_id = Math.max(view.last_event_id, event.event_id);
    if (event.type === "run.started") { view.status = "running"; view.started_at = event.timestamp; }
    if (event.type.startsWith("stage.")) view.stages = view.stages.map(task => task.stage === event.stage ? updateTask(task, event) : task);
    if (event.type.startsWith("worker.")) {
      // A worker may start while the roster snapshot is in flight. Its real ID
      // is usable immediately; a later authoritative snapshot supplies its label.
      if (!view.workers.some(task => task.id === event.worker_id)) view.workers.push({
        id: event.worker_id!, stage: event.stage!, label: event.worker_id!, status: "pending",
        started_at: null, finished_at: null, duration_ms: null, findings_count: null,
      });
      view.workers = view.workers.map(task => task.id === event.worker_id ? updateTask(task, event) : task);
      if (event.type === "worker.completed") { view.metrics.completed_workers++; view.metrics.raw_findings += event.data.findings_count as number; }
    }
    if (event.type === "stage.completed" && event.stage === "prepare_inputs") {
      for (const key of ["total_chunks", "text_chunks", "tables", "filtered_chunks"] as const) {
        if (typeof event.data[key] === "number") view.metrics[key] = event.data[key];
      }
    }
    if (event.type === "run.warning") view.warnings.push({ code: String(event.data.code || "WARNING"), message: event.summary });
    if (event.type === "run.completed" || event.type === "run.failed") {
      view.status = event.type === "run.completed" ? "completed" : "failed";
      view.finished_at = event.timestamp; view.duration_ms = event.duration_ms;
      if (view.status === "failed") view.error = { code: String(event.data.code || "RUN_FAILED"), message: event.summary };
    }
  }
  return view;
}

export function formatDuration(milliseconds: number | null): string {
  if (milliseconds === null) return "—";
  const seconds = Math.floor(milliseconds / 1000);
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s` : `${seconds}s`;
}
