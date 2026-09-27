"""The notebook agent, exposed as callables without import-time execution.

Prompts, schemas, heading chunking, and graph topology are preserved. Only the
copy is adapted; the original main.py is never imported by the demo.
"""

from __future__ import annotations

import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Annotated, Any, Literal, Protocol, TypedDict, get_args

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field


class Requirement(BaseModel):
    category: Literal[
        "submission",
        "required_documents",
        "certifications",
        "insurance",
        "bonding_security",
        "experience",
        "personnel",
        "technical",
        "financial",
        "formatting",
        "legal_regulatory",
        "language",
        "security",
        "site_meeting",
        "signatures",
    ]

    requirement: str

    status: Literal[
        "FOUND",
        "NOT_REQUIRED",
        "EXTERNAL_REFERENCE",
    ]

    source_section: str

    evidence: str


class ChunkFindings(BaseModel):
    requirements: list[Requirement] = Field(default_factory=list)


class WorkerState(TypedDict):
    chunk: Document


class FinalRequirementItem(BaseModel):
    requirement: str

    status: Literal[
        "FOUND",
        "NOT_REQUIRED",
        "EXTERNAL_REFERENCE",
    ]

    requirement_type: Literal[
        "MANDATORY",
        "CONDITIONAL",
        "INFORMATIONAL",
    ]

    source_sections: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class RequirementCategory(BaseModel):
    category: Literal[
        "submission",
        "required_documents",
        "certifications",
        "insurance",
        "bonding_security",
        "experience",
        "personnel",
        "technical",
        "financial",
        "formatting",
        "legal_regulatory",
        "language",
        "security",
        "site_meeting",
        "signatures",
    ]

    status: Literal[
        "FOUND",
        "NOT_FOUND",
    ]

    requirements: list[FinalRequirementItem] = Field(default_factory=list)


class TenderAnalysis(BaseModel):
    categories: list[RequirementCategory]


class DecisionSupportReport(BaseModel):
    executive_summary: str

    reasons_to_consider_bidding: list[str] = Field(default_factory=list)

    concerns_and_risks: list[str] = Field(default_factory=list)

    missing_information: list[str] = Field(default_factory=list)

    mandatory_requirements: list[str] = Field(default_factory=list)

    conditional_requirements: list[str] = Field(default_factory=list)

    external_references_to_review: list[str] = Field(default_factory=list)

    questions_for_bid_team: list[str] = Field(default_factory=list)


class TenderState(TypedDict):
    chunks: list[Document]
    tables: list[dict[str, Any]]
    findings: Annotated[list[Requirement], operator.add]

    final_analysis: TenderAnalysis
    decision_report: DecisionSupportReport


class TableWorkerState(TypedDict):
    table_number: int
    table_data: str


class StructuredModel(Protocol):
    """Minimum provider surface, also implemented by deterministic test doubles."""

    def with_structured_output(self, schema: type[BaseModel]) -> Any:
        """Return a runnable producing the supplied schema."""
        ...


Observer = Callable[..., None]


def ignore_event(*args: Any, **kwargs: Any) -> None:
    """Permit ordinary script callers to run without dashboard instrumentation."""


@dataclass
class PreparedInputs:
    """Retain exact worker inputs and observable preparation counts."""

    chunks: list[Document]
    tables: list[dict[str, Any]]
    total_chunks: int
    filtered_short: int
    filtered_table: int


class PreparationError(ValueError):
    """Reject incomplete sample preparation rather than hide missing evidence."""


def split_markdown(markdown: str) -> tuple[list[Document], list[Document], int]:
    """Apply the notebook's header settings and both original filters verbatim."""
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "title"), ("##", "section"), ("###", "subsection")],
        strip_headers=False,
    )
    chunks = splitter.split_text(markdown)
    clean, excluded = [], []
    short = 0
    for index, chunk in enumerate(chunks, 1):
        chunk.metadata["chunk_id"] = f"chunk-{index}"
        if len(chunk.page_content.strip()) < 50:
            short += 1
            continue
        if chunk.metadata.get("section") == "UNIT PRICE TABLE":
            excluded.append(chunk)
            continue
        clean.append(chunk)
    return clean, excluded, short


