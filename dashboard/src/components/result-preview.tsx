import { ArrowUpRight, FileCheck2, ShieldCheck } from "lucide-react";
import type { RunSnapshot } from "@/lib/contracts";

export function ResultPreview({ snapshot }: { snapshot: RunSnapshot | null }) {
  const analysis = snapshot?.output.tender_analysis;
  const report = snapshot?.output.decision_support_report;
  return <section className="panel result-panel" id="result" aria-labelledby="result-title"><div className="panel-heading"><div><div className="eyebrow">The outcome</div><h2 id="result-title">Run summary</h2></div><FileCheck2 size={21} strokeWidth={1.5} /></div>
    {analysis || report ? <div className="result-content">
      <div className="result-count"><strong>{analysis?.categories.reduce((sum, category) => sum + category.requirements.length, 0) ?? "—"}</strong><span>consolidated requirements<br /><small>{analysis?.categories.length ?? "—"} categories reviewed</small></span></div>
      <span className="preview-label">Executive summary · preview</span>
      {report ? <p className="executive-preview">{report.executive_summary}</p> : <p className="result-pending">{snapshot?.status === "failed" ? "The analysis is available, but the decision-support report could not be completed." : "Findings are consolidated. The decision-support report is being prepared."}</p>}
      <p className="preview-note">This phase provides an output preview. Detailed requirements, evidence, and decision-support review views follow in the next phase.</p>
    </div> : <div className="result-empty"><div className="result-illustration"><FileCheck2 size={34} strokeWidth={1.2} /><ArrowUpRight size={16} /></div><h3>From findings to a clear summary</h3><p>Your consolidated requirements and report preview will appear here after analysis.</p><div className="output-line"><span>01</span> Structured tender analysis</div><div className="output-line"><span>02</span> Decision-support report</div></div>}
    <div className="human-note"><ShieldCheck size={18} /><p>Decision support only.<br /><strong>Your team makes the final Bid / No-Bid decision.</strong></p></div>
  </section>;
}
