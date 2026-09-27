import type { Requirement } from "@/lib/requirements";
export function EvidencePanel({ item }: { item: Requirement }) {
  return <details className="evidence"><summary>Source &amp; evidence</summary><h4>Source sections</h4>{item.source_sections.length ? <ul>{item.source_sections.map((source, index) => <li key={index}>{source}</li>)}</ul> : <p>No source section was returned.</p>}<h4>Extracted evidence</h4>{item.evidence.length ? <ul>{item.evidence.map((text, index) => <li key={index}>{text}</li>)}</ul> : <p>No evidence text was returned.</p>}<p className="review-help">Evidence may be paraphrased by the agent. Check the original tender and incorporated documents before relying on it.</p></details>;
}

