import { ChevronDown, Rows3, TextSearch } from "lucide-react";
import { useState } from "react";
import type { RunSnapshot, StageId } from "@/lib/contracts";
import { formatDuration } from "@/lib/run-state";
import { StatusBadge } from "./ui";

export function WorkerLanes({ snapshot }: { snapshot: RunSnapshot | null }) {
  return <section className="worker-section" id="workers" aria-labelledby="workers-title"><div className="section-heading"><div><div className="eyebrow">Inside the execution</div><h2 id="workers-title">Worker activity</h2></div><span className="quiet-label">Independent tasks · shared findings</span></div>
    <div className="worker-grid"><Lane stage="analyze_chunk" snapshot={snapshot} /><Lane stage="analyze_table" snapshot={snapshot} /></div>
  </section>;
}

function Lane({ stage, snapshot }: { stage: StageId; snapshot: RunSnapshot | null }) {
  const [expanded, setExpanded] = useState(false);
  const text = stage === "analyze_chunk";
  const Icon = text ? TextSearch : Rows3;
  const workers = (snapshot?.workers || []).filter(worker => worker.stage === stage);
  const total = (text ? snapshot?.metrics.text_chunks : snapshot?.metrics.tables) ?? null;
  const done = workers.filter(worker => worker.status === "completed").length;
  const running = workers.filter(worker => worker.status === "running").length;
  const ordered = [...workers].sort((a, b) => {
    const rank = { running: 0, failed: 1, pending: 2, completed: 3, skipped: 4 };
    return rank[a.status] - rank[b.status] || a.id.localeCompare(b.id, undefined, { numeric: true });
  });
  return <div className="panel worker-lane"><div className="lane-heading"><div className="lane-title"><span className="lane-icon"><Icon size={19} /></span><div><h3>{text ? "Text workers" : "Table workers"}</h3><p>{text ? "Section-by-section extraction" : "Structured table extraction"}</p></div></div><span className="worker-count">{total === null ? "—" : `${done}/${total}`}</span></div>
    <div className="worker-progress" role="progressbar" aria-label={`${text ? "Text" : "Table"} workers completed`} aria-valuemin={0} aria-valuemax={total || 1} aria-valuenow={total === null ? undefined : done}><span style={{ width: total ? `${Math.min(100, done / total * 100)}%` : "0%" }} /></div>
    <div className="lane-meta"><span>{total === null ? "Waiting for prepared inputs" : total === 0 ? "No inputs for this branch" : `${running} running · ${done} completed`}</span><span>{total === null ? "" : `${total} total`}</span></div>
    {workers.length ? <ul className="worker-list">{(expanded ? ordered : ordered.slice(0, 4)).map(worker => <li key={worker.id}>
      <div className="worker-info"><span className="worker-id">{worker.id}</span><span className="worker-label" title={worker.label}>{worker.label}</span><span className="worker-finding">{worker.findings_count === null ? "Awaiting findings" : `${worker.findings_count} raw finding${worker.findings_count === 1 ? "" : "s"}`}</span></div>
      <div className="worker-state"><StatusBadge status={worker.status} /><span>{formatDuration(worker.duration_ms)}</span></div>
    </li>)}</ul> : <div className="lane-empty"><Icon size={27} strokeWidth={1.2} /><p>{total === 0 ? "This branch has no work to process." : `${text ? "Text sections" : "Extracted tables"} will appear here once the document is prepared.`}</p></div>}
    {workers.length > 4 && <button className="expand-workers" onClick={() => setExpanded(value => !value)} aria-expanded={expanded}>{expanded ? "Show fewer workers" : `Show all ${workers.length} workers`}<ChevronDown size={14} className={expanded ? "rotate" : ""} /></button>}
  </div>;
}
