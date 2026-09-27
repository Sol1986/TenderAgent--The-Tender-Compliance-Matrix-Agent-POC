import { ArrowRight, FileScan, GitMerge, Layers3, ListChecks, Rows3, TextSearch } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { stageLabels, type RunSnapshot, type StageId } from "@/lib/contracts";
import { formatDuration } from "@/lib/run-state";
import { StatusBadge } from "./ui";

function Node({ id, number, Icon, description, snapshot }: { id: StageId; number: string; Icon: LucideIcon; description: string; snapshot: RunSnapshot | null }) {
    const stage = snapshot?.stages.find(item => item.id === id);
    const status = stage?.status || "pending";
    return <div className={`workflow-node node-${status}`} data-stage={id} data-status={status}>
      <div className="node-top"><span className="node-icon"><Icon size={21} strokeWidth={1.6} /></span><span className="node-number">{number}</span></div>
      <h3>{stageLabels[id]}</h3><p>{description}</p>
      <div className="node-footer"><StatusBadge status={status} />{stage?.duration_ms !== null && stage?.duration_ms !== undefined && <span className="node-duration">{formatDuration(stage.duration_ms)}</span>}</div>
    </div>;
  }
export function WorkflowGraph({ snapshot }: { snapshot: RunSnapshot | null }) {
  return <section className="panel workflow-panel" id="workflow" aria-labelledby="workflow-title">
    <div className="panel-heading"><div><div className="eyebrow">The process</div><h2 id="workflow-title">Agent workflow</h2></div><span className="quiet-label"><span className="tiny-dot" /> Observed execution</span></div>
    <div className="workflow-grid">
      <Node snapshot={snapshot} id="parse_document" number="01" Icon={FileScan} description="Read the PDF with Docling" />
      <ArrowRight className="flow-arrow" size={19} aria-hidden />
      <Node snapshot={snapshot} id="prepare_inputs" number="02" Icon={Layers3} description="Prepare sections and tables" />
      <ArrowRight className="flow-arrow" size={19} aria-hidden />
      <div className="parallel-group"><div className="parallel-label">Parallel extraction</div>
        <Node snapshot={snapshot} id="analyze_chunk" number="03a" Icon={TextSearch} description="Extract section requirements" />
        <Node snapshot={snapshot} id="analyze_table" number="03b" Icon={Rows3} description="Extract table requirements" />
      </div>
      <ArrowRight className="flow-arrow" size={19} aria-hidden />
      <Node snapshot={snapshot} id="reduce_findings" number="04" Icon={GitMerge} description="Combine and deduplicate" />
      <ArrowRight className="flow-arrow" size={19} aria-hidden />
      <Node snapshot={snapshot} id="generate_report" number="05" Icon={ListChecks} description="Prepare decision support" />
    </div>
    <div className="workflow-caption"><span><span className="legend-dot complete" />Completed</span><span><span className="legend-dot running" />Running</span><span><span className="legend-dot waiting" />Waiting</span>
      <p>Text and table branches join before consolidation begins.</p></div>
  </section>;
}