def _rows(markdown: str) -> set[tuple[str, ...]]:
    """Normalize table rows for conservative verification of the prototype skip."""
    rows = set()
    for line in markdown.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = tuple(
            re.sub(r"\s+", "", cell).casefold()
            for cell in line.strip().strip("|").split("|")
        )
        if cells and not all(re.fullmatch(r"[-:]*", cell) for cell in cells):
            rows.add(cells)
    return rows


def prepare_document(
    document: Any, max_workers: int = 500, max_input_characters: int = 2_000_000
) -> PreparedInputs:
    """Use one Docling document for the original text path and all table inputs.

    Skipped table rows must have structured coverage. This intentionally retains
    the sample-specific filter, including its loss of surrounding section prose.
    """
    markdown = document.export_to_markdown()
    clean, excluded, short = split_markdown(markdown)
    tables, represented_rows = [], set()
    for number, table in enumerate(document.tables, 1):
        frame = table.export_to_dataframe(doc=document).fillna("")
        serialized = frame.to_markdown(index=False)
        original_rows = _rows(table.export_to_markdown(doc=document))
        normalized = re.sub(r"\s+", "", serialized).casefold()
        # Match the original exported rows and verify their cells survived the
        # DataFrame conversion before treating the table as covered.
        for row in original_rows:
            if all(cell in normalized for cell in row if cell):
                represented_rows.add(row)
        tables.append({"table_number": number, "table_data": serialized})
    skipped_rows = set().union(*(_rows(chunk.page_content) for chunk in excluded))
    if excluded and (not skipped_rows or not skipped_rows.issubset(represented_rows)):
        raise PreparationError("Excluded table coverage could not be verified.")
    if not clean and not tables:
        raise PreparationError("No usable worker inputs remain.")
    if len(clean) + len(tables) > max_workers:
        raise PreparationError("Sample exceeds the configured worker limit.")
    characters = sum(len(c.page_content) for c in clean) + sum(
        len(t["table_data"]) for t in tables
    )
    if characters > max_input_characters:
        raise PreparationError("Sample exceeds the configured input limit.")
    return PreparedInputs(
        clean, tables, len(clean) + len(excluded) + short, short, len(excluded)
    )


def parse_pdf(path: Path) -> Any:
    """Load Docling lazily and reject partial or failed conversion."""
    from docling.datamodel.base_models import ConversionStatus
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(path)
    if result.status != ConversionStatus.SUCCESS:
        raise PreparationError("Docling did not fully convert the sample.")
    return result.document


def validate_analysis(analysis: TenderAnalysis) -> TenderAnalysis:
    """Enforce the reducer prompt's category invariants without inventing data."""
    expected = set(get_args(RequirementCategory.model_fields["category"].annotation))
    actual = [category.category for category in analysis.categories]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("The reducer must return each category exactly once.")
    for category in analysis.categories:
        if (category.status == "FOUND") != bool(category.requirements):
            raise ValueError("Category status and requirements disagree.")
    return analysis


