# Tender Analysis Application — Implementation Plan

Status: proposed for human review. No implementation has started.

This plan follows `prompt.md` and `AGENTS.md`. It contains exactly three implementation phases. Implement only one approved phase at a time, complete its checks, then stop for explicit human verification. Do not run Git commands. The instruction to save this plan is the sole file-change exception to the prompt's instruction not to implement or modify files yet. On this Windows workspace, `PLAN.md` and `plan.md` refer to the same file; use the requested spelling `plan.md`.

## Findings from the existing project

The following are confirmed by source inspection, not by executing the agent:

- `main.py` already defines `Requirement`, `ChunkFindings`, `FinalRequirementItem`, `RequirementCategory`, `TenderAnalysis`, and `DecisionSupportReport`.
- The four intended nodes exist: `analyze_chunk`, `analyze_table`, `reduce_findings`, and `generate_report`. Both workers return raw findings; `Annotated[list[Requirement], operator.add]` combines them. The reducer prompt requests semantic consolidation and evidence preservation.
- Category status and individual requirement status are already separate. The final requirement schema also includes mandatory, conditional, and informational types. Preserve this model.
- `generate_report` already explicitly forbids making the final bid/no-bid decision and assuming bidder capabilities. Preserve and test those instructions.
- `analyze_table` already permits empty findings for irrelevant tables. Keep this behavior.
- `main.py` performs PDF conversion, writes and rereads `tender.md`, constructs an LLM client, and invokes the graph at module scope. Importing it is therefore unsafe for an API or isolated tests.
- The final invocation references `tables`, but `main.py` never defines that variable. A complete working standalone run is therefore not established.
- The prototype hardcodes `tender.pdf` / `tender.PDF`, removes the section named `UNIT PRICE TABLE`, and drops every text chunk shorter than 50 characters. These rules can lose valid requirements in other tenders.
- `export_tables.py` demonstrates Docling table-to-DataFrame export, but targets an example path rather than the uploaded document. Existing CSV/HTML exports are sample artifacts, not runtime inputs.
- `pyproject.toml` declares the AI/document dependencies, but not a complete explicit API or test toolchain. It references a missing `README.md`. `Makefile` already defines lint, unit, integration, and combined verification commands; there are no test directories or frontend yet.
- `.gitignore` currently omits `.env`, frontend build artifacts, and test artifacts. Update ignore rules during implementation without invoking Git or reading secret values.

No model calls, PDF conversions, dependency installations, or application tests were run for this planning task. Existing notes and sample exports do not establish current correctness.

## Proposed architecture and scope

Use the smallest separation that keeps the existing agent recognizable:

```text
Next.js / React / TypeScript / Tailwind
           |
           | POST /api/analyze — multipart PDF
           v
api/app.py + api/routes.py
           |
           v
services/tender_service.py
           |
           +--> services/document_service.py — Docling, chunks, tables
           |
           +--> main.py — existing schemas, workers, graph factory
                           |
                           v
                 TenderAnalysis + DecisionSupportReport
```

- Keep schemas and agent nodes in `main.py`; do not create another implementation of them in routes. Introduce a graph factory with an injectable configured model and a typed invocation boundary.
- Use a single request/response endpoint. The browser sends the actual file directly to FastAPI, avoiding an extra Next.js upload proxy and its body/time limits.
- Run blocking Docling and graph work through a bounded worker execution path so the API event loop remains responsive. Default to one active analysis per backend process and bounded LangGraph worker concurrency. Reject excess work with a clear busy response rather than creating a queue.
- Use request-local state and temporary directories. No authentication, persistence, history, accounts, payments, collaboration, cloud storage, job infrastructure, or microservices.
- Results live in browser memory. Refreshing the page clears them; display that behavior in the README.
- No AI verdict, confidence score presented as a bid recommendation, or automated final decision. The interface explicitly states that the proposal team makes the final decision.
- Monetary values remain source text. If numeric money processing is later necessary, use `Decimal` or integer cents, never floating-point values. No database is introduced, so database transactions are not applicable to this MVP.

## Shared API contract

### Analyze a tender

`POST /api/analyze`

