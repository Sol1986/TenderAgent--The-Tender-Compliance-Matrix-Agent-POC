# Tender Agent Dashboard — Client Demo

The backend wraps `main_copy.py`; it never imports or changes `main.py`.
The original [application plan](plan.md) remains deferred. The live Next.js
interface in `dashboard/` includes workflow monitoring and the Phase 3 report,
requirements, and evidence review views from [dashboard_plan.md](dashboard_plan.md).

## Start locally

From this project directory in PowerShell:

```powershell
uv sync
uv run uvicorn demo_api.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Open [API documentation](http://127.0.0.1:8000/docs) or
[health](http://127.0.0.1:8000/health). These are backend endpoints; the dashboard runs on port 3000.

In a second PowerShell terminal, start the frontend (Node.js 24 recommended):

```powershell
Set-Location 'C:\Users\Admin\Desktop\AI bid decision Agent\dashboard'
npm ci
npm run build
npm start
```

Open [the dashboard](http://localhost:3000), select **Sample tender**, and click
**Analyze Tender**. This runs the supplied `tender.PDF` through the real backend.
There is no PDF upload in this demonstration. Each deliberate start invokes the
parser and configured model provider. Allow several minutes for a run.

For frontend development use `npm run dev` instead of `npm start`. Stop the current
frontend before switching; both use port 3000. Keep the backend terminal running.
Only loopback interfaces are used by these startup commands.

The frontend defaults to `http://127.0.0.1:8000`. To change it, copy
`dashboard/.env.example` to `dashboard/.env.local`, set `NEXT_PUBLIC_API_BASE_URL`,
and rebuild/restart. This public value must contain only the API origin, never a
provider key. Visit **http://localhost:3000** exactly: the backend's default CORS
allowlist does not include **http://127.0.0.1:3000**.

The existing `.env` supplies server-side provider credentials. `.env.dashboard.example`
documents optional settings. To use a separate configuration file:

```powershell
Copy-Item .env.dashboard.example .env.dashboard
$env:DASHBOARD_ENV_FILE = '.env.dashboard'
```

Edit only the copied configuration. Existing process variables and `.env` values
take precedence. `OPENAI_MODEL` defaults to the prototype's model name; configure
a model your account can access. Never put provider/tracing keys in a frontend
environment variable. Sample tender content is sent to the configured provider.
Existing LangSmith environment settings remain applicable; the local verification
run explicitly disables tracing so test activity does not create external traces.

If `uv` reports `invalid peer certificate: UnknownIssuer`, use its system trust store:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:TEMP = Join-Path (Get-Location) '.test-tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
uv --system-certs sync --link-mode copy
```

This workspace needed the above cache/temp settings for a dependency build.
The lockfile includes the development tools and the pre-existing notebook tooling
in a default `notebook` dependency group, so environment synchronization preserves
Jupyter/IPython use.

Standalone agent execution remains available with `uv run python main_copy.py`.
It uses the configured sample and prints the two structured results. Importing the
copy performs no conversion, provider construction, or graph invocation.

## Start and inspect one run

```powershell
$headers = @{ 'Idempotency-Key' = [guid]::NewGuid().ToString() }
$run = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/runs `
    -ContentType 'application/json' -Headers $headers `
    -Body '{"input_id":"sample-tender"}'
