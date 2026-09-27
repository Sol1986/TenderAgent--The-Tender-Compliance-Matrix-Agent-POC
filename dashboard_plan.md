# Tender Agent — Client Demo Dashboard Plan

## Authorized follow-up: recall-first prompt update

The user's subsequent request authorizes one focused update to the prior
prompt-preservation scope: permissive, evidence-backed candidate extraction in
both workers; precision-oriented reconciliation with explicit amendment
precedence and unresolved review items; and downstream reporting of uncertainty.
Keep the existing schemas, graph, parser, model configuration, and original
`main.py` unchanged. Update prompt contract tests and run unit, integration, and
lint checks. Stop after this phase for human verification. Deterministic tests
verify prompt delivery and wiring, not real-provider recall improvements.

Verification: 25 unit/integration tests passed; 2 opt-in parser/provider tests
were skipped. Lint passes for the changed Python files. Repository-wide lint
still reports existing issues in `agent.ipynb`, `export_tables.py`, and `main.py`.
No live-provider recall evaluation was run. This follow-up awaits human review.

The historical prompt-preservation instructions below describe the original
dashboard effort; this follow-up supersedes them for these prompt changes only.

Status: All three dashboard phases implemented and verified locally. Phase 3 is ready for final human verification. See `DASHBOARD_DEMO.md` for results, limitations, startup instructions, and the client presentation sequence. The original application plan remains deferred.

## Scope and protected files

Build a live, presentation-ready dashboard around `main_copy.py`, following `skills/agent-demo-dashboard/SKILL.md`. Keep `main.py` and the existing `plan.md` unchanged. The original full application plan remains deferred; it is not replaced or implemented by this work.

For this dashboard effort, `dashboard_plan.md` is the active implementation plan. Continue the project rule of implementing one approved phase, verifying it, then stopping for explicit human verification. Run no Git commands. Do not publish or deploy as part of this plan.

Recommended first-demo input: the included `tender.PDF`, selected through a simple “Sample tender” input and an “Analyze Tender” button. Run the actual parser and graph each time. Arbitrary PDF uploads and generic parsing improvements remain in the original application plan. This is an explicit scope assumption for review, not an implemented restriction in the original project.

Use Next.js, React, TypeScript, and Tailwind for consistency with the requested application direction. Keep this frontend in `dashboard/` and its small FastAPI adapter in `demo_api/`, so this experiment is easy to distinguish from the deferred application.

## Verified starting point

- `main_copy.py` exists and is byte-for-byte identical to `main.py` at inspection time.
- Both contain the same Pydantic schemas, prompts, LangGraph state, four nodes, `Send` routing, and additive findings reducer.
- Parsing currently uses Docling → exported Markdown → `MarkdownHeaderTextSplitter`, with `#`/`##`/`###` mapped to title/section/subsection and `strip_headers=False`.
- The current filters drop chunks shorter than 50 characters and the `UNIT PRICE TABLE` section. These are prototype behavior, not generic document handling.
- `tables` is referenced by the graph invocation but never populated in either file. The adapter cannot simply import and run the copy successfully without addressing that missing preparation step.
- Model construction, parsing, `tender.md` writes, and graph execution happen at module scope. The copy needs callable boundaries before it can safely serve dashboard requests.
- No API, event stream, frontend, run store, authentication, or deployment configuration is present in the inspected source inventory. A `.venv` and sample artifacts exist, but do not establish a working live demo.
- No agent execution or paid model call was performed to prepare this plan.

## Preserve the agent's logic

```text
Selected sample PDF
        |
    Docling parsing                 ordinary code / document processing
        |
    Prepare inputs
        |----------------------------|
        v                            v
Markdown heading chunks       Docling tables → DataFrames
        |                            |
analyze_chunk × N              analyze_table × M
        |                            |       model-backed graph workers
        |----------------------------|
                     v
        findings accumulated with operator.add
                     v
              reduce_findings                model-backed consolidation
                     v
              TenderAnalysis
                     v
              generate_report                model-backed report
                     v
           DecisionSupportReport
                     v
             Human reviews evidence
```

The dashboard visualizes this actual map/reduce graph. It must not invent a planner, researcher, tool-selection agent, review loop, approval node, or AI bid decision. Parallel workers are repeated invocations of the existing nodes, not distinct autonomous specialists.