class TenderAgent:
    """Own per-run model adapters while preserving the notebook's node prompts."""

    def __init__(self, model: StructuredModel) -> None:
        """Inject a configured provider or a deterministic model substitute."""
        self.extractor = model.with_structured_output(ChunkFindings)
        self.reducer_llm = model.with_structured_output(TenderAnalysis)
        self.report_llm = model.with_structured_output(DecisionSupportReport)

    def analyze_chunk(self, state: WorkerState) -> dict[str, Any]:
        """Run the original analyze_chunk prompt and return its typed state update."""

        chunk = state["chunk"]

        section = chunk.metadata.get("section", "Unknown Section")

        prompt = f"""
You are analyzing one section of a government tender.

Extract ONLY requirements explicitly supported by this section.

Categories:
- submission
- required_documents
- certifications
- insurance
- bonding_security
- experience
- personnel
- technical
- financial
- formatting
- legal_regulatory
- language
- security
- site_meeting
- signatures

Status rules:

FOUND:
The tender states that a requirement exists.

NOT_REQUIRED:
The tender explicitly states that something is not required.

EXTERNAL_REFERENCE:
The requirement exists, but its details are defined in another
document, clause, standard, appendix, website, or referenced source.

Important:
- Do not return NOT_FOUND.
- Do not invent requirements.
- If this section contains no relevant requirement, return an empty list.
- Preserve concrete details such as dates, dollar amounts, deadlines,
  forms, insurance limits, bond requirements, and submission rules.
- Evidence should contain the relevant supporting text from this section.

IMPORTANT CATEGORY DISTINCTIONS:

bonding_security:
Financial security associated with the bid or contract, such as:
- bid bonds
- bid security
- performance bonds
- labour and material payment bonds
- deposits
- contract security

security:
Personnel, organization, facility, or government security requirements,
such as:
- security clearances
- reliability status
- protected/classified information
- site security screening

Never classify "no security requirement" as bonding_security.

EXPERIENCE RULE:

Classify something as "experience" only when the bidder is required
to demonstrate qualifications or experience, such as:

- minimum years of experience
- previous similar projects
- project references
- demonstrated expertise
- required past project history

Do NOT classify general past-performance evaluation or Canada's
right to reject a bidder for poor previous performance as an
experience requirement.

Those conditions belong under legal_regulatory unless the tender
explicitly requires the bidder to demonstrate experience.

SECTION:
{section}

CONTENT:
{chunk.page_content}
"""

        result = self.extractor.invoke(prompt)

        return {"findings": result.requirements}

    def reduce_findings(self, state: TenderState) -> dict[str, Any]:
        """Run the original reduce_findings prompt and return its typed state update."""

        findings = state["findings"]

        findings_text = "\n\n".join(finding.model_dump_json() for finding in findings)

        prompt = f"""
You are performing the final compliance analysis of a government tender.

Multiple workers independently analyzed text sections and tables.

Consolidate their findings into ONE tender-level analysis.

Return exactly one category for each:

1. submission
2. required_documents
3. certifications
4. insurance
5. bonding_security
6. experience
7. personnel
8. technical
9. financial
10. formatting
11. legal_regulatory
12. language
13. security
14. site_meeting
15. signatures


CATEGORY STATUS:

FOUND:
At least one legitimate requirement or explicit statement
was identified for this category.

NOT_FOUND:
No legitimate requirement or explicit statement was identified
for this category anywhere in the analyzed tender.

If status is NOT_FOUND, requirements must be an empty list.


INDIVIDUAL REQUIREMENT STATUS:

FOUND:
The tender directly establishes the requirement.

NOT_REQUIRED:
The tender explicitly states that this specific requirement
does not apply or is not required.

EXTERNAL_REFERENCE:
The tender indicates that the requirement exists, but important
details are defined in another referenced clause, document,
form, standard, appendix, or source.


IMPORTANT:

A category may contain requirements with DIFFERENT statuses.

For example:

bonding_security
    Bid security must be submitted → FOUND
    Amount defined in GI09 → EXTERNAL_REFERENCE

Do not collapse those into one status.


BONDING VS SECURITY:

bonding_security means financial security such as:
- bid security
- bid bonds
- performance bonds
- labour and material payment bonds
- deposits
- contract security

security means government/personnel/facility security such as:
- security clearance
- reliability status
- protected/classified information
- personnel screening

"No security requirement" refers to the security category.
It does NOT mean that bid security or bonding is not required.


EXPERIENCE:

Only classify a finding as experience when the bidder must
demonstrate qualifications or experience, such as:
- years of experience
- similar projects
- project references
- demonstrated expertise
- required project history

General past-performance evaluation or Canada's right to reject
a bidder because of poor previous performance is NOT an
experience qualification.

Such conditions should normally be classified under
legal_regulatory.


CONSOLIDATION RULES:

- Combine duplicate findings.
- Combine evidence from text and tables when they describe the
  same requirement.
- Do not invent requirements.
- Preserve specific numbers, dates, deadlines, forms, quantities,
  insurance limits, bond requirements and submission rules.
- Preserve useful source sections.
- Prefer direct tender evidence over inference.
- Do not treat the absence of information as NOT_REQUIRED.
- NOT_REQUIRED requires an explicit statement.
- EXTERNAL_REFERENCE does not mean NOT_FOUND.


REQUIREMENT TYPE:

For every individual requirement, assign exactly one:

MANDATORY:
The bidder or contractor must, shall, is required to, or otherwise
has to satisfy the requirement.

This includes requirements where failure to comply could make the
bid non-responsive or prevent contract performance.

Examples:
- Submit the bid before the closing deadline.
- Provide bid security.
- Sign the bid.
- Maintain required insurance.
- Provide required pricing.
- Complete the work within the required period.


CONDITIONAL:
The requirement applies only if a stated condition, circumstance,
event, or trigger occurs.

Examples:
- Provide pardon documentation if applicable.
- Obtain approval if proposing alternative materials.
- Provide additional insurance coverage where the work involves
  specified hazards.
- Provide documents upon Canada's request.


INFORMATIONAL:
The statement provides context, process information, Canada's rights,
administrative information, or other information that does not itself
require the bidder to take an action to make the bid compliant.

Examples:
- Canada may reject unreasonable prices.
- Canada may cancel the solicitation.
- A public bid opening will occur after closing.
- Canada may correct arithmetic errors.


IMPORTANT:

Classify based on what the BIDDER or CONTRACTOR is required to do,
not merely because the statement uses words such as "must" or "shall."

A rule describing what Canada may or will do is generally INFORMATIONAL.

NOT_REQUIRED requirements should normally be INFORMATIONAL because
they tell the bidder that an obligation does not apply.


WORKER FINDINGS:

{findings_text}
"""

        analysis = validate_analysis(
            TenderAnalysis.model_validate(self.reducer_llm.invoke(prompt))
        )

        return {"final_analysis": analysis}

    def analyze_table(self, state: TableWorkerState) -> dict[str, Any]:
        """Run the original analyze_table prompt and return its typed state update."""

        table_number = state["table_number"]
        table_data = state["table_data"]

        prompt = f"""
You are analyzing a table extracted from a government tender.

Extract ONLY tender requirements explicitly supported by this table.

Categories:
- submission
- required_documents
- certifications
- insurance
- bonding_security
- experience
- personnel
- technical
- financial
- formatting
- legal_regulatory
- language
- security
- site_meeting
- signatures

Status rules:

FOUND:
The table contains or establishes a requirement.

NOT_REQUIRED:
The table explicitly states that something is not required.

EXTERNAL_REFERENCE:
The table references another document, form, clause,
standard, appendix, or source that defines the requirement.

Important:
- Do not return NOT_FOUND.
- Do not invent requirements.
- Preserve quantities, units, prices, specification references,
  forms, dates, limits, and other concrete details.
- If the table contains no relevant requirements, return an empty list.

IMPORTANT CATEGORY DISTINCTIONS:

bonding_security:
Financial security associated with the bid or contract, such as:
- bid bonds
- bid security
- performance bonds
- labour and material payment bonds
- deposits
- contract security

security:
Personnel, organization, facility, or government security requirements,
such as:
- security clearances
- reliability status
- protected/classified information
- site security screening

Never classify "no security requirement" as bonding_security.

EXPERIENCE RULE:

Classify something as "experience" only when the bidder is required
to demonstrate qualifications or experience, such as:

- minimum years of experience
- previous similar projects
- project references
- demonstrated expertise
- required past project history

Do NOT classify general past-performance evaluation or Canada's
right to reject a bidder for poor previous performance as an
experience requirement.

Those conditions belong under legal_regulatory unless the tender
explicitly requires the bidder to demonstrate experience.

For source_section use:
"Table {table_number}"

TABLE:

{table_data}
"""

        result = self.extractor.invoke(prompt)

        return {"findings": result.requirements}

    def generate_report(self, state: TenderState) -> dict[str, Any]:
        """Run the original generate_report prompt and return its typed state update."""

        analysis = state["final_analysis"]

        analysis_json = analysis.model_dump_json(indent=2)

        prompt = f"""
You are assisting a proposal team reviewing a government tender.

You have been given a structured analysis of the tender.

Your job is to create a decision-support report that helps a HUMAN
decide whether the company should bid.

You must NOT make the bid/no-bid decision.

Do NOT say:
- BID
- NO BID
- We recommend bidding
- We recommend not bidding

Instead, organize the available evidence so the human can make
the decision.


EXECUTIVE SUMMARY

Provide a concise overview of the opportunity and the most important
requirements, risks, constraints, and unresolved issues.


REASONS TO CONSIDER BIDDING

Identify characteristics of the tender that may make the opportunity
worth considering.

Only use evidence available in the tender analysis.

Do not assume anything about the bidder's capabilities.


CONCERNS AND RISKS

Identify requirements or conditions that could create difficulty,
cost, compliance risk, scheduling risk, contractual risk, or
submission risk.

Examples include:
- tight deadlines
- bonding
- insurance
- unusual technical requirements
- strict submission rules
- significant contractual obligations


MISSING INFORMATION

Identify information required for evaluating the opportunity that
cannot be determined from the tender analysis.

Also include important requirements whose details are contained in
external references that still need to be reviewed.


MANDATORY REQUIREMENTS

Summarize the most important mandatory requirements that could affect
the decision to pursue the opportunity.

Do not simply repeat every extracted requirement. Prioritize those
that materially affect eligibility, compliance, cost, schedule,
technical delivery, or submission.


CONDITIONAL REQUIREMENTS

Identify important requirements that become applicable only under
specific circumstances.


EXTERNAL REFERENCES TO REVIEW

Identify referenced clauses, forms, standards, drawings,
specifications, or other documents that should be reviewed before
making the bid/no-bid decision.


QUESTIONS FOR THE BID TEAM

Generate practical questions the human team should answer before
making a decision.

Examples:

- Can we meet the required construction schedule?
- Can we obtain the required bonding?
- Do our insurance limits satisfy the requirement?
- Do we have the resources and capacity to perform the work?
- Have all external specifications and drawings been reviewed?
- Can we price the required scope competitively?

Do not assume the answers.


IMPORTANT RULES

- Base the report only on the supplied tender analysis.
- Do not invent company capabilities.
- Do not invent tender requirements.
- Clearly identify uncertainty.
- Treat EXTERNAL_REFERENCE findings as unresolved until reviewed.
- Treat NOT_FOUND as absence of extracted evidence, not proof that
  the tender has no such requirement.
- Do not make the final bid/no-bid decision.
- The final decision belongs to the human proposal team.


TENDER ANALYSIS:

{analysis_json}
"""

        report = self.report_llm.invoke(prompt)

        return {"decision_report": report}

    def build_graph(self, observe: Observer = ignore_event) -> Any:
        """Wrap actual node entry/exit; leave the original graph topology intact."""

        def wrap(
            name: str, call: Callable[..., dict[str, Any]]
        ) -> Callable[..., dict[str, Any]]:
            def execute(state: Any) -> dict[str, Any]:
                worker_id = None
                label = name
                if name == "analyze_chunk":
                    worker_id = state["chunk"].metadata["chunk_id"]
                    label = state["chunk"].metadata.get("section", "Unknown Section")
                elif name == "analyze_table":
                    worker_id = f"table-{state['table_number']}"
                    label = f"Table {state['table_number']}"
                prefix = "worker" if worker_id else "stage"
                start = monotonic()
                observe(
                    f"{prefix}.started",
                    stage=name,
                    worker_id=worker_id,
                    summary=f"{label}: started.",
                )
                try:
                    update = call(state)
                except Exception:
                    if worker_id:
                        observe(
                            "worker.failed",
                            stage=name,
                            worker_id=worker_id,
                            summary=f"{label}: failed.",
                            duration_ms=int((monotonic() - start) * 1000),
                        )
                    raise
                data = {"findings_count": len(update["findings"])} if worker_id else {}
                # Output is supplied separately to the observer, never in SSE data.
                observe(
                    f"{prefix}.completed",
                    stage=name,
                    worker_id=worker_id,
                    summary=f"{label}: completed.",
                    data=data,
                    duration_ms=int((monotonic() - start) * 1000),
                    output=update if not worker_id else None,
                )
                return update

            return execute

        builder = StateGraph(TenderState)
        for name in (
            "analyze_chunk",
            "analyze_table",
            "reduce_findings",
            "generate_report",
        ):
            builder.add_node(name, wrap(name, getattr(self, name)))
        builder.add_conditional_edges(START, map_chunks, ["analyze_chunk"])
        builder.add_conditional_edges(START, map_tables, ["analyze_table"])
        builder.add_edge("analyze_chunk", "reduce_findings")
        builder.add_edge("analyze_table", "reduce_findings")
        builder.add_edge("reduce_findings", "generate_report")
        builder.add_edge("generate_report", END)
        return builder.compile()


