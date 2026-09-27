import { Clock3, Hash } from "lucide-react";
import type { RunSnapshot } from "@/lib/contracts";
import { formatDuration } from "@/lib/run-state";
import { StatusBadge } from "./ui";

export function RunHeader({ snapshot, runId, elapsed }: { snapshot: RunSnapshot | null; runId: string | null; elapsed: number | null }) {
  const metric = snapshot?.metrics;
  return <>
    <div className="run-meta"><div className="run-identity"><StatusBadge status={snapshot?.status || (runId ? "queued" : "ready")} />
      <span className="run-id" title={runId || undefined}><Hash size={12} />{runId ? `Run ${runId.slice(0, 8)}` : "No run started"}</span></div>
      <span className="elapsed"><Clock3 size={14} />{elapsed === null ? "Elapsed time appears during analysis" : `Elapsed ${formatDuration(elapsed)}`}</span></div>
    <div className="metrics-grid">
      <Metric label="Text chunks" value={metric?.text_chunks} description="Sections prepared for analysis" number="01" />
      <Metric label="Structured tables" value={metric?.tables} description="Tables extracted by Docling" number="02" />
      <Metric label="Workers completed" value={metric && metric.text_chunks !== null && metric.tables !== null ? `${metric.completed_workers} / ${metric.text_chunks + metric.tables}` : null} description="Text and table tasks finished" number="03" />
      <Metric label="Raw findings" value={snapshot?.started_at ? metric?.raw_findings : null} description="Before semantic consolidation" number="04" />
    </div>
  </>;
}

function Metric({ label, value, description, number }: { label: string; value: number | string | null | undefined; description: string; number: string }) {
  return <div className="metric"><div className="metric-label">{label}<span>{number}</span></div><strong className="metric-value">{value ?? "—"}</strong><p>{description}</p></div>;
}