Preserve the copy's schemas, worker prompts, routing, section-aware Markdown chunking, and map/reduce/report order. Restrict changes to import-safe functions, configured model creation, missing structured-table preparation, run-local data, and execution instrumentation. Do not import `main.py` indirectly from the adapter or tests.

For this sample-only demo, keep the existing text filters to demonstrate the current prototype faithfully. Emit an honest preparation warning with counts and the reasons for filtered chunks. Explicitly describe the tender-specific table exclusion as a prototype rule, not “smart table detection.” Verify that the excluded table is represented in structured table input. If that coverage cannot be established, fail the demo preparation rather than silently claim complete analysis. The short-chunk filter is a known potential evidence-loss limitation, recorded in the demo notes.

This differs intentionally from the later full application: generic large-table routing, removal of the short-chunk filter, arbitrary uploads, and broader PDF hardening remain deferred. Do not silently change extraction semantics just to make the dashboard look better.

## Client-facing experience

- **Header:** “Tender Analysis Agent,” selected document, backend connection, run status, and elapsed time.
- **Before a run:** sample tender selector, concise workflow explanation, “Analyze Tender,” and a clear indication that this is a live sample demonstration. Explain that the configured model provider processes extracted tender content.
- **Live workflow:** Docling → preparation → two parallel worker lanes → consolidation → decision report. Use readable business labels with code node names in secondary detail.
- **Worker panel:** actual text/table task IDs, section or table label, pending/running/completed/failed state, measured duration, and raw finding count after completion. A completed table with zero findings is valid, not a failed or skipped task.
- **Event timeline:** ordered, plain-language runtime observations. Examples of event wording are design examples, never fabricated observations.
- **Final review:** Decision Support is the default result tab; Tender Analysis and Compliance Matrix expose the structured evidence. Keep the completed workflow accessible.
- **Human decision boundary:** “Decision support only — the proposal team makes the final Bid / No-Bid decision.” No AI verdict or invented readiness score.

Use a restrained navy/slate palette, teal for successful execution, amber for unresolved references, and red for failures. Always pair color with labels. Prioritize readable evidence and a clear parallel graph over decorative animation. On smaller screens stack the two worker lanes without implying sequential execution.

## Shared live API and event contract

All interfaces below are proposed new dashboard interfaces, not existing functionality.

| Endpoint | Contract |
| --- | --- |
| `GET /health` | `200 {"status":"ok"}` for process liveness only |
| `GET /api/demo-inputs` | Allowlisted sample IDs, display names, byte sizes, and availability; never filesystem paths |
| `POST /api/runs` | JSON `{"input_id":"sample-tender"}` with a client-generated `Idempotency-Key`; return `202` with `run_id`, current status, relative snapshot URL, and relative events URL before parsing/model work completes |
| `GET /api/runs/{run_id}` | Current snapshot, stage/worker state, metrics, warnings, latest event ID, validated outputs when available, and safe error details |
| `GET /api/runs/{run_id}/events` | SSE, ordered replay, then live events until the run reaches terminal status |

Reject unknown input IDs; never accept arbitrary file paths or URLs. Use the same idempotency key to recover from an ambiguous start-request response. A duplicate start key returns the existing run within the retention window; a deliberate new run uses a new key. Reconnecting the stream never posts a new run.

Run statuses: `queued`, `running`, `completed`, `failed`. `queued` is the brief accepted-before-start state, not a durable queue. Only one run may be active initially. Additional starts receive a structured `409 RUN_BUSY`, except idempotent repeats of the current request.

Proposed snapshot shape:

```typescript
interface RunSnapshot {
  run_id: string;
  status: "queued" | "running" | "completed" | "failed";
  input: { id: string; display_name: string };
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  last_event_id: number;
  stages: StageSnapshot[];
  workers: WorkerSnapshot[];
  metrics: RunMetrics;
  warnings: Array<{ code: string; message: string }>;
  output: {
    tender_analysis: TenderAnalysis | null;
    decision_support_report: DecisionSupportReport | null;
  };
  error: { code: string; message: string } | null;
}
```

`TenderAnalysis` and `DecisionSupportReport` reuse the copy's existing schemas. Stage and worker records contain stable IDs, real statuses and timestamps, nullable measured durations, and safe labels. Metrics are nullable until measured. Define their exact Pydantic and TypeScript schemas together in Phase 1/2.

