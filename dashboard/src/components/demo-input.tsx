import { ArrowRight, FileText, LoaderCircle, LockKeyhole } from "lucide-react";
import type { DemoInput } from "@/lib/contracts";

interface Props { inputs: DemoInput[]; active: boolean; starting: boolean; recover: boolean; completed: boolean; onStart: (id: string) => void }
export function DemoInputPanel({ inputs, active, starting, recover, completed, onStart }: Props) {
  const input = inputs.find(item => item.id === "sample-tender");
  const size = input?.size_bytes ? `${(input.size_bytes / 1024 / 1024).toFixed(2)} MB` : null;
  return <section className="input-panel" aria-labelledby="input-title">
    <div className="document-icon"><FileText size={28} strokeWidth={1.5} /><span>PDF</span></div>
    <div className="input-description"><div className="eyebrow" id="input-title">Selected package</div>
      <label className="sr-only" htmlFor="sample-input">Tender package</label>
      <select id="sample-input" value={input?.id || ""} disabled={active || !input} onChange={() => {}}>
        <option value={input?.id || ""}>{input?.display_name || "Loading sample tender…"}</option>
      </select>
      <div className="document-meta"><span>Government procurement</span><span className="separator">·</span><span>{size || "PDF package"}</span><span className="file-tag">Sample</span></div>
      {input && !input.available && <p className="error-text">The sample package is unavailable on the backend.</p>}
    </div>
    <div className="input-action"><button className="primary-button" disabled={active || !input?.available} onClick={() => input && onStart(input.id)}>
      {starting ? <LoaderCircle size={17} className="spin" /> : <ArrowRight size={17} />}
      {starting ? "Starting analysis…" : active ? "Analysis in progress" : recover ? "Recover run" : completed ? "Analyze again" : "Generate compliance matrix"}
    </button><span className="input-note"><LockKeyhole size={12} /> One live analysis at a time</span></div>
  </section>;
}
