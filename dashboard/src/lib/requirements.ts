import type { RunSnapshot } from "./contracts";
export type Analysis = NonNullable<RunSnapshot["output"]["tender_analysis"]>;
export type Report = NonNullable<RunSnapshot["output"]["decision_support_report"]>;
export type Requirement = Analysis["categories"][number]["requirements"][number];
export type Category = Analysis["categories"][number]["category"];
export type Row = Requirement & { id: string; category: Category };
export type Filters = { query: string; type: string; externalOnly: boolean };
export const emptyFilters: Filters = { query: "", type: "ALL", externalOnly: false };
export const categoryLabel = (category: string): string => category.split("_").map(word => word[0].toUpperCase() + word.slice(1)).join(" ");
/** Positional UI identifiers are stable within this output, not model-supplied IDs. */
export function requirementRows(analysis: Analysis): Row[] {
  return analysis.categories.flatMap(category => category.requirements.map((item, index) => ({ ...item, category: category.category, id: `${category.category}-${index + 1}` })));
}
/** Type counts exclude explicit waivers; external references can overlap either type. */
export function requirementCounts(rows: Row[]): { mandatory: number; conditional: number; external: number; total: number } {
  return { total: rows.length, mandatory: rows.filter(r => r.requirement_type === "MANDATORY" && r.status !== "NOT_REQUIRED").length,
    conditional: rows.filter(r => r.requirement_type === "CONDITIONAL" && r.status !== "NOT_REQUIRED").length,
    external: rows.filter(r => r.status === "EXTERNAL_REFERENCE").length };
}
export function filterRequirements(rows: Row[], filters: Filters): Row[] {
  const query = filters.query.trim().toLocaleLowerCase();
  return rows.filter(row => (filters.type === "ALL" || row.requirement_type === filters.type)
    && (!filters.externalOnly || row.status === "EXTERNAL_REFERENCE")
    && (!query || [row.requirement, categoryLabel(row.category), ...row.source_sections, ...row.evidence].join(" ").toLocaleLowerCase().includes(query)));
}

