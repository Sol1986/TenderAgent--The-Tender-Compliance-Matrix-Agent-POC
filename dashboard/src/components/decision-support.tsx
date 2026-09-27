import type { Report } from "@/lib/requirements";
const sections = [
  ["reasons_to_consider_bidding", "Reasons to consider bidding"],
  ["concerns_and_risks", "Concerns and risks"],
  ["missing_information", "Missing information"],
  ["mandatory_requirements", "Mandatory requirements"],
  ["conditional_requirements", "Conditional requirements"],
  ["external_references_to_review", "External references to review"],
  ["questions_for_bid_team", "Questions for the bid team"],
] as const;
export function DecisionSupport({ report, onReview }: { report: Report; onReview: () => void }) {
  return <><div className="executive-report"><span className="eyebrow">Decision brief</span><h3>Executive summary</h3><p>{report.executive_summary || "No executive summary was returned."}</p></div><div className="report-sections">{sections.map(([key, label]) => <section key={key}><h3>{label}</h3>{report[key].length ? <ul>{report[key].map((text, index) => <li key={index}>{text}</li>)}</ul> : <p className="review-help">No items were returned in this section. This does not establish that the tender has no relevant obligations or risks.</p>}</section>)}</div><div className="review-callout"><p>Report bullets summarize the analysis. Use the structured requirements to inspect source evidence; bullet counts are not compliance totals.</p><button className="review-button" onClick={onReview}>Review structured evidence</button></div></>;
}

