import { Check, Circle, LoaderCircle, Minus, X } from "lucide-react";
import type { TaskSnapshot } from "@/lib/contracts";

export function StatusBadge({ status }: { status: TaskSnapshot["status"] | "queued" | "ready" }) {
  const Icon = status === "completed" ? Check : status === "failed" ? X : status === "running" ? LoaderCircle : status === "skipped" ? Minus : Circle;
  const label = { completed: "Completed", failed: "Failed", running: "Running", pending: "Waiting", queued: "Queued", skipped: "Skipped", ready: "Ready" }[status];
  return <span className={`status-badge status-${status}`}><Icon size={12} className={status === "running" ? "spin" : ""} aria-hidden />{label}</span>;
}
