import { useState } from "react";
import { categoryLabel, filterRequirements, type Analysis, type Filters, type Row } from "@/lib/requirements";
import { EvidencePanel } from "./evidence-panel";
export function TenderAnalysis({ analysis, rows, filters }: { analysis: Analysis; rows: Row[]; filters: Filters }) {
  const [category, setCategory] = useState("ALL");
  const filtered = filterRequirements(rows, filters).filter(row => category === "ALL" || row.category === category);
  const selected = analysis.categories.find(item => item.category === category);
  return <><div className="category-list" role="group" aria-label="Requirement categories"><button aria-pressed={category === "ALL"} onClick={() => setCategory("ALL")}>All categories</button>{analysis.categories.map(item => <button key={item.category} aria-pressed={category === item.category} onClick={() => setCategory(item.category)}>{categoryLabel(item.category)} <span>{item.requirements.length}</span></button>)}</div><p className="review-help">Category NOT_FOUND means no extracted evidence; it is not a waiver. Item status and requirement type are shown separately.</p>{selected && <p className="category-status">{categoryLabel(selected.category)} · Category status: <strong>{selected.status}</strong></p>}<p className="result-tally">{filtered.length} matching requirements</p>{filtered.length ? <div className="requirement-list">{filtered.map(row => <article key={row.id}><div className="requirement-meta"><span>{categoryLabel(row.category)}</span><span>Type: <strong>{row.requirement_type}</strong></span><span className={row.status === "EXTERNAL_REFERENCE" ? "external-status" : ""}>Status: <strong>{row.status}</strong></span></div><h3>{row.requirement}</h3><EvidencePanel item={row} /></article>)}</div> : <p className="review-empty">{selected?.status === "NOT_FOUND" ? "No evidence was extracted for this category. Review the original tender." : "No requirements match the current filters."}</p>}</>;
}

