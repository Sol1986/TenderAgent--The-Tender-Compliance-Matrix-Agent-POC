import type { RunSnapshot } from "@/lib/contracts";
export function RawJsonPanel({ output }: { output: RunSnapshot["output"] }) {
  return <details className="raw-json"><summary>Structured output JSON</summary><p className="review-help">The two returned agent outputs, shown separately for inspection.</p><pre tabIndex={0}>{JSON.stringify(output, null, 2)}</pre></details>;
}

