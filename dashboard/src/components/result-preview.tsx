import { Download, FileSpreadsheet } from "lucide-react";
import { apiBase } from "@/lib/api";
import type { RunSnapshot } from "@/lib/contracts";

export function ResultPreview({ snapshot }: { snapshot: RunSnapshot | null }) {
  const ready = snapshot?.status === "completed" && snapshot.output.excel_url;
  return <section className="panel result-panel" id="result" aria-labelledby="result-title"><div className="panel-heading"><div><div className="eyebrow">The deliverable</div><h2 id="result-title">Excel compliance matrix</h2></div><FileSpreadsheet size={21} strokeWidth={1.5} /></div>
    {ready ? <div className="result-content"><div className="result-count"><strong>{snapshot.metrics.final_requirements ?? "—"}</strong><span>requirements classified</span></div><p className="result-pending">The source-backed compliance matrix is ready for your team to assign and complete.</p><a className="download-button" href={`${apiBase()}${snapshot.output.excel_url}`} download="compliance_matrix.xlsx"><Download size={18} /> Download Excel matrix</a></div>
      : <div className="result-empty"><div className="result-illustration"><FileSpreadsheet size={34} strokeWidth={1.2} /></div><h3>{snapshot?.status === "failed" ? "Matrix unavailable" : "Your Excel matrix is being prepared"}</h3><p>{snapshot?.status === "failed" ? "This run did not finish, so there is no completed workbook to download." : "Follow the live steps as the agent extracts and reconciles requirements. The download appears when the workbook is complete."}</p></div>}
  </section>;
}
