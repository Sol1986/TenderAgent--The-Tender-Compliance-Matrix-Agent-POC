import { ArrowRight, FileScan, GitMerge, Link2, ListChecks, Sheet } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { stageIds, stageLabels, stageTalkingPoints, type RunSnapshot, type StageId } from "@/lib/contracts";
import { formatDuration } from "@/lib/run-state";
import { StatusBadge } from "./ui";

const icons: Record<StageId, LucideIcon> = { extract: FileScan, reconcile: GitMerge, resolve: Link2, classify: ListChecks, export: Sheet };

export function WorkflowGraph({ snapshot }: { snapshot: RunSnapshot | null }) {
  return <section className="panel workflow-panel" id="workflow" aria-labelledby="workflow-title">
    <div className="panel-heading"><div><div className="eyebrow">The process</div><h2 id="workflow-title">Agent workflow</h2></div><span className="quiet-label"><span className="tiny-dot" /> Observed execution</span></div>
    <div className="workflow-grid">
      {stageIds.map((id, index) => {
        const stage = snapshot?.stages.find(item => item.id === id);
        const Icon = icons[id];
        return <div className="workflow-step" key={id}>
          {index > 0 && <ArrowRight className="flow-arrow" size={19} aria-hidden />}
          <div className={`workflow-node node-${stage?.status || "pending"}`} data-stage={id} data-status={stage?.status || "pending"}>
            <div className="node-top"><span className="node-icon"><Icon size={21} strokeWidth={1.6} /></span><span className="node-number">{String(index + 1).padStart(2, "0")}</span></div>
            <h3>{stageLabels[id]}</h3><p>{stageTalkingPoints[id]}</p>
            <div className="node-footer"><StatusBadge status={stage?.status || "pending"} />{stage?.duration_ms !== null && stage?.duration_ms !== undefined && <span className="node-duration">{formatDuration(stage.duration_ms)}</span>}</div>
          </div>
        </div>;
      })}
    </div>
    <div className="workflow-caption"><span><span className="legend-dot complete" />Completed</span><span><span className="legend-dot running" />Running</span><span><span className="legend-dot waiting" />Waiting</span><p>Each step reflects a real phase of the package workflow.</p></div>
  </section>;
}
