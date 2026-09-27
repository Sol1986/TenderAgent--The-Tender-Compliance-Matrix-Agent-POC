import { z } from "zod";

export const stageIds = ["parse_document", "prepare_inputs", "analyze_chunk", "analyze_table", "reduce_findings", "generate_report"] as const;
export const eventTypes = ["run.started", "stage.started", "stage.completed", "stage.skipped", "worker.started", "worker.completed", "worker.failed", "run.warning", "run.completed", "run.failed"] as const;
export const categoryNames = ["submission", "required_documents", "certifications", "insurance", "bonding_security", "experience", "personnel", "technical", "financial", "formatting", "legal_regulatory", "language", "security", "site_meeting", "signatures"] as const;
const count = z.number().int().nonnegative();
const timestamp = z.iso.datetime({ offset: true });
export const errorSchema = z.object({ code: z.string(), message: z.string() });
export const taskSchema = z.object({
  id: z.string(), stage: z.enum(stageIds), label: z.string(),
  status: z.enum(["pending", "running", "completed", "failed", "skipped"]),
  started_at: timestamp.nullable(), finished_at: timestamp.nullable(),
  duration_ms: count.nullable(), findings_count: count.nullable(),
});
const requirementSchema = z.object({
  requirement: z.string(), status: z.enum(["FOUND", "NOT_REQUIRED", "EXTERNAL_REFERENCE"]),
  requirement_type: z.enum(["MANDATORY", "CONDITIONAL", "INFORMATIONAL"]),
  source_sections: z.array(z.string()), evidence: z.array(z.string()),
});
export const analysisSchema = z.object({ categories: z.array(z.object({
  category: z.enum(categoryNames), status: z.enum(["FOUND", "NOT_FOUND"]),
  requirements: z.array(requirementSchema),
}).refine(c => (c.status === "FOUND") === (c.requirements.length > 0), "Inconsistent category status"))
  .length(15).refine(categories => new Set(categories.map(c => c.category)).size === 15, "Duplicate categories") });
export const reportSchema = z.object({
  executive_summary: z.string(), reasons_to_consider_bidding: z.array(z.string()),
  concerns_and_risks: z.array(z.string()), missing_information: z.array(z.string()),
  mandatory_requirements: z.array(z.string()), conditional_requirements: z.array(z.string()),
  external_references_to_review: z.array(z.string()), questions_for_bid_team: z.array(z.string()),
});
export const snapshotSchema = z.object({
  run_id: z.uuid(), status: z.enum(["queued", "running", "completed", "failed"]),
  input: z.object({ id: z.string(), display_name: z.string() }),
  started_at: timestamp.nullable(), finished_at: timestamp.nullable(), duration_ms: count.nullable(),
  last_event_id: count,
  stages: z.array(taskSchema).length(6).refine(stages => new Set(stages.map(s => s.stage)).size === 6 && stages.every(s => s.id === s.stage), "Invalid stage roster"),
  workers: z.array(taskSchema).refine(workers => new Set(workers.map(w => w.id)).size === workers.length, "Duplicate worker IDs"),
  metrics: z.object({ total_chunks: count.nullable(), text_chunks: count.nullable(), tables: count.nullable(),
    filtered_chunks: count.nullable(), completed_workers: count, raw_findings: count, final_requirements: count.nullable() }),
  warnings: z.array(errorSchema), output: z.object({ tender_analysis: analysisSchema.nullable(), decision_support_report: reportSchema.nullable() }),
  error: errorSchema.nullable(),
}).refine(snapshot => snapshot.status !== "completed" || (!!snapshot.output.tender_analysis && !!snapshot.output.decision_support_report), "Completed output missing");
export const eventSchema = z.object({
  event_id: count.positive(), run_id: z.uuid(), type: z.string(), status: z.string(),
  stage: z.enum(stageIds).nullable(), worker_id: z.string().nullable(), timestamp,
  duration_ms: count.nullable(), summary: z.string(), data: z.record(z.string(), z.union([z.string(), z.number().int()])),
}).superRefine((event, context) => {
  if (event.type.startsWith("worker.") && (!event.worker_id || !event.stage)) context.addIssue({ code: "custom", message: "Worker identity missing" });
  if (event.type.startsWith("stage.") && !event.stage) context.addIssue({ code: "custom", message: "Stage identity missing" });
  if (event.type === "worker.completed" && (typeof event.data.findings_count !== "number" || event.data.findings_count < 0)) context.addIssue({ code: "custom", message: "Finding count missing" });
});
export const inputsSchema = z.array(z.object({ id: z.string(), display_name: z.string(), size_bytes: count.nullable(), available: z.boolean() }));
export const startSchema = z.object({ run_id: z.uuid(), status: z.enum(["queued", "running", "completed", "failed"]), snapshot_url: z.string(), events_url: z.string() });
export type RunSnapshot = z.infer<typeof snapshotSchema>;
export type RunEvent = z.infer<typeof eventSchema>;
export type TaskSnapshot = z.infer<typeof taskSchema>;
export type DemoInput = z.infer<typeof inputsSchema>[number];
export type StageId = typeof stageIds[number];
export const stageLabels: Record<StageId, string> = {
  parse_document: "Parse document", prepare_inputs: "Prepare inputs", analyze_chunk: "Analyze text",
  analyze_table: "Analyze tables", reduce_findings: "Consolidate findings", generate_report: "Generate report",
};
export const isTerminal = (snapshot: RunSnapshot) => ["completed", "failed"].includes(snapshot.status);
