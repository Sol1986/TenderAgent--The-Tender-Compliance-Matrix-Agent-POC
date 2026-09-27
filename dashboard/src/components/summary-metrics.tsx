import { requirementCounts, type Row } from "@/lib/requirements";
export function SummaryMetrics({ rows }: { rows: Row[] }) {
  const counts = requirementCounts(rows);
  return <><div className="review-metrics">{[["Consolidated requirements", counts.total], ["Mandatory", counts.mandatory], ["Conditional", counts.conditional], ["External references", counts.external]].map(([label, value]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div><p className="review-help">Mandatory and conditional counts exclude items marked NOT_REQUIRED. External references may overlap either count. These are extracted requirements, not company compliance scores.</p></>;
}

