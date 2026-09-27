import { Activity, Check, Clock3, OctagonAlert, Play, TriangleAlert } from "lucide-react";
import type { RunEvent, RunSnapshot } from "@/lib/contracts";
import { stageLabels } from "@/lib/contracts";
import { formatDuration } from "@/lib/run-state";

export function EventTimeline({ events, snapshot }: { events: RunEvent[]; snapshot: RunSnapshot | null }) {
  return <section className="panel timeline-panel" id="activity" aria-labelledby="activity-title"><div className="panel-heading"><div><div className="eyebrow">Run observability</div><h2 id="activity-title">Execution timeline</h2></div><span className="number-pill">{events.length} updates</span></div>
    <p className="panel-description">Actual execution events, in the order they occurred.</p>
    {events.length ? <ol className="timeline">{events.map(event => {
      const completed = event.type.endsWith("completed");
      const failed = event.type.endsWith("failed");
      const warning = event.type === "run.warning";
      const Icon = completed ? Check : failed ? OctagonAlert : warning ? TriangleAlert : Play;
      const tone = failed ? "failed" : warning ? "warning" : completed ? "completed" : "started";
      const title = event.worker_id ? `${event.worker_id} ${event.type.split(".")[1]}` : event.stage ? `${stageLabels[event.stage]} · ${event.type.split(".")[1]}` : event.type === "run.started" ? "Analysis started" : event.type === "run.completed" ? "Analysis complete" : event.type === "run.failed" ? "Analysis failed" : "Preparation notice";
      return <li key={event.event_id} className={`timeline-item event-${tone}`}><span className="event-icon"><Icon size={13} /></span><details><summary><span className="event-title">{title}</span><time dateTime={event.timestamp}>{event.timestamp.slice(11, 19)} UTC</time></summary><p>{event.summary}</p><div className="event-detail">Event {event.event_id}{event.duration_ms !== null && <> · Duration {formatDuration(event.duration_ms)}</>}{typeof event.data.findings_count === "number" && <> · {event.data.findings_count} raw findings</>}</div></details></li>;
    })}</ol> : <div className="timeline-empty"><span><Activity size={26} strokeWidth={1.4} /></span><h3>{snapshot ? "Current run synchronized" : "A clear record of every step"}</h3><p>{snapshot ? "Stage and worker results reflect the latest backend snapshot. New events will appear here while this run continues." : "Start an analysis to follow document processing, worker activity, and report generation in real time."}</p><span className="empty-note"><Clock3 size={13} />Measured timings. No simulated progress.</span></div>}
    {events.length > 0 && <div className="timeline-footnote">Showing activity received during this connection. Expand an event for details.</div>}
  </section>;
}
