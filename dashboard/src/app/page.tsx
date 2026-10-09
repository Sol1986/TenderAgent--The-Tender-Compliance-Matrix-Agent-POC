"use client";

import { Activity, ArrowUpRight, FileSpreadsheet, Layers3, LayoutDashboard, Radio, TriangleAlert } from "lucide-react";
import { useTenderRun } from "@/hooks/use-tender-run";
import { ConnectionStatus } from "@/components/connection-status";
import { DemoInputPanel } from "@/components/demo-input";
import { RunHeader } from "@/components/run-header";
import { WorkflowGraph } from "@/components/workflow-graph";
import { WorkerLanes } from "@/components/worker-lanes";
import { EventTimeline } from "@/components/event-timeline";
import { ResultPreview } from "@/components/result-preview";
import { stageLabels, stageTalkingPoints, type StageId } from "@/lib/contracts";

export default function Dashboard() {
  const run = useTenderRun();
  const current = run.snapshot?.stages.find(stage => stage.status === "running");
  const currentId = current?.id as StageId | undefined;
  return <div className="app-shell"><a href="#main" className="skip-link">Skip to workspace</a>
    <aside className="sidebar"><a href="#main" className="brand"><span className="brand-mark"><Layers3 size={23} /></span><span>Tender<span className="brand-light">Agent</span><small>COMPLIANCE MATRIX</small></span></a>
      <div className="nav-label">Workspace</div><nav aria-label="Workspace navigation"><a href="#workflow" className="nav-item nav-active"><LayoutDashboard size={18} />Live workflow<span className="nav-dot" /></a><a href="#workers" className="nav-item"><Layers3 size={18} />Document activity</a><a href="#activity" className="nav-item"><Activity size={18} />Execution timeline</a><a href="#result" className="nav-item"><FileSpreadsheet size={18} />Excel download</a></nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><FileSpreadsheet size={20} /><h3>One clear deliverable.</h3><p>A source-backed Excel compliance matrix for the proposal team.</p></div><div className="demo-mark"><span /> Client demonstration</div></div>
    </aside>
    <div className="workspace"><header className="topbar"><span className="breadcrumb">Workspace <span>/</span> <strong>Compliance matrix</strong></span><div className="topbar-right"><ConnectionStatus status={run.connection} onRetry={run.reconnect} /><span className="avatar" title="Proposal team">PT</span></div></header>
      <main id="main"><div className="page-heading"><div><div className="eyebrow"><Radio size={13} /> Tender requirements, made clear</div><h1>Compliance matrix</h1>
        <p>This agent identifies your tender’s requirements and turns them into a compliance matrix to help your team decide whether to bid or not bid. Allow approximately 5–10 minutes, depending on the size of the tender.</p>
        <p>Get results at a fraction of the cost of manual review, with the potential to save tens of thousands of dollars in engineering and coordinator costs across your tender pipeline. Free up your team to bid on more tenders and pursue more revenue.</p>
        <p>The process below shows how it works. When the analysis finishes, download your Excel spreadsheet with the compliance matrix and review the requirements with your team.</p>
      </div></div>
        {run.problem && <div className="notice error-notice" role="alert"><TriangleAlert size={20} /><div><strong>{run.problem.code === "RUN_NOT_FOUND" ? "Run no longer available" : "Connection needs attention"}</strong><p>{run.problem.message}</p></div>{["RUN_NOT_FOUND", "INVALID_RUN"].includes(run.problem.code) ? <button onClick={run.clearRun}>New analysis <ArrowUpRight size={14} /></button> : <button onClick={run.reconnect}>Retry connection</button>}</div>}
        {run.connection === "reconnecting" && <div className="notice" role="status"><Radio size={19} /><p>Reconnecting to this run. The agent may still be processing; no new analysis will start.</p></div>}
        {run.snapshot?.error && <div className="notice error-notice" role="alert"><TriangleAlert size={20} /><div><strong>Analysis could not finish</strong><p>{run.snapshot.error.message}</p></div></div>}
        <DemoInputPanel inputs={run.inputs} active={run.active} starting={run.starting} recover={!!run.pending} selection={run.selection} uploading={run.uploading} uploadProblem={run.uploadProblem} onUpload={run.upload} onUseSample={run.useSample} onStart={run.start} />
        <RunHeader snapshot={run.snapshot} runId={run.runId} elapsed={run.elapsed} />
        {currentId && <section className="presenter-note" aria-live="polite"><span>While this runs, explain</span><strong>{stageLabels[currentId]}</strong><p>{stageTalkingPoints[currentId]}</p></section>}
        <WorkflowGraph snapshot={run.snapshot} />
        {!!run.snapshot?.warnings.length && <details className="preparation-notice"><summary><TriangleAlert size={16} /><span>Processing notes</span><span className="number-pill">{run.snapshot.warnings.length}</span></summary>{run.snapshot.warnings.map((warning, index) => <p key={`${warning.code}-${index}`}>{warning.message}</p>)}</details>}
        <WorkerLanes snapshot={run.snapshot} />
        <div className="bottom-grid"><EventTimeline events={run.events} snapshot={run.snapshot} /><ResultPreview snapshot={run.snapshot} /></div>
        <footer className="page-footer"><span>Tender Agent <span> / </span> Client demonstration</span><span>Observed steps. Excel deliverable.</span></footer>
      </main>
    </div>
  </div>;
}