def map_chunks(state: TenderState) -> list[Send]:
    """Route prepared inputs to the existing parallel worker node."""

    return [Send("analyze_chunk", {"chunk": chunk}) for chunk in state["chunks"]]


def map_tables(state: TenderState) -> list[Send]:
    """Route prepared inputs to the existing parallel worker node."""

    return [
        Send(
            "analyze_table",
            {"table_number": table["table_number"], "table_data": table["table_data"]},
        )
        for table in state["tables"]
    ]


def run_tender(
    path: Path,
    model: StructuredModel,
    observe: Observer = ignore_event,
    parser: Callable[[Path], Any] = parse_pdf,
    max_concurrency: int = 4,
    max_workers: int = 500,
    max_input_characters: int = 2_000_000,
) -> dict[str, Any]:
    """Execute parsing, preparation, and the preserved graph once per run."""
    document = None
    for stage in ("parse_document", "prepare_inputs"):
        start = monotonic()
        observe("stage.started", stage=stage, summary=f"{stage}: started.")
        if stage == "parse_document":
            document = parser(path)
            data = {}
        else:
            prepared = prepare_document(document, max_workers, max_input_characters)
            data = {
                "total_chunks": prepared.total_chunks,
                "text_chunks": len(prepared.chunks),
                "tables": len(prepared.tables),
                "filtered_chunks": prepared.filtered_short + prepared.filtered_table,
            }
            workers = [
                {
                    "id": c.metadata["chunk_id"],
                    "stage": "analyze_chunk",
                    "label": c.metadata.get("section", "Unknown Section"),
                }
                for c in prepared.chunks
            ]
            workers += [
                {
                    "id": f"table-{t['table_number']}",
                    "stage": "analyze_table",
                    "label": f"Table {t['table_number']}",
                }
                for t in prepared.tables
            ]
            observe("inputs.prepared", data=data, workers=workers)
            if prepared.filtered_short or prepared.filtered_table:
                observe(
                    "run.warning",
                    stage=stage,
                    summary=(
                        f"Prototype filters removed {prepared.filtered_short} short chunks and "
                        f"{prepared.filtered_table} UNIT PRICE TABLE sections, including surrounding prose. "
                        "Structured table coverage was verified; extraction may omit filtered prose."
                    ),
                    data={"code": "PROTOTYPE_FILTERS"},
                )
        observe(
            "stage.completed",
            stage=stage,
            summary=f"{stage}: completed.",
            duration_ms=int((monotonic() - start) * 1000),
            data=data,
        )
    for name, values in [
        ("analyze_chunk", prepared.chunks),
        ("analyze_table", prepared.tables),
    ]:
        if not values:
            observe("stage.skipped", stage=name, summary="No inputs for this branch.")
    graph = TenderAgent(model).build_graph(observe)
    return graph.invoke(
        {"chunks": prepared.chunks, "tables": prepared.tables, "findings": []},
        config={"max_concurrency": max_concurrency},
    )


def main() -> None:
    """Retain a standalone script entry point using the demo's environment settings."""
    from langchain_openai import ChatOpenAI

    from demo_api.config import Settings

    settings = Settings.from_env()
    model = ChatOpenAI(
        model=settings.model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    result = run_tender(
        settings.sample_path,
        model,
        max_concurrency=settings.graph_concurrency,
        max_workers=settings.max_workers,
        max_input_characters=settings.max_input_characters,
    )
    print(result["final_analysis"].model_dump_json(indent=2))
    print(result["decision_report"].model_dump_json(indent=2))


if __name__ == "__main__":
    main()
