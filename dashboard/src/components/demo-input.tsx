import { useRef } from "react";
import { ArrowRight, Eye, FileText, LoaderCircle, Upload } from "lucide-react";
import type { DemoInput } from "@/lib/contracts";
import { tenderUrl } from "@/lib/api";

interface Props {
  inputs: DemoInput[]; active: boolean; starting: boolean; recover: boolean;
  selection: { id: string; display_name: string; size_bytes: number } | null;
  uploading: boolean; uploadProblem: string | null;
  onStart: (id: string) => void; onUpload: (file: File) => void; onUseSample: () => void;
}

/** Keep the preview and Analyze action tied to the same selected PDF. */
export function DemoInputPanel({ inputs, active, starting, recover, selection, uploading, uploadProblem, onStart, onUpload, onUseSample }: Props) {
  const picker = useRef<HTMLInputElement>(null);
  const sample = inputs.find(item => item.id === "sample-tender");
  const selected = selection || sample;
  const available = !!selection || !!sample?.available;
  const size = selected?.size_bytes ? `${(selected.size_bytes / 1024 / 1024).toFixed(2)} MB` : "PDF document";
  const locked = active || uploading || recover;
  return <section className="input-panel" aria-labelledby="input-title">
    <div className="document-icon"><FileText size={28} strokeWidth={1.5} /><span>PDF</span></div>
    <div className="input-description"><div className="eyebrow" id="input-title">Selected tender</div>
      <h2 className="selected-filename">{selection?.display_name || "tender.pdf"}</h2>
      <div className="document-meta"><span>{size}</span><span className="file-tag">{selection ? "Your upload" : "Sample"}</span>
        {selection && <button className="text-button" disabled={locked} onClick={onUseSample}>Use sample tender</button>}
      </div>
      <p className="selection-help">Upload your tender, or analyze the sample tender.pdf.</p>
      {!selection && sample && !sample.available && <p className="error-text">The sample tender is unavailable. You can upload your own PDF.</p>}
      {uploadProblem && <p className="error-text" role="alert">{uploadProblem}</p>}
      <input ref={picker} className="sr-only" type="file" accept=".pdf,application/pdf" aria-label="Upload tender PDF" disabled={locked}
        onChange={event => { const file = event.currentTarget.files?.[0]; if (file) onUpload(file); event.currentTarget.value = ""; }} />
    </div>
    <div className="input-action">
      {available && <a className="secondary-button view-tender" href={tenderUrl(selected!.id)} target="_blank" rel="noopener noreferrer"><Eye size={16} />View Tender</a>}
      <div className="tender-buttons"><button className="secondary-button" disabled={locked} onClick={() => picker.current?.click()}>
        {uploading ? <LoaderCircle size={16} className="spin" /> : <Upload size={16} />}{uploading ? "Uploading…" : "Upload Tender"}
      </button><button className="primary-button" disabled={active || uploading || (!available && !recover)} onClick={() => onStart(selected?.id || "sample-tender")}>
        {starting ? <LoaderCircle size={17} className="spin" /> : <ArrowRight size={17} />}
        {starting ? "Starting analysis…" : active ? "Analysis in progress" : recover ? "Recover run" : "Analyze"}
      </button></div>
      <span className="input-note" role="status">{uploading ? "Preparing your PDF…" : "Estimated analysis time: 5–10 minutes"}</span>
    </div>
  </section>;
}
