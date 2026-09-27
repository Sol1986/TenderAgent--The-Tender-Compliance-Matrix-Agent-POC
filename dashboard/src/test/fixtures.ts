/** Synthetic contract fixtures for tests only. Never imported by the application. */
import { categoryNames, stageIds, type RunEvent, type RunSnapshot } from "@/lib/contracts";

export const runId = "5f7d9867-f73b-4267-a71c-9f8175697c93";
export const timestamp = "2026-09-17T03:00:00+00:00";
export const sample = { id: "sample-tender", display_name: "Sample tender", size_bytes: 123000, available: true };
export function snapshot(overrides: Partial<RunSnapshot> = {}): RunSnapshot {
  return {
    run_id: runId, status: "running", input: { id: sample.id, display_name: sample.display_name },
    started_at: timestamp, finished_at: null, duration_ms: null, last_event_id: 1,
    stages: stageIds.map(id => ({ id, stage: id, label: id, status: "pending", started_at: null, finished_at: null, duration_ms: null, findings_count: null })),
    workers: [], metrics: { total_chunks: null, text_chunks: null, tables: null, filtered_chunks: null, completed_workers: 0, raw_findings: 0, final_requirements: null },
    warnings: [], output: { tender_analysis: null, decision_support_report: null }, error: null, ...overrides,
  };
}
export function event(id: number, overrides: Partial<RunEvent> = {}): RunEvent {
  return { event_id: id, run_id: runId, type: "worker.started", status: "started", stage: "analyze_chunk", worker_id: "chunk-1", timestamp,
    duration_ms: null, summary: "Fixture worker started.", data: {}, ...overrides };
}
export function completedSnapshot(): RunSnapshot {
  const result = snapshot({ status: "completed", last_event_id: 8, duration_ms: 25000, finished_at: timestamp });
  result.stages = result.stages.map(s => ({ ...s, status: "completed" }));
  result.output = {
    tender_analysis: { categories: categoryNames.map(category => ({ category, status: "NOT_FOUND", requirements: [] })) },
    decision_support_report: { executive_summary: "Synthetic test report. Human review required.", reasons_to_consider_bidding: [], concerns_and_risks: [], missing_information: [], mandatory_requirements: [], conditional_requirements: [], external_references_to_review: [], questions_for_bid_team: [] },
  };
  return result;
}