If report generation fails after consolidation succeeds, retain the validated tender analysis in the snapshot, mark the run failed, and clearly label the result incomplete. Never present partial output as a completed report.

Event envelope:

```json
{
  "event_id": 12,
  "run_id": "generated-run-id",
  "type": "worker.completed",
  "status": "completed",
  "stage": "analyze_table",
  "worker_id": "table-2",
  "timestamp": "ISO-8601 UTC timestamp",
  "duration_ms": 1834,
  "summary": "Table 2 analysis completed; 3 raw findings returned.",
  "data": {"table_number": 2, "findings_count": 3}
}
```

This is an illustrative envelope, not a result from the supplied tender. Use per-run monotonically increasing event IDs and thread-safe event/snapshot updates. Measure durations using a monotonic clock. Concurrent task completion order may vary; event IDs describe observation order, not a claimed deterministic worker order.

Supported event types: `run.started`, `stage.started`, `stage.completed`, `stage.skipped`, `worker.started`, `worker.completed`, `worker.failed`, `run.warning`, `run.completed`, and `run.failed`. Emit only states actually observed. An empty text/table branch may be marked skipped because it has no tasks; consolidation and reporting do not become “skipped” just because another stage failed.

Use named SSE frames (`event: worker.completed`, etc.), an `id` field, and JSON `data`. The frontend registers matching `addEventListener` handlers for all defined event types, closes the stream on terminal events, and fetches the final snapshot. Named events are not delivered to `onmessage`. See the [MDN SSE documentation](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).

Support replay after `Last-Event-ID`; allow an `after_event_id` query cursor for a newly created EventSource after refresh. Fetch a snapshot first, then subscribe after its `last_event_id` so events between the two calls are replayed. Deduplicate by event ID; do not let a late snapshot overwrite newer event state. Send heartbeat comments during quiet model calls. A terminal snapshot needs no new subscription.

Centralize API error responses as `{"error":{"code":"...","message":"...","request_id":"..."}}`. Cover invalid requests, unavailable sample input, unknown/expired run, busy service, parser failure, provider failure, malformed output, and graph failure. An error after SSE headers are sent becomes a safe failure event rather than a second HTTP response.

## Phase 1 — Make the Copy Runnable and Expose Real Run Events

### Objective

Create the smallest live adapter around `main_copy.py` while retaining the prototype's agent and parsing logic.

### Files to create or modify

Modify only the following existing implementation/configuration files:

- `main_copy.py` — callable preparation/graph boundaries, missing tables input, optional event hooks, and a guarded script entry point.
- `pyproject.toml`, `uv.lock` — explicit FastAPI/Uvicorn and focused test dependencies; compatible resolved versions.
- `.gitignore` — environment secrets, dashboard builds, test caches, and disposable run artifacts; no Git commands.

Create:

- `demo_api/__init__.py`, `demo_api/app.py`, `demo_api/config.py`, `demo_api/models.py`, `demo_api/errors.py`.
- `demo_api/runner.py`, `demo_api/store.py`, `demo_api/events.py` — in-process execution, run storage, event normalization/SSE.
- `.env.dashboard.example` — secret-free configuration template, with explicit loading instructions.
- `tests/unit/test_demo_agent.py`, `tests/unit/test_demo_events.py`, `tests/unit/test_demo_store.py`, `tests/integration/test_demo_api.py`.
- `README.md` — short project entry point if still missing, linking both plans and the demo guide.
- `DASHBOARD_DEMO.md` — startup commands, contracts, sample limitations, and verification record.

### Backend work

