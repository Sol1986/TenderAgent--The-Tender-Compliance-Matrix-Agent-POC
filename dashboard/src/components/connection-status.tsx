import { RefreshCw } from "lucide-react";
import type { Connection } from "@/hooks/use-tender-run";

export function ConnectionStatus({ status, onRetry }: { status: Connection; onRetry: () => void }) {
  const labels = { checking: "Connecting", connected: "API connected", live: "Live connection", reconnecting: "Reconnecting", offline: "Disconnected" };
  return <div className="connection-group"><span className={`connection connection-${status}`} role="status"><span className="connection-dot" />{labels[status]}</span>
    {["offline", "reconnecting"].includes(status) && <button className="icon-button" onClick={onRetry} title="Reconnect to backend" aria-label="Reconnect to backend"><RefreshCw size={15} /></button>}</div>;
}