Request: `multipart/form-data` with exactly one required `file` field containing PDF bytes. No local file path or remote URL input. The browser uses `FormData` and lets the browser set the multipart boundary.

Success: `200 application/json`, returned only after both validated outputs are ready:

```typescript
type CategoryName =
  | "submission" | "required_documents" | "certifications" | "insurance"
  | "bonding_security" | "experience" | "personnel" | "technical"
  | "financial" | "formatting" | "legal_regulatory" | "language"
  | "security" | "site_meeting" | "signatures";

interface FinalRequirementItem {
  requirement: string;
  status: "FOUND" | "NOT_REQUIRED" | "EXTERNAL_REFERENCE";
  requirement_type: "MANDATORY" | "CONDITIONAL" | "INFORMATIONAL";
  source_sections: string[];
  evidence: string[];
}

interface TenderAnalysis {
  categories: Array<{
    category: CategoryName;
    status: "FOUND" | "NOT_FOUND";
    requirements: FinalRequirementItem[];
  }>;
}

interface DecisionSupportReport {
  executive_summary: string;
  reasons_to_consider_bidding: string[];
  concerns_and_risks: string[];
  missing_information: string[];
  mandatory_requirements: string[];
  conditional_requirements: string[];
  external_references_to_review: string[];
  questions_for_bid_team: string[];
}

interface AnalyzeResponse {
  tender_analysis: TenderAnalysis;
  decision_support_report: DecisionSupportReport;
}
```

Reuse the Python domain models inside an API response wrapper. Map graph `final_analysis` to `tender_analysis` and graph `decision_report` to `decision_support_report`. Validate that all 15 categories occur exactly once, `NOT_FOUND` categories are empty, and `FOUND` categories contain findings. Do not collapse requirement statuses or invent empty categories to conceal a malformed model output.

All application errors, including FastAPI request validation, use the centralized JSON envelope:

```json
{
  "error": {
    "code": "INVALID_PDF",
    "message": "This PDF could not be opened. Select a readable PDF and try again.",
    "request_id": "server-generated-correlation-id"
  }
}
```

| HTTP | Error codes / intended behavior |
| --- | --- |
| 400 | `EMPTY_FILE`, `INVALID_PDF`: empty, corrupt, or unsupported encrypted PDF |
| 413 | `FILE_TOO_LARGE`: configurable byte limit exceeded |
| 415 | `UNSUPPORTED_FILE_TYPE`: extension, media type, or signature does not support PDF input |
| 422 | `INVALID_REQUEST`, `NO_EXTRACTABLE_CONTENT`, `DOCUMENT_LIMIT_EXCEEDED`: missing file, neither usable text nor usable tables, or configured processing limits exceeded |
| 502 | `LLM_FAILED`, `INVALID_ANALYSIS_RESPONSE`: provider failure or invalid structured output |
| 503 | `ANALYSIS_BUSY`: processing capacity occupied; manual retry is available |
| 504 | `ANALYSIS_TIMEOUT`: analysis exceeds its configured deadline |
| 500 | `DOCUMENT_PROCESSING_FAILED`, `GRAPH_EXECUTION_FAILED`, `INTERNAL_ERROR`: unexpected internal failures |

Do not return stack traces, provider credentials, raw provider errors, or extracted tender content in errors. Log request IDs and concise diagnostics without logging complete documents by default. Browser-side network failures and non-JSON proxy responses are translated to understandable frontend errors.

Also expose `GET /api/health` → `200 {"status":"ok"}` for process health; it does not make paid provider calls or certify model availability. Retain FastAPI's generated OpenAPI document for contract checks.

## Phase 1 — Backend Integration + PDF Upload Pipeline

### Objective

Accept a real uploaded PDF, process its text and structured tables safely, invoke the existing graph, and return both validated outputs independently.

### Files to create or modify

Modify:

- `main.py` — remove import-time processing; retain domain schemas and nodes; add typed graph factory/invocation boundaries, schema invariants, and focused prompt safeguards.
- `pyproject.toml` and `uv.lock` — explicitly declare FastAPI, Uvicorn, multipart handling, DataFrame serialization dependencies, configuration and test tools as needed; pin a compatible resolved environment.
- `.gitignore` — ignore `.env`, generated frontend/runtime files, temporary outputs, and test artifacts; permit secret-free example configuration.