1. Record the SHA-256 of `main.py` and `plan.md`; verify these files remain unchanged throughout dashboard work.
2. Refactor only the copy's orchestration into functions. Imports must not parse PDFs, overwrite `tender.md`, invoke models, or require live credentials. Retain direct script execution through a guarded entry point accepting a configured sample path.
3. Preserve Docling export and the existing header splitter settings. Keep intermediate Markdown in memory or a private temporary location so a dashboard run cannot overwrite prototype artifacts.
4. Populate structured table inputs from the same Docling document using DataFrames and faithful string serialization. Preserve table numbering and source evidence. The existing table worker continues to return zero or more raw requirements.
5. Preserve the four graph nodes and their schema/prompt semantics. Establish the actual join behavior with fake models: all scheduled text and table workers must finish before one reduction and one report. Make only a demonstrated wiring correction if this invariant fails, and document it.
6. Instrument real parsing/preparation boundaries and worker/node starts, completions, and failures. Prefer supported LangGraph task observations; verify the installed interface before choosing it. If task events do not expose a needed identity or count, use thin wrappers around the same node calls, not a second graph execution. See [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming).
7. Map text workers to chunk IDs/section headings and table workers to table IDs. Show parser/preparation as ordinary processing, and model-backed nodes as model-backed work. Do not label these as model-selected tools or SDK handoffs.
8. Start work outside the request handler in a bounded executor. Default to one active run, one backend process, and graph concurrency of four. Store final schema-validated results before the terminal event, atomically with terminal state.
9. Use a thread-safe in-memory store. Proposed environment defaults: terminal-run retention 60 minutes, maximum 10 retained terminal runs, heartbeat every 15 seconds, provider timeout 120 seconds, provider retries 2. Do not evict active runs. Retain events for the retained run; sample workload counts must be checked before scheduling to keep memory bounded.
10. Configure the sample path, provider model, backend/frontend URLs, and exact CORS origins through environment variables. Never expose provider keys to the frontend. Do not assume the prototype model name is available until a real provider check succeeds.
11. Sanitize events: no raw prompts, secrets, hidden reasoning, full tables, or extracted document dumps. Final evidence belongs in result views. Resource cleanup occurs when the worker actually exits; a disconnected browser is not cancellation of model execution.
12. Keep this local demo without authentication, a database, durable jobs, or deployment. A backend restart loses all run records, and the UI must explain a missing run rather than recreate it automatically.

### Frontend work

Define typed event/snapshot examples for later consumption. No dashboard UI implementation in this phase.

### API contracts

Implement the shared endpoints, idempotent start, safe errors, named events, replay, and terminal closure specified above. Keep liveness distinct from provider readiness.

### Testing

- Safe import and direct callable execution; untouched `main.py`/`plan.md` hashes.
- Baseline chunking equivalence for fixed Markdown, including headings and both prototype filters; transparent filter warnings and structured coverage of the excluded sample table.
- Deterministic graph tests with fake models: parallel worker collection, empty findings, text-only/table-only branches, single reduction/report, source/evidence preservation, and independent per-run state.
- Controlled blocking-run tests prove the start response arrives before completion. Verify busy admission, idempotency, monotonically increasing event IDs under concurrent worker events, and one terminal event.
- SSE replay, heartbeat, empty replay, final snapshot consistency, unknown-run errors, retention, provider failure, parser failure, and partial-result reporting.
- Run focused unit/integration tests plus `uv run ruff check .` and `uv run ruff format --check .`. Existing lint issues in protected `main.py` must be reported separately; do not modify it or claim a clean whole-project lint run if it fails.

### Completion criteria

The actual sample can run through the copy with both structured outputs; run ID returns promptly; observed events reflect the actual work; required tests pass or external blockers are explicitly documented. Verify the original file hashes. Stop for human verification before Phase 2.

## Phase 2 — Build the Live Client Dashboard

### Objective

Let a client start a real run and understand the agent's parallel execution through a polished, responsive interface.

### Files to create or modify

Create:

- `dashboard/package.json`, `dashboard/package-lock.json`, `dashboard/tsconfig.json`, `dashboard/next-env.d.ts`, `dashboard/next.config.ts`, `dashboard/postcss.config.mjs`, `dashboard/eslint.config.mjs`, `dashboard/.env.example`.
- `dashboard/src/app/layout.tsx`, `dashboard/src/app/page.tsx`, `dashboard/src/app/globals.css`.
- `dashboard/src/lib/api.ts`, `dashboard/src/lib/contracts.ts`, `dashboard/src/lib/run-state.ts`, `dashboard/src/hooks/use-tender-run.ts`.
- `dashboard/src/components/demo-input.tsx`, `dashboard/src/components/run-header.tsx`, `dashboard/src/components/workflow-graph.tsx`, `dashboard/src/components/worker-lanes.tsx`, `dashboard/src/components/event-timeline.tsx`, `dashboard/src/components/connection-status.tsx`.
- `dashboard/src/components/result-preview.tsx` — a clearly labeled structured summary before the full review views in Phase 3.
- `dashboard/vitest.config.ts`, `dashboard/src/test/setup.ts`, `dashboard/src/test/fixtures.ts`, `dashboard/src/test/run-state.test.ts`, `dashboard/src/test/live-dashboard.test.tsx`.

