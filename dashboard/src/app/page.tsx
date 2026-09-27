"use client";

import { Activity, ArrowUpRight, CircleHelp, FileCheck2, Layers3, LayoutDashboard, Radio, ShieldCheck, TriangleAlert } from "lucide-react";
import { useTenderRun } from "@/hooks/use-tender-run";
import { ConnectionStatus } from "@/components/connection-status";
import { DemoInputPanel } from "@/components/demo-input";
import { RunHeader } from "@/components/run-header";
import { WorkflowGraph } from "@/components/workflow-graph";
import { WorkerLanes } from "@/components/worker-lanes";
import { EventTimeline } from "@/components/event-timeline";
import { ResultPreview } from "@/components/result-preview";
import { ResultTabs } from "@/components/result-tabs";

export default function Dashboard() {
  const run = useTenderRun();
  return <div className="app-shell"><a href="#main" className="skip-link">Skip to workspace</a>
    <aside className="sidebar"><a href="#main" className="brand"><span className="brand-mark"><Layers3 size={23} /></span><span>Tender<span className="brand-light">Agent</span><small>INTELLIGENCE WORKSPACE</small></span></a>
      <div className="nav-label">Workspace</div><nav aria-label="Workspace navigation"><a href="#workflow" className="nav-item nav-active"><LayoutDashboard size={18} />Live overview<span className="nav-dot" /></a><a href="#workers" className="nav-item"><Layers3 size={18} />Worker activity</a><a href="#activity" className="nav-item"><Activity size={18} />Execution timeline</a><a href="#result" className="nav-item"><FileCheck2 size={18} />Run summary</a></nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={20} /><h3>Intelligence for your team.</h3><p>The agent surfaces the evidence.<br />You make the decision.</p></div><div className="demo-mark"><span /> Client demonstration</div></div>
    </aside>
    <div className="workspace"><header className="topbar"><span className="breadcrumb">Workspace <span>/</span> <strong>Tender analysis</strong></span><div className="topbar-right"><ConnectionStatus status={run.connection} onRetry={run.reconnect} /><span className="avatar" title="Proposal team">PT</span></div></header>
      <main id="main"><div className="page-heading"><div><div className="eyebrow"><Radio size={13} /> Live agent workspace</div><h1>Tender analysis, in focus.</h1><p>Follow the workflow. Understand the findings. Make an informed decision.</p></div><details className="about-demo"><summary><CircleHelp size={15} /> About this demo</summary><p>This live demo analyzes the included sample tender. Extracted content is sent to the configured model provider. Runs are temporary and are lost when the backend restarts.</p></details></div>
        {run.problem && <div className="notice error-notice" role="alert"><TriangleAlert size={20} /><div><strong>{run.problem.code === "RUN_NOT_FOUND" ? "Run no longer available" : "Connection needs attention"}</strong><p>{run.problem.message}</p></div>{["RUN_NOT_FOUND", "INVALID_RUN"].includes(run.problem.code) ? <button onClick={run.clearRun}>New analysis <ArrowUpRight size={14} /></button> : <button onClick={run.reconnect}>Retry connection</button>}</div>}
        {run.connection === "reconnecting" && <div className="notice" role="status"><Radio size={19} /><p>Reconnecting to this run. Processing may still be continuing on the backend; no new analysis will be started.</p></div>}
        {run.snapshot?.error && <div className="notice error-notice" role="alert"><TriangleAlert size={20} /><div><strong>Analysis could not finish</strong><p>{run.snapshot.error.message}</p></div></div>}
        <DemoInputPanel inputs={run.inputs} active={run.active} starting={run.starting} recover={!!run.pending} completed={!!run.snapshot && ["completed", "failed"].includes(run.snapshot.status)} onStart={run.start} />
        <RunHeader snapshot={run.snapshot} runId={run.runId} elapsed={run.elapsed} />
        <WorkflowGraph snapshot={run.snapshot} />
        {!!run.snapshot?.warnings.length && <details className="preparation-notice"><summary><TriangleAlert size={16} /><span>Preparation notes</span><span className="number-pill">{run.snapshot.warnings.length}</span><span className="notice-hint">Review prototype filtering</span></summary>{run.snapshot.warnings.map((warning, index) => <p key={`${warning.code}-${index}`}>{warning.message}</p>)}</details>}
        <WorkerLanes snapshot={run.snapshot} />
        {run.snapshot?.output.tender_analysis || run.snapshot?.output.decision_support_report ? <><div className="review-timeline"><EventTimeline events={run.events} snapshot={run.snapshot} /></div><ResultTabs key={run.snapshot.run_id} snapshot={run.snapshot} /></> : <div className="bottom-grid"><EventTimeline events={run.events} snapshot={run.snapshot} /><ResultPreview snapshot={run.snapshot} /></div>}
        <footer className="page-footer"><span>Tender Agent <span> / </span> Client demonstration</span><span>Evidence first. Human decision.</span></footer>
      </main>
    </div>
  </div>;
}
