import { FileText } from "lucide-react";
import type { RunSnapshot } from "@/lib/contracts";
import { StatusBadge } from "./ui";

export function WorkerLanes({ snapshot }: { snapshot: RunSnapshot | null }) {
  const workers = snapshot?.workers || [];
  return <section className="worker-section" id="workers" aria-labelledby="workers-title">
    <div className="section-heading"><div><div className="eyebrow">Inside extraction</div><h2 id="workers-title">Documents in the package</h2></div><span className="quiet-label">Real document activity</span></div>
    <div className="panel document-panel">
      {workers.length ? <ul className="worker-list">{workers.map(worker => <li key={worker.id}>
        <div className="worker-info"><span className="worker-label"><FileText size={15} /> {worker.label}</span><span className="worker-finding">{worker.status === "failed" ? "Could not process this PDF" : worker.findings_count === null ? "Awaiting extraction" : `${worker.findings_count} candidate findings`}</span></div>
        <div className="worker-state"><StatusBadge status={worker.status} /></div>
      </li>)}</ul> : <div className="lane-empty"><FileText size={27} strokeWidth={1.2} /><p>Source PDFs will appear as the agent begins extraction.</p></div>}
    </div>
  </section>;
}
