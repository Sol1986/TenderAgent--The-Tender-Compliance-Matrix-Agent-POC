import { stageIds, type RunEvent, type RunSnapshot } from "@/lib/contracts";

export const runId = "5f7d9867-f73b-4267-a71c-9f8175697c93";
export const timestamp = "2026-09-17T03:00:00+00:00";
export const sample = { id: "sample-tender", display_name: "Sample tender package", size_bytes: 123000, available: true };
export function snapshot(overrides: Partial<RunSnapshot> = {}): RunSnapshot {
  return {
    run_id: runId, status: "running", input: { id: sample.id, display_name: sample.display_name },
    started_at: timestamp, finished_at: null, duration_ms: null, last_event_id: 1,
    stages: stageIds.map(id => ({ id, stage: id, label: id, status: "pending", started_at: null, finished_at: null, duration_ms: null, findings_count: null })),
    workers: [], metrics: { documents_total: null, completed_workers: 0, raw_findings: 0, final_requirements: null },
    warnings: [], output: { excel_url: null }, error: null, ...overrides,
  };
}
export function event(id: number, overrides: Partial<RunEvent> = {}): RunEvent {
  return { event_id: id, run_id: runId, type: "worker.started", status: "started", stage: "extract", worker_id: "doc-1", timestamp,
    duration_ms: null, summary: "Reading source PDF.", data: {}, ...overrides };
}
export function completedSnapshot(): RunSnapshot {
  const result = snapshot({ status: "completed", last_event_id: 8, duration_ms: 25000, finished_at: timestamp });
  result.stages = result.stages.map(stage => ({ ...stage, status: "completed" }));
  result.metrics = { documents_total: 1, completed_workers: 1, raw_findings: 27, final_requirements: 18 };
  result.output.excel_url = `/api/runs/${runId}/compliance-matrix.xlsx`;
  return result;
}