Modify `DASHBOARD_DEMO.md` with frontend setup and verification results. Fix backend contract defects only in the Phase 1 files when demonstrated by integration.

### Backend work

Verify real cross-origin start, snapshot, and streaming requests. Expose no new agent behavior for presentation. Return safe, real preparation and worker counts required by the UI.

### Frontend work

1. Build the sample input, immediate run ID display, connection indicator, and explicit start action. Fetch available sample metadata from the API. Disable duplicate starts while a run is active.
2. Render the actual workflow as a small SVG/CSS graph with two parallel branches and a join. Do not create a complex graph editor or a fictional sequential “current agent.”
3. Derive stage and worker states from normalized events and snapshots. Show pending, running, completed, failed, and actually skipped work with text labels. Present warnings separately from terminal status.
4. Display measured counts: selected text chunks, filtered chunks, structured tables, completed workers, raw findings, and elapsed time. Before preparation finishes, show “Preparing inputs,” not invented totals.
5. Use worker completion fractions as worker progress only. Do not equate “20/20 workers finished” with 100% overall completion while reduction/reporting remain active.
6. Show a concise timeline with expandable details. No artificial delays, timer-driven stage completion, hidden model reasoning, invented tool calls, cost estimates, confidence, or unobserved token metrics.
7. Restore the run ID from the URL on refresh, fetch the snapshot, and reconnect with the cursor when appropriate. Display reconnecting distinctly from agent failure. Close subscriptions on completion, failure, component disposal, or run replacement.
8. Handle unavailable backend, CORS/network problems, expired/restarted run, and invalid responses clearly. Do not silently switch to sample results when live mode fails. Test fixtures remain development-only and visibly labeled wherever rendered.
9. Use keyboard-accessible controls, readable focus states, text status badges, and a responsive layout suitable for screen sharing.

### API contracts

Consume the Phase 1 contract directly through `NEXT_PUBLIC_API_BASE_URL`. Runtime-validate events and snapshots. Unknown additive event types should not crash the UI; malformed required fields trigger a connection/contract error. Preserve separate tender-analysis and report objects.

### Testing

- Simulated interleaved text/table events, duplicate replay events, out-of-order snapshot arrival, missing worker totals, failed workers, zero-finding workers, and terminal closure.
- Refresh recovery, no extra POST on reconnect, idempotent retry after a lost start response, missing run after backend restart, and no mock fallback.
- Frontend lint, type checks, unit/component tests, and production build.
- Browser verification against the real backend: run ID appears immediately; parsing and worker observations arrive during execution; stage timings and final summary agree with the snapshot.

### Completion criteria

The client can launch the sample and watch an honest live workflow, including parallel workers, with clear connection and failure states. Frontend checks pass and actual browser/API streaming is verified. Stop for human verification before Phase 3.

## Phase 3 — Tender Review Views and Client Demo Rehearsal

### Objective

Complete the tender-specific outputs and verify a reliable presentation from sample selection to evidence review.

### Files to create or modify

Create:

- `dashboard/src/components/result-tabs.tsx`, `dashboard/src/components/decision-support.tsx`, `dashboard/src/components/summary-metrics.tsx`, `dashboard/src/components/tender-analysis.tsx`, `dashboard/src/components/requirement-filters.tsx`, `dashboard/src/components/evidence-panel.tsx`, `dashboard/src/components/compliance-matrix.tsx`, `dashboard/src/components/raw-json-panel.tsx`.
- `dashboard/src/lib/requirements.ts`, `dashboard/src/test/results.test.tsx`, `dashboard/playwright.config.ts`, `dashboard/e2e/tender-demo.spec.ts`.
- `tests/integration/test_demo_pipeline.py` — parser-to-graph integration with deterministic model substitutes and separately marked live-provider checks.

Modify `dashboard/src/app/page.tsx`, `dashboard/src/app/globals.css`, `dashboard/src/components/result-preview.tsx`, `dashboard/package.json`, `dashboard/package-lock.json`, and `DASHBOARD_DEMO.md` for completed results, polish, browser tests, and the final demo script. Fix only demonstrated integration defects in earlier dashboard files.

### Backend work

Reuse `final_analysis` and `decision_report`; do not run another model to generate charts, counts, a compliance matrix, or UI sections. Validate final shapes and the separation of category status from individual requirement status. Verify the reducer returns the intended 15 unique categories and flag malformed output instead of inventing missing data.