Create:

- `config.py` — validated environment configuration.
- `.env.example` — documented variables with placeholders and proposed operational defaults, never real credentials.
- `api/__init__.py`, `api/app.py`, `api/routes.py`, `api/schemas.py`, `api/errors.py` — application composition, upload route, response wrapper, and global error handling.
- `services/__init__.py`, `services/document_service.py`, `services/tender_service.py` — document preparation and graph orchestration.
- `tests/conftest.py`, `tests/unit/test_document_service.py`, `tests/unit/test_graph.py`, `tests/unit/test_schemas.py`, `tests/unit/test_config.py`.
- `tests/integration/test_analyze_api.py`, `tests/integration/test_docling_pipeline.py`.
- `tests/fixtures/text_only.pdf`, `tests/fixtures/tables_only.pdf`, `tests/fixtures/mixed_large_table.pdf`, `tests/fixtures/short_requirement.pdf`, `tests/fixtures/corrupt.pdf` — small synthetic, non-confidential fixtures.
- `README.md` — environment setup, API contract, local startup, limitations, and verification instructions.

Leave `agent.ipynb`, `export_tables.py`, `notes.md`, and existing sample tender/export files intact. Use the existing `Makefile` checks; do not reorganize unrelated prototype material.

### Backend work

1. Make importing `main.py` free of PDF reads, file writes, graph invocation, and model construction that requires credentials. Preserve node names and domain prompts except for targeted safeguards and input context changes. Remove duplicate imports and duplicate extractor initialization in the touched file.
2. Configure model selection and provider credentials through environment variables. Verify the selected model with the actual provider during the live smoke test; the prototype's hardcoded model string is not proof of API availability.
3. Validate `.pdf` extension case-insensitively, supported media type, PDF signature, and actual parseability. Accommodate a missing/generic browser MIME type only when other checks confirm a PDF. Treat filenames as display metadata, never paths.
4. Enforce a default `MAX_UPLOAD_BYTES=26214400` (25 MiB) while receiving the multipart request, including a bounded allowance for multipart overhead, and verify the exact file byte count before conversion. Do not rely only on `Content-Length` or a post-upload read check.
5. Store input under a generated name in a request-owned temporary directory. Close upload handles and clean up on success and failure. Never overwrite `tender.md` or share per-document output paths.
6. Parse the uploaded PDF with Docling once. Produce section-aware text and every extracted structured table from that same document. Remove the blanket 50-character text filter: short deadlines, signatures, and other meaningful text must survive.
7. Apply the generic large-table policy below. Keep DataFrame values as faithful strings for model serialization. Preserve headings, table identity, available page references, captions, and evidence context.
8. Invoke the existing map/reduce graph with `chunks`, `tables`, and a fresh empty `findings` list. Test the existing fan-out/join behavior before changing graph edges. Both worker branches must finish before a single reduction and a single report generation. Verify text-only, table-only, and workers returning no findings.
9. Preserve an empty `analyze_table` result as valid. No tables is normal for a text-only document; no prose is acceptable when structured tables contain usable content. Reject only when neither path can supply usable content. Fail visibly on incomplete conversion or lost table extraction instead of silently reporting comprehensive analysis.
10. Add bounded request and model concurrency, provider retries/timeouts, and input budgets. Initial environment defaults: `MAX_ACTIVE_ANALYSES=1`, `GRAPH_MAX_CONCURRENCY=4`, `LLM_TIMEOUT_SECONDS=120`, `LLM_MAX_RETRIES=2`, `ANALYSIS_TIMEOUT_SECONDS=900`, and `MAX_PDF_PAGES=200`. Tune against actual fixtures and hardware.
11. Bound text/table model inputs and reducer inputs before invocation. Proposed starting budgets: `TEXT_CHUNK_MAX_TOKENS=6000`, `TABLE_BATCH_MAX_TOKENS=6000`, `REDUCER_MAX_INPUT_TOKENS=48000`, with prompt/schema/output headroom checked against the chosen model. Split prose along headings and paragraphs; preserve metadata. Reject an input that still cannot fit rather than truncating findings silently or introducing a new multilevel reducer for the MVP.
12. Treat uploaded content as evidence, not instructions. Keep extraction/report instructions outside document content. Do not follow embedded requests to alter behavior or fetch arbitrary links. External references remain unresolved for human review.
13. Centralize exceptions and validate the response before returning it. Retain the no-verdict prompt and add focused report-output validation/regression cases for explicit AI bid/no-bid recommendations; reject such output rather than showing a verdict. Natural-language compliance and extraction accuracy still require live evaluation, not just schema checks.

