---
name: agent-demo-dashboard
description: Build or adapt a live demonstration dashboard for an existing AI agent or graph, showing its real workflow, tools, decisions, parallel work, and final output. Use when a user wants a client-facing dashboard for an agent they have already built.
---

# Agent demo dashboard

Create a working, presentation-ready dashboard that lets someone start one agent run, watch its actual execution, and inspect the result. Adapt the dashboard to the new agent's graph and output. The company research dashboard is a reference pattern, not a template whose workers, stages, or report sections should be copied.

## Discover the agent first

Inspect the current repository, its instructions, entry points, graph definition, state, nodes, conditional edges, tool/API calls, output schema, tests, and deployment setup. If a frontend already exists, inspect its components and API adapter too. Establish:

- The exact user input and completed output, including files, links, or structured fields.
- The actual order of stages, branches, loops, parallel nodes, skipped work, and failure paths.
- Which steps call a model, which call external tools, and which are ordinary code. Distinguish LangGraph routing from an Agents SDK handoff or a model-selected tool call.
- What the runtime can observe during execution versus what would require instrumentation.
- Whether an HTTP API, event stream, authentication, persistent run storage, and deployment configuration already exist.

Treat README files and earlier briefs as leads; verify behavior against current code. Do not infer a live event from a final report or a trace that the dashboard cannot access. Do not display hidden model reasoning.

## Implement the smallest live contract

Reuse the backend's current framework and preserve its CLI or existing callers. If the user wants a live dashboard and the backend lacks a run API, add the minimum interface for starting a run, reading its state/result, subscribing to updates, and checking health. A useful shape is `POST /api/runs`, `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/events`, and `GET /health`; adapt existing routes if already established.

Return a run ID promptly while the agent runs outside the request handler. Emit ordered, frontend-safe events at real runtime boundaries. Use stable event IDs and a consistent record such as `event_id`, `run_id`, `type`, `status`, `stage`, `worker` or `agent` when applicable, `timestamp`, `duration_ms` when measured, `summary`, and a small structured `data` object. Include terminal success and failure events. Expose a run snapshot containing status, output, and any honest summary metrics.

For SSE, support missed-event replay or an equivalent recovery path, heartbeat long connections when needed, and close after a terminal event. Match browser dispatch to server framing: `EventSource.onmessage` receives default message frames; named `event:` frames require matching `addEventListener` handlers. The frontend must close its subscription after completion or failure and must not start a second agent run merely because the stream reconnects. Keep secrets and raw sensitive payloads out of events.

If run records live only in memory, use a single server process for the demo and explain that restarts lose old run IDs. Add durable storage only if the new agent or deployment requires it; do not imply that in-memory runs survive a Render sleep, restart, or deploy. Configure CORS for the exact local and hosted frontend origins actually used. Avoid putting model, search, or tracing keys in browser-exposed environment variables.

## Build the demonstration experience

Use the existing frontend stack when practical. Otherwise build a small responsive frontend that can be hosted separately and configured with the backend's public URL. Show:

1. A simple input form and immediate run ID/status.
2. A live graph or stage overview that reflects real branches and parallel work.
3. An ordered event timeline with plain-language summaries, elapsed time, and measured durations when available.
4. Agent-specific decisions, tool activity, evidence, validations, or approvals only when the backend really emits them.
5. The final output in a form suited to that agent, plus a concise run summary and clear failure or partial-result states.

Derive UI state from normalized events and the run snapshot. Show selected, running, completed, skipped, failed, and warning states distinctly when those concepts exist. Do not present parallel workers as one sequential "current agent." Use the new agent's real labels and output sections; do not copy company-research fields such as sources, confidence, or seven report sections unless they apply. Hide or explain unavailable metrics instead of filling cards with invented values. Make the pre-run view useful and avoid panels that appear broken or empty during a run.

Optional example data must be visibly labeled as mock. A configured live mode should never silently fall back to mock data when the API fails. Present useful connection, CORS, timeout, restart, and run-not-found errors to the user without exposing secrets.

## Verify the complete flow

Use a representative input to verify: start response arrives before execution finishes; live events appear in order; parallel and skipped states match the graph; a terminal event closes the stream; the final snapshot and rendered output agree; refresh/reconnect behavior matches the chosen storage; and a failure is understandable. Check the frontend build and focused backend tests. Record what was verified locally versus what still needs a hosted check.

If deployment is requested, provide or apply host-specific build/start/health settings, server-side secrets, the exact frontend API URL, and CORS origins. For Render, check that the server binds to `0.0.0.0` and its assigned port, and warm a sleeping free-tier service before a live presentation. Do not push, publish, or deploy unless that action is within the user's request.

Deliver the working dashboard and any necessary backend adapter, then give a short demo script: the input to use, the graph decisions viewers should watch, and where the final result appears.
