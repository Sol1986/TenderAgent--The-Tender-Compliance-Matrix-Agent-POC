import { useRef, useState, type KeyboardEvent } from "react";
import type { RunSnapshot } from "@/lib/contracts";
import { emptyFilters, requirementRows } from "@/lib/requirements";
import { DecisionSupport } from "./decision-support";
import { SummaryMetrics } from "./summary-metrics";
import { TenderAnalysis } from "./tender-analysis";
import { RequirementFilters } from "./requirement-filters";
import { ComplianceMatrix } from "./compliance-matrix";
import { RawJsonPanel } from "./raw-json-panel";
const tabs = ["Decision Support", "Tender Analysis", "Compliance Matrix"] as const;
type Tab = typeof tabs[number];
export function ResultTabs({ snapshot }: { snapshot: RunSnapshot }) {
  const [tab, setTab] = useState<Tab>("Decision Support");
  const [filters, setFilters] = useState(emptyFilters);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const analysis = snapshot.output.tender_analysis;
  const report = snapshot.output.decision_support_report;
  const rows = analysis ? requirementRows(analysis) : [];
  const select = (index: number): void => { setTab(tabs[index]); buttons.current[index]?.focus(); };
  const onKey = (event: KeyboardEvent, index: number): void => {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
    if (next !== null) { event.preventDefault(); select(next); }
  };
  return <section className="panel review-panel" id="result" aria-labelledby="result-title"><div className="panel-heading"><div><div className="eyebrow">The outcome</div><h2 id="result-title">Tender review</h2></div><span className="number-pill">{snapshot.status === "completed" ? "Ready for human review" : "Partial output"}</span></div><div className="review-body">
    {snapshot.status === "failed" && <div className="notice error-notice" role="alert"><p>Incomplete analysis. The run failed; available output is retained for inspection. A complete decision-support report is unavailable.</p></div>}
    {analysis && <SummaryMetrics rows={rows} />}
    <div className="review-tabs" role="tablist" aria-label="Result views">{tabs.map((name, index) => <button ref={element => { buttons.current[index] = element; }} key={name} id={`result-tab-${index}`} role="tab" aria-selected={tab === name} aria-controls={`result-panel-${index}`} tabIndex={tab === name ? 0 : -1} onClick={() => setTab(name)} onKeyDown={event => onKey(event, index)}>{name}</button>)}</div>
    {tabs.map((name, index) => <div key={name} role="tabpanel" id={`result-panel-${index}`} aria-labelledby={`result-tab-${index}`} hidden={tab !== name} tabIndex={0}>
      {name === "Decision Support" ? report ? <DecisionSupport report={report} onReview={() => select(1)} /> : <div className="review-empty"><p>{snapshot.status === "failed" ? "The decision-support report could not be completed." : "The decision-support report is being prepared."}</p>{analysis && <button className="review-button" onClick={() => select(1)}>Review available requirements</button>}</div>
        : analysis ? <><RequirementFilters value={filters} onChange={setFilters} />{name === "Tender Analysis" ? <TenderAnalysis analysis={analysis} rows={rows} filters={filters} /> : <ComplianceMatrix rows={rows} filters={filters} />}</> : <p className="review-empty">Structured requirements are not available yet.</p>}
    </div>)}
    <RawJsonPanel output={snapshot.output} /></div><div className="human-note"><p>Decision support only. <strong>Your team makes the final Bid / No-Bid decision.</strong></p></div></section>;
}

