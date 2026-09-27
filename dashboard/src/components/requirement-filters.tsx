import { useId } from "react";
import { emptyFilters, type Filters } from "@/lib/requirements";
export function RequirementFilters({ value, onChange }: { value: Filters; onChange: (value: Filters) => void }) {
  const id = useId();
  return <div className="requirement-filters"><label htmlFor={id}>Search requirements<input id={id} type="search" placeholder="Requirement, source, or evidence…" value={value.query} onChange={e => onChange({ ...value, query: e.target.value })} /></label><label htmlFor={id + "-type"}>Requirement type<select id={id + "-type"} value={value.type} onChange={e => onChange({ ...value, type: e.target.value })}><option value="ALL">All types</option><option value="MANDATORY">Mandatory</option><option value="CONDITIONAL">Conditional</option><option value="INFORMATIONAL">Informational</option></select></label><label className="checkbox-filter"><input type="checkbox" checked={value.externalOnly} onChange={e => onChange({ ...value, externalOnly: e.target.checked })} />External references only</label><button className="review-button" onClick={() => onChange(emptyFilters)}>Clear filters</button></div>;
}

