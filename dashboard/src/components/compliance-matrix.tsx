import { categoryLabel, filterRequirements, type Filters, type Row } from "@/lib/requirements";
import { EvidencePanel } from "./evidence-panel";
export function ComplianceMatrix({ rows, filters }: { rows: Row[]; filters: Filters }) {
  const filtered = filterRequirements(rows, filters);
  return <><p className="review-help">An evidence review checklist derived from the same consolidated requirements. Company compliance has not been assessed. NOT_REQUIRED records an extracted statement; verify it in context.</p><p className="result-tally">{filtered.length} matching requirements</p>{filtered.length ? <div className="matrix-scroll" tabIndex={0} role="region" aria-label="Compliance matrix table"><table className="compliance-table"><caption>Extracted requirements for human review</caption><thead><tr><th scope="col">Category</th><th scope="col">Requirement &amp; evidence</th><th scope="col">Type</th><th scope="col">Extraction status</th></tr></thead><tbody>{filtered.map(row => <tr key={row.id}><td>{categoryLabel(row.category)}</td><td>{row.requirement}<EvidencePanel item={row} /></td><td>{row.requirement_type}</td><td className={row.status === "EXTERNAL_REFERENCE" ? "external-status" : ""}>{row.status}</td></tr>)}</tbody></table></div> : <p className="review-empty">No requirements match the current filters.</p>}</>;
}