### Frontend work

1. Default final results to **Decision Support**: executive summary plus all seven existing list fields — reasons to consider bidding, concerns and risks, missing information, mandatory requirements, conditional requirements, external references to review, and questions for the bid team.
2. Provide **Tender Analysis** navigation for the 15 actual categories: submission, required documents, certifications, insurance, bonding security, experience, personnel, technical, financial, formatting, legal/regulatory, language, security, site meeting, and signatures.
3. Show requirement type (`MANDATORY`, `CONDITIONAL`, `INFORMATIONAL`) and item status (`FOUND`, `NOT_REQUIRED`, `EXTERNAL_REFERENCE`) separately, with source sections and expandable evidence. Category `NOT_FOUND` means no extracted evidence; it is not an explicit waiver.
4. Add requirement search, type filtering, and an independent external-reference filter. Derive the Compliance Matrix from the same final requirements; do not infer that the company complies.
5. Compute headline mandatory/conditional counts from final requirements of that type excluding `NOT_REQUIRED`; external-reference count includes items with that status and may overlap either count. Raw worker findings and final consolidated requirements remain separately labeled.
6. Report lists are summaries, so their lengths are not compliance totals. They have no requirement IDs: do not fabricate evidence links for narrative bullets. Offer a clear route into structured evidence review instead.
7. Explain empty report sections without claiming the tender has no risks. Display partial analysis with a failure banner when report generation failed. Keep the final human-decision notice visible.
8. Include collapsed raw JSON for debugging. Render document-derived text safely, without interpreting embedded HTML or instructions. Preserve monetary figures as source strings.
9. Finish responsive and keyboard behavior, uncluttered event history, and screenshot-ready layouts. Do not add authentication, saved history, decision recording, team features, or deployment.

### API contracts

No new endpoints are expected. The completed dashboard consumes the same snapshot outputs and events. If an actual contract defect requires a change, update Python schemas, frontend validation/types, fixtures, and the demo guide together.

### Testing

- Unit/component tests for all report fields, the 15 categories, mixed statuses, filters, empty results, evidence, deterministic matrix rows/counts, and default result tab.
- Browser test: select sample → start → real-time stages/parallel workers → terminal closure → Decision Support → Tender Analysis → evidence → Compliance Matrix.
- Failure tests: parser error, model error, malformed report, lost stream, backend restart, and report failure after successful consolidation.
- Live rehearsal with `tender.PDF`: inspect actual source evidence for selected text/table findings, verify no AI bid verdict, measure total and stage times, and confirm final snapshot/rendered output agreement.
- Separate deterministic automated checks from real Docling/model verification. Live provider access, model availability, parser assets, and runtime are not assumed. Record exactly what passed locally and what remains unverified; do not use fixtures to conceal a failed live check.
- Run project backend commands and dashboard lint/typecheck/tests/build; report inherited protected-file lint failures separately. Recheck original file hashes.

### Completion criteria

The live dashboard works end to end for the supplied sample, displays the real graph and both agent outputs, and supports evidence-led human review. Focused checks pass; a client-demo rehearsal is documented. `main.py` and `plan.md` remain unchanged. Stop for final human verification.

## Proposed client demo script

1. Select the supplied sample tender: “This demonstration runs our existing tender agent on this document.”
2. Click Analyze Tender: “Docling parses the PDF, and the application prepares heading-based chunks and structured tables.”
3. Show both worker lanes: “Text and table workers extract findings in parallel. These are observed execution updates.”
4. Show consolidation: “The agent combines the findings, preserves evidence, and consolidates duplicate requirements.”
5. Open Decision Support: “The report identifies considerations, risks, missing information, and questions for the team.”
6. Open a requirement and its evidence: “The team can inspect the source before making its own Bid / No-Bid decision.”

Before the presentation, verify both local services, sample availability, provider access, and parser assets. Rehearse the actual elapsed time; never manufacture progress. The in-memory demo is single-process and loses run IDs on restart. Hosted deployment and checks are a separate request.

## Approval boundary

Review this dashboard plan before implementation. The project instructions require “Stop and request explicit human verification”; after approval, implement only Phase 1 first. The dashboard skill supplies the live-demo requirements; it does not independently require an extra approval step. The original application plan remains available for later work.