Timeout limitation: timing out an await does not forcibly terminate a running synchronous converter or model call. Keep its capacity reservation and temporary directory until the worker exits, check the deadline between stages, and do not promise immediate cancellation. The browser must not automatically resubmit a long-running request. Process isolation and durable background jobs remain outside this MVP.

### Generic large-table handling

Use Docling structure and table identity first, rather than guessing from a section name or deleting an entire chunk.

Proposed configurable starting thresholds:

| Variable | Initial value | Purpose |
| --- | --- | --- |
| `LARGE_TABLE_ROW_THRESHOLD` | 25 | Data rows, excluding repeated headers |
| `LARGE_TABLE_CELL_THRESHOLD` | 150 | Rows × columns |
| `LARGE_TABLE_CHARACTER_THRESHOLD` | 6000 | Serialized content size of an identified table |
| `TABLE_HEAVY_RATIO_THRESHOLD` | 0.60 | Fallback ratio of confidently identified tabular content in a text chunk |
| `TABLE_BATCH_MAX_ROWS` | 50 | Maximum rows per table-worker batch; token budget can force smaller batches |

Algorithm:

1. Enumerate Docling tables with stable document-local IDs. Convert every table to a DataFrame and register its serialized worker input before considering any text omission.
2. Mark an identified table large when rows reach 25, cells reach 150, or its serialized size reaches 6000 characters. Character count is used only after structural table identification; it cannot classify a prose paragraph as a table. Record column counts and available Docling references as part of this decision.
3. Build text in document order from Docling items/serialization boundaries while tracking headings. For a registered large table, omit only its table-body representation from the text path. Keep captions, nearby instructions, footnotes, and a lightweight source marker. Verify the installed Docling traversal/serialization APIs during implementation; do not assume a nonexistent export option.
4. If a document export requires fallback matching, combine Markdown table structure, row/column structure, tabular-content ratio, and a reliable match to a registered structured table. Strip only the matched table span, even inside a mixed prose/table chunk. The 0.60 ratio alone never authorizes dropping a chunk.
5. If correspondence is uncertain, retain the text representation. If structured table conversion fails, never remove its text and silently lose coverage: surface a document-processing failure. A little duplicate input is preferable to hidden evidence loss.
6. Small tables remain eligible for text processing and always enter the table pipeline. Let the table worker return empty findings when appropriate; do not introduce a table-classification model.
7. Split oversized structured tables into row batches with repeated headers, table ID, row range, caption, and source context. Respect both row and token limits. Preserve all rows in order without summarization or numeric rounding. If a single row cannot fit, return a clear processing-limit error rather than dropping cells.
8. All resulting table batches still call `analyze_table`. Their raw findings combine with text findings through the existing reducer, which remains responsible for semantic deduplication.

Test the central invariant: every large table omitted from text has complete structured worker coverage, and unrelated prose remains present. These thresholds are starting heuristics, not a guarantee of perfect table recognition.

### Frontend work

No frontend implementation in this phase. Finalize the response/error contracts and fixture payloads that Phase 2 will consume.

### API contracts

Implement `POST /api/analyze`, `GET /api/health`, the shared success model, and the error envelope above. Configure allowed frontend origins explicitly through environment variables; no wildcard CORS. Never expose provider keys to the frontend.

### Testing

