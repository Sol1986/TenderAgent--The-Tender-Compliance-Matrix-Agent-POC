import { Clock3, Hash } from "lucide-react";
import type { RunSnapshot } from "@/lib/contracts";
import { formatDuration } from "@/lib/run-state";
import { StatusBadge } from "./ui";

export function RunHeader({ snapshot, runId, elapsed }: { snapshot: RunSnapshot | null; runId: string | null; elapsed: number | null }) {
  const metric = snapshot?.metrics;
  return <><div className="run-meta"><div className="run-identity"><StatusBadge status={snapshot?.status || (runId ? "queued" : "ready")} /><span className="run-id" title={runId || undefined}><Hash size={12} />{runId ? `Run ${runId.slice(0, 8)}` : "No run started"}</span></div><span className="elapsed"><Clock3 size={14} />{elapsed === null ? "Elapsed time appears during analysis" : `Elapsed ${formatDuration(elapsed)}`}</span></div>
    <div className="metrics-grid"><Metric label="PDFs discovered" value={metric?.documents_total} description="Documents in this package" number="01" /><Metric label="PDFs processed" value={metric?.completed_workers} description="Extraction tasks completed" number="02" /><Metric label="Candidate findings" value={snapshot?.started_at ? metric?.raw_findings : null} description="Before package reconciliation" number="03" /><Metric label="Matrix requirements" value={metric?.final_requirements} description="Classified requirements" number="04" /></div>
  </>;
}

function Metric({ label, value, description, number }: { label: string; value: number | null | undefined; description: string; number: string }) {
  return <div className="metric"><div className="metric-label">{label}<span>{number}</span></div><strong className="metric-value">{value ?? "—"}</strong><p>{description}</p></div>;
}