$run
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/runs/$($run.run_id)"
```

Reuse the same key only when recovering an ambiguous start response. A deliberate
new run needs a fresh key. A second independent run while one is active returns
`409 RUN_BUSY`. Refresh, snapshot reads, and stream reconnects never start another run.

| Route | Behavior |
| --- | --- |
| `GET /health` | Process liveness; does not certify parser/provider readiness |
| `GET /api/demo-inputs` | The configured sample's public ID, display name, size, availability |
| `POST /api/runs` | Required JSON `input_id` and `Idempotency-Key`; immediate `202` |
| `GET /api/runs/{run_id}` | Execution snapshot, warnings, counters, separate outputs, safe error |
| `GET /api/runs/{run_id}/events` | Named SSE events with IDs, replay, heartbeats, terminal closure |

Client-supplied paths/URLs are rejected. Errors consistently use
`{"error":{"code":"...","message":"...","request_id":"..."}}`.
Provider exceptions and document contents are not copied into error responses.

## Event and frontend adapter notes

- Stage IDs: `parse_document`, `prepare_inputs`, `analyze_chunk`, `analyze_table`,
  `reduce_findings`, `generate_report`.
- Stage/worker statuses: `pending`, `running`, `completed`, `failed`, `skipped`.
  Warnings are separate; a zero-finding table worker is completed, not skipped.
- Run statuses: `queued`, `running`, `completed`, `failed`. No durable queue exists.
- Named events: `run.started`, `stage.started`, `stage.completed`, `stage.skipped`,
  `worker.started`, `worker.completed`, `worker.failed`, `run.warning`,
  `run.completed`, `run.failed`.
- Event envelope fields: `event_id`, `run_id`, `type`, `status`, `stage`,
  `worker_id`, UTC `timestamp`, nullable `duration_ms`, `summary`, and small `data`.
  Event `status` is the event suffix (for example `started`); snapshot task status
  is `running`. Do not assign an event suffix directly as a snapshot task status.
- Use `addEventListener` for named events, not only `onmessage`. Close EventSource
  on terminal success/failure and fetch the final snapshot.
- A preparation-completed event carries counts. Fetch the snapshot at that point
  for the full pending-worker roster. Event records deliberately exclude raw
  worker inputs and document dumps.
- On refresh, restore the run ID, fetch its snapshot, then connect with
  `?after_event_id=<last_event_id>`. Automatic reconnect supports `Last-Event-ID`,
  which takes precedence over the query cursor. Deduplicate by integer event ID.
  A cursor ahead of the run is a structured `422 INVALID_CURSOR`.
- Snapshots are self-contained, deep-copied restoration points; final output is
  committed before the terminal event. If consolidation succeeds but report
  generation fails, `tender_analysis` remains available while the run is failed
  and `decision_support_report` is null.
- Counts distinguish raw worker findings from final consolidated requirements.
  Unknown counts/durations are null, not invented zeros. `completed_workers` and
  `raw_findings` begin at zero and increase on actual successful worker completions.
- Model prompts, reasoning, tokens, cost, and model-selected tool calls are not
  exposed as dashboard events. Thin wrappers observe actual node entry/exit;
  native scheduled-task announcements are not mislabeled as running work.

Inspect `/openapi.json` for the full snapshot/domain schemas. Pydantic models live
in `demo_api/models.py`; `main_copy.py` remains the source of the agent's output schemas.

## Deliberate prototype limits

- The demo is sample-only. Arbitrary uploads and generic large-table handling are
  deferred to `plan.md`.
- The original heading splitter and both filters remain: fewer than 50 characters,
  and the `UNIT PRICE TABLE` section. A warning reports omissions, including prose
  surrounding the filtered table. Structured table coverage must verify before a
  run can proceed. This is not a guarantee that filtered prose is unimportant.
- Every structured table enters the existing table worker. Values are serialized
  from DataFrames without monetary arithmetic. The original worker may return no
  relevant findings; the reducer combines findings semantically.
- One server process, one active run, configurable graph concurrency (default 4).
  No authentication, durable history, cancellation API, database, or job service.
- Retain at most 10 terminal runs for up to 60 minutes by default. Expiry is checked
  lazily when the store is accessed; the count bound is enforced on completion.
  Active runs are not evicted. Restart loses run IDs and idempotency keys.
- Limits cap scheduled work at 500 inputs and 2,000,000 serialized input characters.
  These are workload safeguards, not per-model context-window guarantees. Oversized
  samples fail instead of silently truncating evidence. Row batching is deferred.
- Provider calls have configurable timeout/retries. Docling conversion itself has
  no hard execution timeout. Browser disconnect does not cancel processing. Clean
  shutdown waits for in-flight work; forcibly stopping the server loses its runs.
- Events are frontend-safe, but the final report contains tender evidence and is
  available to anyone who can reach this unauthenticated local server. Bind to
  loopback for the demo. Hosted deployment is not implemented or verified.
- The unchanged report prompt forbids an AI Bid / No-Bid decision. Schema checks
  establish shape and category invariants, not factual completeness or semantic
  compliance. The team must review the evidence and make the final decision.

## Phase 1 verification record

- Deterministic unit tests: **13 passed**.
- API integration tests: **10 passed**; actual LangGraph with model substitutes,
  admission/idempotency, parallel join, event replay/closure, partial output,
  parser/provider/malformed failures, restart loss, CORS, and error handling.
- AST regression test verifies all four prompt bodies match `main.py` exactly.
- Changed-code lint and formatting pass after fixes.
- Whole-project lint reports **14 pre-existing findings** in `main.py`,
  `agent.ipynb`, and `export_tables.py`; whole-project formatting reports the
  original `main.py` and `agent.ipynb`. These protected/unrelated files were not fixed.
- Real Docling conversion and preparation passed: **54 initial chunks → 43 text
  workers; 5 structured tables; 10 short chunks and 1 table section filtered**.
  The excluded table passed structured-coverage verification. Docling emitted
  table-layout recovery warnings; extraction quality still needs evidence review.
- The configured provider answered a live smoke request successfully.
- Full HTTP + real-parser + real-model verification **passed** on the supplied
  sample: start response in **0.032 seconds**, execution in **238 seconds**,
  **48 completed workers**, **124 raw findings**, **60 consolidated requirements**
  across **15 categories**, and both structured outputs.
- The live SSE client received **111 events** in strictly increasing ID order and
  reached EOF after `run.completed`. A separate connection replayed the next event
  using `Last-Event-ID` on the same run. Observed text/table execution overlapped.
- The report included the executive summary and all seven list fields. A focused
  check found no explicit final-verdict/recommendation patterns. The closing date,
  closing time, and BA02 reference were spot-checked against the existing tender
  Markdown export; this was not a full audit of all 60 requirements.
- Some returned evidence strings are summaries rather than verbatim quotations.
  That reflects the preserved extraction/consolidation behavior. Phase 2/3 must
  not label every evidence string an exact source quote.
- Verified `main.py` SHA-256 remains
  `FF51E0BE2086230DA08319FBA1F0B19B52EF371D43A09695EB370C4DCD756034`;
  `plan.md` remains
  `103C38C64CA41B84B30D297C7F85651A022F321A83174AFD871ABE5479D2593B`.
- Live run ID: `c6f6f25b-48c9-4cb3-a009-f58e74527035`. It is temporary and expires
  with retention or server restart. The local verification snapshot is in the
  ignored `.test-tmp/live-run.json`; it is a recorded live result, not mock data.
- No browser dashboard was part of Phase 1. Phase 2 browser checks are recorded
  below. Hosted deployment remains outside this local demonstration.
- Starlette's TestClient emits an upstream AnyIO alias deprecation warning; tests pass.

Commands:

```powershell
uv run pytest tests/unit/ -q
uv run pytest tests/integration/ -q
uv run ruff check main_copy.py demo_api tests
uv run ruff format --check main_copy.py demo_api tests
```

Do not use a whole-repository auto-fix command: `main.py` and notebook artifacts
must remain unchanged.

## Phase 2 behavior and verification

The dashboard shows the sample document, immediate run ID, measured elapsed time,
actual stage states, parallel text/table branches, expandable worker lists,
preparation warnings, and an ordered event timeline. Worker fractions measure
worker completion only; consolidation and report generation remain separate.
The result preview shows the returned executive summary and consolidated
requirement count. Full decision-support lists, evidence filters, and the
Compliance Matrix are deferred to Phase 3.

The run ID is stored in the page URL. Refresh restores stage/worker/output state
from the backend and subscribes after that snapshot's event cursor. The timeline
shows events received during the current page connection; it does not reconstruct
older history on refresh. A completed snapshot needs no stream. Native stream
reconnects never start another run, and ambiguous start retries reuse their
idempotency key. Restarted or expired runs produce an explicit unavailable-run
message. There is no mock data fallback or browser-exposed provider credential.

- Frontend unit/component checks: **15 passed**, covering interleaved workers,
  duplicate events, stale snapshots, zero findings, failure states, terminal
  closure, refresh recovery, reconnect without POST, idempotent start recovery,
  malformed events, expired runs, and unavailable backend.
- `npm run lint`, `npm run typecheck`, and `npm run build`: **passed**.
  Final checks used bundled Node.js **24.19.0**. Node 22.12 ran initial checks but
  emitted a transitive ESLint engine warning; use Node 24 for the documented setup.
- The live browser launched run `d304afea-b0bb-45f1-826d-1bd928f0c20b` and received
  real parser/worker events. The final UI agreed with the API snapshot:
  **251,733 ms**, **43 text workers**, **5 table workers**, **48 completed workers**,
  **146 raw findings**, **67 consolidated requirements**, and both outputs across
  **15 categories**. Model-generated counts can differ between runs.
- A sidebar anchor-navigation defect discovered during live testing was fixed:
  section changes preserve the current snapshot and subscription. An automated
  regression test covers this behavior.
- The production build was checked in the browser at desktop and phone widths.
  The phone layout had no horizontal document overflow. Refresh during parsing
  recovered the same run and continued receiving worker events; subsequent
  sidebar navigation retained its real worker counts. Keyboard activation
  expanded the table-worker list. No browser console errors or warnings were
  observed in this production check.
- Final production-browser run `5f108219-4a09-443d-b426-d5aaa13761cc` completed
  in **173,859 ms** with **48 completed workers**, **144 raw findings**, and
  **61 consolidated requirements**. The browser transitioned to Completed / API
  connected and displayed the returned executive summary and 61 requirements,
  agreeing with the final API snapshot (event ID 111). The ignored record is
  `.test-tmp/phase2-production-run.json`.
- The original `main.py` and `plan.md` hashes still match the Phase 1 record.
  Phase 2 did not alter the backend or `main_copy.py`.
- The recorded first Phase 2 live snapshot is in ignored
  `.test-tmp/phase2-live-run.json`; it is not imported by the dashboard. Runs remain
  temporary and do not survive backend restart.

Frontend verification commands, from `dashboard/`:

```powershell
npm run test
npm run lint
npm run typecheck
npm run build
```

Phase 2 was approved before Phase 3 implementation.

## Phase 3 review experience

After consolidation, **Tender review** exposes three keyboard-accessible tabs:

- **Decision Support** opens by default. It renders the executive summary and
  all seven returned report lists. Empty sections explicitly mean no items were
  returned, not an absence of obligations or risks.
- **Tender Analysis** covers the 15 actual categories, with category selection,
  text search (including source/evidence), requirement-type filtering, and a
  separate external-reference checkbox. Each requirement shows its type and
  extraction status independently. Expand **Source & evidence** to inspect the
  returned source sections and evidence; evidence may be paraphrased.
- **Compliance Matrix** derives its rows from those same requirements and shares
  the search/type/external filters. It does not assess the bidder's compliance,
  invent a company profile, or record review decisions. On small screens, the
  table scrolls within its own focusable region.

Summary counts derive from final requirements, not report-bullet counts or raw
worker findings. Mandatory/conditional totals exclude `NOT_REQUIRED`; external
references may overlap either total. Category `NOT_FOUND` indicates no extracted
evidence, not a waiver. Source amounts remain unmodified strings. Report bullets
have no fabricated requirement IDs or evidence links.

If reporting fails after consolidation, the failure banner remains visible and
the available structured requirements can still be reviewed. Raw JSON is
collapsed by default and keeps both outputs separate. Source text is rendered
as text, never interpreted as HTML. No additional model calls generate the views.

### Phase 3 automated checks

- Frontend: **23 tests passed**, including all report fields, 15 categories,
  overlapping counts, waiver exclusion, combined/shared filters, matrix rows,
  evidence expansion, literal HTML rendering, preserved source amounts, empty
  sections, keyboard tabs, partial-report failure, and failed-run stream closure
  with retained analysis.
- Frontend lint, TypeScript validation, and production build passed.
- Backend default suite: **23 passed, 2 opt-in tests skipped**. Existing tests cover
  parser/provider/malformed-output errors, stream replay, restart loss, and partial
  output. The upstream AnyIO deprecation warning remains.
- Separately enabled real-Docling integration test: **1 passed** in 62.45 seconds
  using deterministic model substitutes. It verified 43 text inputs, 5 tables,
  11 filtered chunks, 48 worker completions before the join, and exactly one
  consolidation and report invocation. Docling/Torch emitted upstream warnings.
- Changed-code Python lint and formatting passed. Whole-project lint retains
  the same 14 inherited findings in `main.py`, `agent.ipynb`, and
  `export_tables.py`; formatting still flags `main.py` and `agent.ipynb`.
- The opt-in Playwright scenario was added and test discovery passed. Its CLI
  browser execution was not run in this session; the live flow was exercised
  through the connected browser instead. Live-provider pytest is also opt-in
  rather than part of every fast test run.

To run the real parser with model substitutes:

```powershell
$env:DEMO_TEST_REAL_PARSER = '1'
uv run pytest tests/integration/test_demo_pipeline.py -m real_parser -q
Remove-Item Env:DEMO_TEST_REAL_PARSER
```

For a repeatable paid-provider browser rehearsal, keep both services running,
install the Playwright Chromium browser once, and run from `dashboard/`:

```powershell
npx playwright install chromium
$env:DEMO_TEST_LIVE_PROVIDER = '1'
npm run test:e2e
Remove-Item Env:DEMO_TEST_LIVE_PROVIDER
```

The test starts exactly one sample run and allows up to ten minutes. It checks
refresh without another POST, real completion, report/API agreement, evidence,
and matrix row count. For a separate Python live-provider check, set the same
opt-in flag and run `uv run pytest tests/integration/test_demo_pipeline.py -m live_provider -q`
from the project root; this starts another paid run.

### Phase 3 live rehearsal record

Run `70b16e9d-e633-4f44-8207-fb6052a71a4d` completed through the production
dashboard in **127,891 ms (2m 07s displayed)**. The final API snapshot and browser
agreed on **43 text workers**, **5 table workers**, **48 completed workers**,
**120 raw findings**, and **52 final requirements**. Headline counts were **41
mandatory**, **6 conditional**, and **15 external references**; these are
overlapping dimensions, not numbers to sum into a total.

Measured stages: parsing 45,250 ms; preparation 62 ms; text branch 30,342 ms;
table branch 7,703 ms; consolidation 24,905 ms; report 21,453 ms. Branch timings
can overlap and do not sum to total elapsed time.

The browser displayed the immediate run ID and live events, restored the same
run after refresh, then changed to Completed / API connected. Decision Support
was selected by default. All seven report-list lengths matched the returned
output (7, 17, 13, 17, 8, 13, 20 in schema order). The matrix contained 52
requirement rows; the external-only filter reduced both review views to 15.
Table evidence expanded to its returned Table 3/4/5 source sections. Keyboard
Home navigation selected Decision Support. Phone layout had no horizontal
document overflow; the wide matrix scrolled internally, and all tab labels fit.
No console errors or warnings were observed.

Selected text and table findings were spot-checked against `tender.md`: the
June 19, 2012 closing date/time, BA06 seven-week construction period, and the
unit-price work items through item 51. This was not a completeness audit of
all requirements. Evidence includes paraphrases and the preserved short-chunk
filter may omit relevant prose. No AI verdict control was added.

The ignored verification snapshot is `.test-tmp/phase3-live-run.json`; the
application never loads it as fallback data. Both protected file hashes still
match the Phase 1 record. Phase 3 changed no agent prompts, graph, parser, or
backend execution behavior.

### Client presentation sequence

1. Select **Sample tender** and click **Analyze Tender**. Explain that it is the
   included historical tender and that this starts real parsing/model work.
2. Show parsing and the two worker branches. Worker counts and durations are
   observations; a full worker progress bar does not mean the report is ready.
3. Expand **Preparation notes** to explain the preserved prototype filters.
4. When complete, use **Run summary** to reach **Decision Support**. Discuss the
   concerns, missing information, and questions the agent returned.
5. Click **Review structured evidence**, select a category, and expand a
   requirement's **Source & evidence**. Check the original document when needed.
6. Open **Compliance Matrix**, try a type or external-reference filter, then
   close with the human decision boundary. The agent makes no Bid / No-Bid verdict.

Run history remains temporary. The supplied tender has a historical closing date;
this demonstration does not represent a currently open procurement opportunity.
Arbitrary PDF uploads, authentication, durable storage, and hosted deployment
remain outside the completed dashboard scope.