- Unit tests: safe import; graph fan-out/join with injected fake structured models; text-only/table-only flows; empty findings; mixed statuses; exactly 15 unique categories; response mapping and invalid output handling.
- Document tests: generic table names; row, cell, and character boundaries; short important prose; mixed prose/table spans; uncertain matching; no missing or repeated row coverage across batches; small irrelevant tables returning empty findings; preservation of sections and evidence.
- API integration tests: actual multipart bytes; misleading filenames/MIME; missing, empty, oversized, corrupt, and encrypted inputs; request-size enforcement without trustworthy `Content-Length`; safe temporary paths; cleanup; provider/graph failures; error shape; CORS; concurrency and request isolation.
- Real Docling fixture tests with fake LLMs verify parsing and extraction without paid calls. Document required parser/OCR model assets; never report skipped parser tests as passed.
- Run `uv run pytest tests/unit/`, `uv run pytest tests/integration/`, `uv run ruff check .`, and `uv run ruff format --check .`. Report any existing unrelated failures separately.
- After approval and configured provider access, perform a live smoke test using the supplied tender and a structurally different PDF. Compare outputs to source evidence. Record runtime and issues; do not claim this has already passed.

### Completion criteria

A non-hardcoded PDF uploaded over HTTP produces both valid outputs, with preserved evidence and no AI decision. Generic large-table routing avoids duplicated large-table bodies when confidently mapped and never loses structured coverage. All required automated checks pass; real parser/model smoke-test outcomes or blockers are recorded. Stop for explicit human verification before Phase 2.

## Phase 2 — Core Frontend + Tender Analysis UI

### Objective

Build the professional PDF upload and detailed review workflow in Next.js, React, TypeScript, and Tailwind, connected to the real API.

### Files to create or modify

Create:

