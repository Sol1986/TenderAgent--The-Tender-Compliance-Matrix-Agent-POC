from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Literal
from langchain_text_splitters import MarkdownHeaderTextSplitter
from docling.document_converter import DocumentConverter
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Literal
from typing import TypedDict, Annotated
import operator

load_dotenv()

llm = ChatOpenAI(
    model="gpt-5.6-luna"
)


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
    chunk: object


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

    requirements: list[FinalRequirementItem] = Field(
        default_factory=list
    )


class TenderAnalysis(BaseModel):
    categories: list[RequirementCategory]

class DecisionSupportReport(BaseModel):
    executive_summary: str

    reasons_to_consider_bidding: list[str] = Field(
        default_factory=list
    )

    concerns_and_risks: list[str] = Field(
        default_factory=list
    )

    missing_information: list[str] = Field(
        default_factory=list
    )

    mandatory_requirements: list[str] = Field(
        default_factory=list
    )

    conditional_requirements: list[str] = Field(
        default_factory=list
    )

    external_references_to_review: list[str] = Field(
        default_factory=list
    )

    questions_for_bid_team: list[str] = Field(
        default_factory=list
    )

class TenderState(TypedDict):
    chunks: list
    tables: list
    findings: Annotated[list[Requirement], operator.add]
    
    final_analysis: TenderAnalysis
    decision_report: DecisionSupportReport


class TableWorkerState(TypedDict):
    table_number: int
    table_data: str




pdf_path = Path("tender.pdf")

if not pdf_path.exists():
    raise FileNotFoundError(f"Could not find {pdf_path}")



source = "tender.PDF"  # a document via a local path or URL
converter = DocumentConverter()
result = converter.convert(source)


markdown = result.document.export_to_markdown()

with open("tender.md", "w", encoding="utf-8") as f:
    f.write(markdown)



with open("tender.md", "r", encoding="utf-8") as f:
    markdown = f.read()

headers_to_split_on = [
    ("#", "title"),
    ("##", "section"),
    ("###", "subsection"),
]

splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False
)

chunks = splitter.split_text(markdown)


clean_chunks = []

for chunk in chunks:

    # Remove tiny / useless chunks
    if len(chunk.page_content.strip()) < 50:
        continue

    # Don't use the giant unit price table as text
    if chunk.metadata.get("section") == "UNIT PRICE TABLE": #### This should change to whatever table that is very large 
        continue

    clean_chunks.append(chunk)




extractor = llm.with_structured_output(ChunkFindings)


def analyze_chunk(state: WorkerState):

    chunk = state["chunk"]

    section = chunk.metadata.get(
        "section",
        "Unknown Section"
    )

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

    result = extractor.invoke(prompt)

    return {
        "findings": result.requirements
    }


def map_chunks(state: TenderState):

    return [
        Send(
            "analyze_chunk",
            {"chunk": chunk}
        )
        for chunk in state["chunks"]
    ]



reducer_llm = llm.with_structured_output(TenderAnalysis)

def reduce_findings(state: TenderState):

    findings = state["findings"]

    findings_text = "\n\n".join(
        finding.model_dump_json()
        for finding in findings
    )

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

    analysis = reducer_llm.invoke(prompt)

    return {
        "final_analysis": analysis
    }



def analyze_table(state: TableWorkerState):

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

    result = extractor.invoke(prompt)

    return {
        "findings": result.requirements
    }

extractor = llm.with_structured_output(ChunkFindings)

def map_tables(state: TenderState):

    return [
        Send(
            "analyze_table",
            {
                "table_number": table["table_number"],
                "table_data": table["table_data"]
            }
        )
        for table in state["tables"]
    ]

report_llm = llm.with_structured_output(
    DecisionSupportReport
)


def generate_report(state: TenderState):

    analysis = state["final_analysis"]

    analysis_json = analysis.model_dump_json(
        indent=2
    )

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

    report = report_llm.invoke(prompt)

    return {
        "decision_report": report
    }



builder = StateGraph(TenderState)

builder.add_node(
    "analyze_chunk",
    analyze_chunk
)

builder.add_node(
    "analyze_table",
    analyze_table
)

builder.add_node(
    "reduce_findings",
    reduce_findings
)

builder.add_node(
    "generate_report",
    generate_report
)

builder.add_conditional_edges(
    START,
    map_chunks,
    ["analyze_chunk"]
)

builder.add_conditional_edges(
    START,
    map_tables,
    ["analyze_table"]
)

builder.add_edge(
    "analyze_chunk",
    "reduce_findings"
)

builder.add_edge(
    "analyze_table",
    "reduce_findings"
)

builder.add_edge(
    "reduce_findings",
    "generate_report"
)

builder.add_edge(
    "generate_report",
    END
)

graph = builder.compile()

final_result = graph.invoke({
    "chunks": clean_chunks,
    "tables": tables,
    "findings": []
})