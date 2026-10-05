import { z } from "zod";

export const stageIds = ["extract", "reconcile", "resolve", "classify", "export"] as const;
export const eventTypes = ["run.started", "stage.started", "stage.completed", "stage.skipped", "worker.started", "worker.completed", "worker.failed", "run.warning", "run.completed", "run.failed"] as const;
const count = z.number().int().nonnegative();
const timestamp = z.iso.datetime({ offset: true });
export const errorSchema = z.object({ code: z.string(), message: z.string() });
export const taskSchema = z.object({
  id: z.string(), stage: z.enum(stageIds), label: z.string(),
  status: z.enum(["pending", "running", "completed", "failed", "skipped"]),
  started_at: timestamp.nullable(), finished_at: timestamp.nullable(),
  duration_ms: count.nullable(), findings_count: count.nullable(),
});
export const snapshotSchema = z.object({
  run_id: z.uuid(), status: z.enum(["queued", "running", "completed", "failed"]),
  input: z.object({ id: z.string(), display_name: z.string() }),
  started_at: timestamp.nullable(), finished_at: timestamp.nullable(), duration_ms: count.nullable(),
  last_event_id: count,
  stages: z.array(taskSchema).length(stageIds.length).refine(stages => new Set(stages.map(s => s.stage)).size === stageIds.length, "Invalid stage roster"),
  workers: z.array(taskSchema),
  metrics: z.object({ documents_total: count.nullable(), completed_workers: count, raw_findings: count, final_requirements: count.nullable() }),
  warnings: z.array(errorSchema), output: z.object({ excel_url: z.string().nullable() }),
  error: errorSchema.nullable(),
}).refine(snapshot => snapshot.status !== "completed" || !!snapshot.output.excel_url, "Completed workbook missing");
export const eventSchema = z.object({
  event_id: count.positive(), run_id: z.uuid(), type: z.string(), status: z.string(),
  stage: z.enum(stageIds).nullable(), worker_id: z.string().nullable(), timestamp,
  duration_ms: count.nullable(), summary: z.string(), data: z.record(z.string(), z.union([z.string(), count])),
}).superRefine((event, context) => {
  if (event.type.startsWith("worker.") && (!event.worker_id || !event.stage)) context.addIssue({ code: "custom", message: "Worker identity missing" });
  if (event.type.startsWith("stage.") && !event.stage) context.addIssue({ code: "custom", message: "Stage identity missing" });
});
export const inputsSchema = z.array(z.object({ id: z.string(), display_name: z.string(), size_bytes: count.nullable(), available: z.boolean() }));
export const startSchema = z.object({ run_id: z.uuid(), status: z.enum(["queued", "running", "completed", "failed"]), snapshot_url: z.string(), events_url: z.string() });
export type RunSnapshot = z.infer<typeof snapshotSchema>;
export type RunEvent = z.infer<typeof eventSchema>;
export type TaskSnapshot = z.infer<typeof taskSchema>;
export type DemoInput = z.infer<typeof inputsSchema>[number];
export type StageId = typeof stageIds[number];
export const stageLabels: Record<StageId, string> = {
  extract: "Extract requirements", reconcile: "Reconcile duplicates", resolve: "Resolve references",
  classify: "Classify obligations", export: "Build Excel matrix",
};
export const stageTalkingPoints: Record<StageId, string> = {
  extract: "The agent reads each PDF and captures candidate requirements with source evidence.",
  reconcile: "It compares candidates across documents so the same obligation is not counted twice.",
  resolve: "It checks amendments and references to see which wording applies to the package.",
  classify: "It determines which source-backed items belong in the client compliance matrix.",
  export: "It adds source references and writes the downloadable Excel file.",
};
export const isTerminal = (snapshot: RunSnapshot) => ["completed", "failed"].includes(snapshot.status);