- `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, `frontend/next-env.d.ts`, `frontend/next.config.ts`, `frontend/postcss.config.mjs`, `frontend/eslint.config.mjs`, `frontend/.env.example` — minimal pinned frontend setup and public API-base configuration.
- `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/globals.css` — application shell, in-memory workflow, and visual tokens.
- `frontend/src/lib/api.ts`, `frontend/src/lib/schemas.ts`, `frontend/src/lib/requirements.ts` — multipart request helper, runtime response validation/types, category labels and deterministic filtering/matrix transforms.
- `frontend/src/components/tender-upload.tsx`, `frontend/src/components/analysis-loading.tsx`, `frontend/src/components/error-state.tsx`, `frontend/src/components/results-shell.tsx`.
- `frontend/src/components/tender-analysis.tsx`, `frontend/src/components/requirement-card.tsx`, `frontend/src/components/requirement-filters.tsx`, `frontend/src/components/compliance-matrix.tsx`, `frontend/src/components/raw-json-panel.tsx`.
- `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/test/fixtures.ts`, `frontend/src/test/requirements.test.ts`, `frontend/src/test/upload.test.tsx`, `frontend/src/test/tender-analysis.test.tsx`, `frontend/src/test/api.test.ts`.

Modify `README.md` with frontend startup, environment, build, and test commands. Backend changes are limited to contract defects exposed by integration, in the Phase 1 files; document any necessary changes before making them.

### Backend work

Verify configured CORS and successful uploads from the development frontend. Preserve the Phase 1 API contract; no new endpoint, LLM call, persistence, or progress infrastructure is needed.

### Frontend work

1. Build a clean procurement application shell with restrained typography, accessible colors, clear hierarchy, and no chat interface.
2. Implement accessible drag-and-drop and a Select PDF button, filename, readable file size, remove/replace actions, PDF/size prechecks, and Analyze Tender. Backend validation remains authoritative.
3. Manage idle, selected, analyzing, success, and error states explicitly. Disable duplicate submissions and clear stale results when starting another tender.
4. Show an indeterminate processing screen with elapsed time and a truthful description that parsing and analysis are underway. Do not display completed backend stages or percentages without actual signals. No automatic retry of analysis requests.
5. Render all 15 categories with a stable navigation order and empty-category states. Display category status separately from each item's status and requirement type.
6. Display requirement cards/rows with source sections and expandable evidence. Render extracted content as escaped text; do not execute uploaded HTML.
7. Provide All/Mandatory/Conditional/Informational filters, an independent External References filter, and text search across requirement text, sections, and evidence. Define filters as intersections and show a clear zero-results state.
8. Build the Compliance Matrix from `tender_analysis.categories[].requirements` using the same filters and evidence controls. It shows extraction status, not an invented assessment of the bidder's compliance.
9. Provide a collapsed View Raw JSON developer panel containing the actual response. Keep it secondary to structured UI components.
10. Retain both response objects in typed application state. Phase 2 delivers the Tender Analysis view; Phase 3 adds and defaults to Decision Support. Do not render a fake report or an inactive report tab as a finished feature.
11. Implement understandable messages and manual retry/replace-file paths for server errors, malformed responses, timeouts, and an unavailable backend. Explain that leaving the screen does not guarantee server cancellation.

### API contracts

Consume `POST /api/analyze` directly using `NEXT_PUBLIC_API_BASE_URL`; this value is public configuration, never a secret. Validate the response at runtime before rendering and check frontend types against backend OpenAPI/fixtures. Set the request timeout consistently with the backend's configured analysis budget. Preserve `tender_analysis` and `decision_support_report` as separate objects.

### Testing

- Component/unit tests: keyboard file selection, drop, replace/remove, duplicate-submit prevention, loading/error transitions, invalid payload handling, category statuses, mixed requirement statuses, filter intersections, source/evidence expansion, and matrix equality with source requirements.
- Include malicious-looking source text in fixtures and verify it renders as text.
- Verify no-table tenders, empty findings, long evidence, and narrow-screen navigation.
- Run frontend lint, TypeScript checks, component tests, and a production build; rerun backend tests if backend files change.
- Manually upload a real PDF through the UI to the backend and inspect the rendered response. Use mocked responses only for deterministic UI tests, clearly distinguished from this integration check.

### Completion criteria

A user can select a PDF, see honest loading feedback, recover from errors, and review structured requirements and the derived matrix with evidence. No JSON inspection is required. Frontend checks pass, and the browser-to-backend flow is verified or an explicit external blocker is recorded. Stop for explicit human verification before Phase 3.

## Phase 3 — Decision Support UX + Polish

### Objective

Complete the evidence-based decision-support experience, make it the default results view, and verify the full application.

### Files to create or modify

Create:

- `frontend/src/components/decision-support.tsx`, `frontend/src/components/summary-metrics.tsx`, `frontend/src/components/report-section.tsx`.
- `frontend/src/test/decision-support.test.tsx`, `frontend/playwright.config.ts`, `frontend/e2e/tender-review.spec.ts`.
- `tests/integration/test_end_to_end_analysis.py` — full backend pipeline using real document fixtures and deterministic model substitutes, with separately marked live-provider coverage.

Modify:

- `frontend/src/components/results-shell.tsx`, `frontend/src/components/tender-analysis.tsx`, `frontend/src/components/compliance-matrix.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/globals.css` — final two-view navigation, responsive/accessibility polish, review links, and state handling.
- `frontend/src/lib/requirements.ts`, `frontend/src/test/requirements.test.ts`, `frontend/src/test/fixtures.ts` — deterministic summary metrics and final fixtures.
- `frontend/package.json`, `frontend/package-lock.json` — browser-test dependencies/scripts.
- `README.md` — complete runbook, measured smoke-test results, known limits, and verification checklist.

Any integration fixes to Phase 1/2 source and test files must stay within the approved architecture and be identified in the phase completion report.

### Backend work

Use the existing `decision_support_report` from `generate_report`; do not add another LLM call for UI summaries, counts, or the compliance matrix. Resolve only demonstrated contract, reliability, or evidence-preservation defects and rerun affected checks.

### Frontend work

1. Add two main result views: Decision Support and Tender Analysis. Default to Decision Support after successful analysis.
2. Render the executive summary and all seven list sections: reasons to consider bidding, concerns and risks, missing information, mandatory requirements, conditional requirements, external references to review, and questions for the bid team.
3. Calculate summary metrics from final structured requirements, never report-summary list lengths: mandatory count = `MANDATORY` and status other than `NOT_REQUIRED`; conditional count = `CONDITIONAL` and status other than `NOT_REQUIRED`; external-reference count = `EXTERNAL_REFERENCE`. External-reference counts may overlap the other metrics; do not add them into a total.
4. Let metrics navigate to the matching Tender Analysis filters. The report schema contains plain strings without requirement IDs, so do not invent exact evidence links for narrative bullets. Provide links to relevant filtered extraction views where deterministically justified and a general Review Evidence action otherwise.
5. Explain `NOT_FOUND` as no extracted evidence, `NOT_REQUIRED` as an explicit source statement, and external references as needing review. Do not label an external reference resolved just because it was displayed.
6. Display the human-decision boundary clearly. No automated BID/NO BID badge or verdict. Questions may have session-only review checkboxes; these do not claim compliance or persist team decisions.
7. Handle empty report lists honestly, such as “No items identified in this analysis,” without implying the tender has no risk. Preserve long text, dates, quantities, and monetary strings without truncating important evidence.
8. Polish responsive layouts, keyboard navigation, visible focus, accessible tab behavior, semantic headings, status text labels, contrast, loading announcements, and readable evidence controls. Verify desktop and mobile layouts.

### API contracts

No new endpoints or schema changes are planned. Render `decision_support_report` separately from `tender_analysis`; derive metrics and matrix rows locally. Any unavoidable contract change must update backend validation, frontend runtime schema, fixtures, and documentation together.

### Testing

- Tests for every report field, empty lists, overlapping metrics, `NOT_REQUIRED` exclusion, default tab, tab switching, metric-to-filter navigation, and the persistent human-decision notice.
- Browser tests for the complete upload → loading → Decision Support → Tender Analysis → evidence → matrix flow, plus upload failure, backend failure, and malformed-response recovery.
- Accessibility and responsive checks with keyboard-only use and desktop/mobile viewports. Inspect screenshots of upload, loading, errors, and both result views.
- Run all backend and frontend checks once after final changes. Run actual Docling integration fixtures and a separately identified live model smoke test on at least two different tender structures when configured access is available.
- Inspect source evidence for selected mandatory, conditional, external-reference, and table-derived findings. Check for omissions, invented details, inappropriate verdicts, and runtime/provider-limit problems. Automated schemas cannot prove extraction accuracy.

### Completion criteria

The full upload-to-review workflow works, Decision Support is the default, both outputs remain independently inspectable, and evidence and matrix views support human review. Required checks pass and live-test outcomes are recorded accurately. No AI final decision or excluded MVP feature is introduced. Stop for final human verification.

## Main risks and review checkpoints

- The current module has an undefined table input and import-time work. Phase 1 must establish standalone correctness before the frontend is built.
- PDF layout, scans, OCR quality, and table structure vary. “Any tender PDF” means no tender-specific names or assumptions; unreadable, encrypted, oversized, or unprocessable files receive clear errors, not fabricated analysis.
- Large or numerous tables can exceed worker or reducer budgets. Preserve coverage through bounded batches and fail explicitly when limits are exceeded; do not truncate silently.
- Synchronous analysis can take minutes, consume memory, and encounter browser/proxy deadlines. Start as a local single-process MVP, measure runtime, and document hosting limits before deployment. A thread timeout is not a hard processing kill.
- Model output is probabilistic. Schema validation, no-verdict checks, and regression tests reduce failures but do not establish factual completeness. Evidence review remains central.
- The report contains summary strings without evidence IDs. Preserve that schema for this MVP rather than implying links it cannot support.
- Uploads and extracted content are sent to the configured model provider during analysis. State this plainly near upload and in setup documentation; avoid retaining uploaded documents after processing.
- No implementation phase is authorized by the creation of this plan. After plan review, implement Phase 1 only, verify it, and stop as required by `AGENTS.md`.

## Primary technical references

The design preserves LangGraph's `Send` map/reduce approach and uses FastAPI multipart upload handling and Docling's structured tables. Exact installed interfaces will be checked during implementation.

- [LangGraph graph API and reducers](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph Send reference](https://reference.langchain.com/python/langgraph/types/Send)
- [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
- [Docling document reference](https://docling-project.github.io/docling/reference/docling_document/)
- [Docling table export example](https://github.com/docling-project/docling/blob/main/docs/examples/export_tables.py)
