You are working inside my existing AI tender-analysis project.

IMPORTANT:
Before writing or changing code, inspect the existing repository and create an implementation plan. The code is located in main.py. That's where you should look.

Be sure to also follow the instructions in the AGENTS.MD. 

Break the plan into exactly 3 phases.

For each phase include:
- objective
- files to create or modify
- backend work
- frontend work
- API contracts
- testing
- completion criteria

DO NOT IMPLEMENT ANYTHING YET.

First give me the 3-phase plan and stop. Save the plan as: plan.md in this directory.

I will review the plan before asking you to implement it. Save the plan as: plan.md in this directory.


==================================================
PROJECT GOAL
==================================================

Build a full-stack web application around my existing government tender analysis agent.

The application allows a user to:

1. Upload any tender PDF.
2. Parse the PDF with Docling.
3. Extract structured text chunks and tables.
4. Run the existing LangGraph tender analysis agent.
5. Produce:
   - a structured Tender Analysis
   - a Decision Support Report
6. Display both outputs in a professional web interface.
7. Help a human make a Bid / No-Bid decision.

IMPORTANT:

The AI MUST NOT make the final Bid / No-Bid decision.

The system provides decision support only.

The human user makes the final decision.


==================================================
CURRENT PROJECT
==================================================

My existing LangGraph nodes and Pydantic schemas have been moved into:

main.py

Before making changes:

1. Inspect main.py.
2. Understand the existing graph and schemas.
3. Reuse the existing agent logic.
4. Do not unnecessarily rewrite working LangGraph nodes.
5. Refactor only where needed to expose the functionality cleanly through FastAPI.

The current conceptual LangGraph flow is:

                    Tender PDF
                         |
                         v
                       Docling
                         |
              +----------+----------+
              |                     |
              v                     v
         Text Chunks              Tables
              |                     |
              v                     v
       analyze_chunk          analyze_table
              |                     |
              +----------+----------+
                         |
                         v
                  reduce_findings
                         |
                         v
                  TenderAnalysis
                         |
                         v
                  generate_report
                         |
                         v
              DecisionSupportReport


==================================================
BACKEND
==================================================

Use FastAPI.

The frontend must upload the actual PDF to the backend.

Do NOT assume a PDF already exists on disk with a hardcoded name such as:

tender.PDF

The user should be able to select or drag and drop a PDF from their computer.


Suggested API:

POST /api/analyze

Request:

multipart/form-data

file:
    PDF file


Backend flow:

PDF upload
    |
    v
Validate PDF
    |
    v
Temporarily store or process uploaded file
    |
    v
Docling parsing
    |
    +--------------------+
    |                    |
    v                    v
Text extraction       Table extraction
    |                    |
    v                    v
Chunk processing      DataFrames
    |                    |
    v                    v
analyze_chunk         analyze_table
    |                    |
    +---------+----------+
              |
              v
       reduce_findings
              |
              v
       final_analysis
              |
              v
       generate_report
              |
              v
       decision_report
              |
              v
         JSON Response


==================================================
IMPORTANT TABLE HANDLING REQUIREMENT
==================================================

The current prototype contains logic similar to:

if chunk.metadata.get("section") == "UNIT PRICE TABLE":
    continue

DO NOT use this in the production implementation.

This was specific to the test tender.

The application must work with ANY tender PDF.

There may be:

- unit price tables
- pricing schedules
- equipment schedules
- compliance matrices
- technical tables
- quantities
- deliverable schedules
- forms
- small metadata tables
- layout tables
- irrelevant tables

The system must NOT hardcode table names.


==================================================
GENERIC LARGE TABLE HANDLING
==================================================

Docling may represent the same table in two places:

1. Inside exported Markdown/text.
2. As a structured Docling table that can be converted into a DataFrame.

Large tables should preferably be processed through the structured table pipeline rather than duplicated inside the text pipeline.

Design this generically.


Desired concept:

                     Docling Document
                           |
                +----------+----------+
                |                     |
                v                     v
            Text Content          Tables
                |                     |
                |                     v
                |                 DataFrames
                |                     |
                v                     v
        Structure-aware         analyze_table
        text chunking
                |
                v
        Detect table-heavy
        / duplicated content
                |
           +----+----+
           |         |
         normal     large table
          text       representation
           |         |
           v         v
     analyze_chunk   Skip from
                     TEXT path only
                         |
                         |
                    still processed
                         |
                         v
                    analyze_table


IMPORTANT:

A table being removed from the text path MUST NOT mean the table is ignored.

It should still go through:

Docling Table
    ->
DataFrame
    ->
analyze_table


==================================================
TABLE FILTERING LOGIC
==================================================

Do not detect large tables only by character length.

Use structure-aware logic.

Consider signals such as:

- table row count
- column count
- estimated cell count
- serialized table size
- percentage of a chunk that appears to be tabular
- Markdown table syntax
- Docling table metadata where available

Use configurable thresholds rather than hardcoded tender-specific names.

For example, the implementation may define configuration such as:

LARGE_TABLE_ROW_THRESHOLD
LARGE_TABLE_CELL_THRESHOLD
LARGE_TABLE_CHARACTER_THRESHOLD

The exact values should be proposed in the plan.

Do not overengineer this.

This is an MVP.

The goal is primarily to avoid sending a very large structured table twice:

once through analyze_chunk
and again through analyze_table.


==================================================
USELESS TABLES
==================================================

Not every Docling table will contain tender requirements.

The existing analyze_table worker is allowed to return:

[]

when a table contains no relevant requirements.

Keep that behavior.

For the MVP, it is acceptable for small tables to still reach the LLM and let analyze_table determine whether they contain useful requirements.

Do not build a complicated table-classification system unless there is a clear reason.

The important optimization is avoiding duplication of very large tables.


==================================================
EXISTING MAP REDUCE DESIGN
==================================================

Preserve the existing architecture.

Text workers produce raw Requirement findings.

Table workers produce raw Requirement findings.

Both feeds are combined using the LangGraph reducer.

Conceptually:

        Chunk 1 -> analyze_chunk -> Requirement
        Chunk 2 -> analyze_chunk -> Requirement
        Chunk 3 -> analyze_chunk -> Requirement

        Table 1 -> analyze_table -> Requirement
        Table 2 -> analyze_table -> Requirement
        Table 3 -> analyze_table -> Requirement

                         |
                         v

                  combined findings

                         |
                         v

                  reduce_findings

                         |
                         v

              deduplicated analysis


The reducer performs semantic consolidation and deduplication.


==================================================
TENDER ANALYSIS OUTPUT
==================================================

The backend already produces a structured TenderAnalysis.

The structure conceptually looks like:

{
    "categories": [
        {
            "category": "submission",
            "status": "FOUND",
            "requirements": [
                {
                    "requirement": "...",
                    "status": "FOUND",
                    "requirement_type": "MANDATORY",
                    "source_sections": ["..."],
                    "evidence": ["..."]
                }
            ]
        }
    ]
}


Category statuses:

FOUND
NOT_FOUND


Individual requirement statuses:

FOUND
NOT_REQUIRED
EXTERNAL_REFERENCE


Requirement types:

MANDATORY
CONDITIONAL
INFORMATIONAL


IMPORTANT:

A category may contain requirements with different statuses.

Do not flatten this model.


==================================================
DECISION SUPPORT REPORT
==================================================

After TenderAnalysis, the existing generate_report node creates a:

DecisionSupportReport


It contains fields such as:

executive_summary

reasons_to_consider_bidding

concerns_and_risks

missing_information

mandatory_requirements

conditional_requirements

external_references_to_review

questions_for_bid_team


This report helps the HUMAN determine whether to bid.

It must never output a final:

BID

or

NO BID


Architecture:

TenderAnalysis
      |
      v
generate_report
      |
      v
DecisionSupportReport
      |
      v
Human reviews evidence
      |
      v
Human makes Bid / No-Bid decision


==================================================
API RESPONSE
==================================================

Design the endpoint to return both outputs separately.

Conceptually:

{
    "tender_analysis": {
        ...
    },

    "decision_support_report": {
        ...
    }
}


Do not combine them into one unstructured LLM response.


==================================================
FRONTEND
==================================================

Build a professional frontend for proposal teams reviewing tenders.

Use:

Next.js
React
TypeScript
Tailwind CSS

Keep the design professional, clean and enterprise-oriented.

This should look like a real proposal-management / procurement application, not an AI chatbot.


==================================================
UPLOAD SCREEN
==================================================

The first screen should allow the user to upload a tender PDF.

Include:

- drag and drop area
- Select PDF button
- file name
- file size
- remove / replace file
- Analyze Tender button

Example:

+-------------------------------------------------------+
|                                                       |
|                Tender Analysis                        |
|                                                       |
|        Upload a government tender PDF                 |
|                                                       |
|        +-----------------------------------+          |
|        |                                   |          |
|        |      Drag PDF here                |          |
|        |                                   |          |
|        |      or                           |          |
|        |                                   |          |
|        |      [ Select PDF ]               |          |
|        |                                   |          |
|        +-----------------------------------+          |
|                                                       |
|              [ Analyze Tender ]                       |
|                                                       |
+-------------------------------------------------------+


Only PDF files should be accepted.


==================================================
ANALYSIS LOADING STATE
==================================================

Tender analysis may take time.

Create a proper analysis/progress screen.

Do NOT leave the user looking at a frozen button.

Example:

Analyzing Tender

[✓] PDF uploaded
[✓] Document parsed
[ ] Extracting requirements
[ ] Analyzing tables
[ ] Consolidating findings
[ ] Generating decision report


If exact backend stage streaming is not implemented in the MVP,
use an honest loading state rather than fake exact progress percentages.


==================================================
RESULTS PAGE
==================================================

The results page should have two main views:

[ Decision Support ]   [ Tender Analysis ]


Default to:

Decision Support


==================================================
DECISION SUPPORT VIEW
==================================================

The main decision-support screen should contain:

Tender Decision Support

Executive Summary

Reasons to Consider Bidding

Concerns & Risks

Missing Information

Mandatory Requirements

Conditional Requirements

External References to Review

Questions for Bid Team


Example:

+-------------------------------------------------------+
| Tender Decision Support                               |
+-------------------------------------------------------+

|  Mandatory  | Conditional | External References |
|      18      |      6      |         7           |

---------------------------------------------------------

Executive Summary

This tender involves...


---------------------------------------------------------

Reasons to Consider Bidding

✓ Clearly defined scope
✓ Defined construction timeline
✓ Detailed pricing schedule


---------------------------------------------------------

Concerns & Risks

! Seven-week delivery period
! Bid security required
! $5M insurance requirement


---------------------------------------------------------

Missing Information

? Exact bid security requirements contained in GI09
? Company resource availability unknown


---------------------------------------------------------

Questions for Bid Team

□ Can we complete the project in seven weeks?

□ Can we obtain the required bid security?

□ Does our insurance satisfy the requirements?

□ Have all drawings and specifications been reviewed?


==================================================
TENDER ANALYSIS VIEW
==================================================

This is the detailed structured extraction.

Add category navigation such as:

Submission
Required Documents
Certifications
Insurance
Bonding Security
Experience
Personnel
Technical
Financial
Formatting
Legal / Regulatory
Language
Security
Site Meeting
Signatures


Requirements should be displayed as cards or rows.

Example:

Submission

---------------------------------------------------------

MANDATORY

Submit bid no later than June 19 at 2:00 PM

Status:
FOUND

Source:
Issuing Office

[ View Evidence ]

---------------------------------------------------------

CONDITIONAL

Bid revisions may be submitted by fax

Status:
EXTERNAL_REFERENCE

Source:
SI04 / GI11

[ View Evidence ]


==================================================
VISUAL TYPE BADGES
==================================================

Clearly distinguish:

MANDATORY
CONDITIONAL
INFORMATIONAL


Also display:

FOUND
NOT_REQUIRED
EXTERNAL_REFERENCE


Do not rely only on color.

Always show the text label.


==================================================
FILTERING
==================================================

Allow users to filter requirements by:

All

Mandatory

Conditional

Informational

External References


Potential controls:

[ All ] [ Mandatory ] [ Conditional ] [ Informational ]

Search requirements: [________________]


==================================================
COMPLIANCE MATRIX
==================================================

Include a useful Compliance Matrix view or section.

Example:

Requirement                  Type          Status
-----------------------------------------------------------
Submit before closing        Mandatory     Found
Provide bid security         Mandatory     External Reference
Insurance certificate        Mandatory     Found
Alternative material approval Conditional  External Reference
Site visit                   Informational Not Required


The matrix should be generated from TenderAnalysis.

Do NOT have another LLM generate it.


==================================================
RAW JSON
==================================================

The normal user should NOT need to look at JSON.

The UI should render the structured response as components.

However, for development/debugging, provide an optional collapsed:

View Raw JSON

section.

It should not be the primary interface.


==================================================
ERROR HANDLING
==================================================

Handle cases such as:

- non-PDF file
- empty file
- corrupted PDF
- Docling parsing failure
- no text extracted
- no tables extracted
- LLM failure
- graph execution failure
- malformed response
- backend unavailable

Show understandable error messages to the user.

Do not expose stack traces in the frontend.


==================================================
BACKEND ORGANIZATION
==================================================

The current AI logic exists in main.py.

Inspect it before deciding how to organize the FastAPI application.

Avoid unnecessary refactoring.

However, the architecture should keep concerns reasonably separated.

For example, the final implementation may evolve toward something like:

project/
|
|-- main.py
|
|-- api/
|    |-- routes.py
|
|-- services/
|    |-- tender_service.py
|    |-- document_service.py
|
|-- frontend/
     |-- ...


But DO NOT blindly create this structure.

Inspect the current repository first and propose the smallest clean architecture in the plan.


==================================================
IMPORTANT ENGINEERING REQUIREMENTS
==================================================

1. Reuse existing Pydantic schemas where possible.

2. Reuse the existing LangGraph graph.

3. Do not duplicate agent logic inside FastAPI routes.

4. Do not hardcode anything specific to the current test tender.

5. Do not hardcode:
   "UNIT PRICE TABLE"

6. The system must accept arbitrary tender PDFs.

7. Keep structured tables available to analyze_table.

8. Avoid sending large structured tables through both the
   chunk worker and table worker unnecessarily.

9. Do not remove small tables simply because they appear unimportant.

10. Preserve source sections and evidence.

11. Preserve the separation between:
    raw Requirement findings
    TenderAnalysis
    DecisionSupportReport

12. The human makes the final Bid / No-Bid decision.


==================================================
SECURITY / FILE HANDLING
==================================================

For uploaded PDFs:

- validate MIME type / extension appropriately
- establish a reasonable configurable upload-size limit
- generate safe temporary filenames
- do not trust the user's original filename as a filesystem path
- clean up temporary files after processing when possible
- do not allow arbitrary path access


==================================================
MVP SCOPE
==================================================

Do NOT add:

- authentication
- database persistence
- multi-user accounts
- payments
- tender history
- team collaboration
- cloud storage
- background job infrastructure
- complicated queues
- premature microservices

unless the existing repository already requires them.

This version is an MVP proving:

PDF Upload
    ->
AI Tender Analysis
    ->
Decision Support Report
    ->
Professional Human Review UI


==================================================
THREE PHASE REQUIREMENT
==================================================

Your implementation plan MUST be divided into exactly three phases.


PHASE 1

Backend Integration + PDF Upload Pipeline

Likely goals:

- inspect existing main.py
- expose FastAPI
- PDF upload
- Docling parsing
- generic text/table separation
- generic large-table handling
- execute existing graph
- return structured JSON
- backend tests


PHASE 2

Core Frontend + Tender Analysis UI

Likely goals:

- upload interface
- backend integration
- loading/error states
- Tender Analysis page
- categories
- requirement cards
- filters
- compliance matrix
- raw JSON developer view


PHASE 3

Decision Support UX + Polish

Likely goals:

- Decision Support Report UI
- summary metrics
- risks
- missing information
- questions for bid team
- external-reference review
- responsive layout
- final integration testing
- cleanup


You may adjust what belongs in each phase after inspecting the repository,
but there MUST be exactly three phases.


==================================================
FIRST TASK
==================================================

DO NOT IMPLEMENT YET.

Your first task is:

1. Inspect the repository.
2. Inspect main.py carefully.
3. Identify what already works.
4. Identify what must change.
5. Identify any risks or architectural issues.
6. Produce a detailed implementation plan.
7. Break that implementation plan into exactly 3 phases.
8. List the exact files you expect to create or modify in each phase.
9. Describe the API contract.
10. Explain your proposed generic large-table handling logic.
11. Explain how you will avoid duplicating large table content between
    analyze_chunk and analyze_table.
12. Explain how the frontend will consume TenderAnalysis and
    DecisionSupportReport.
13. Include testing criteria for each phase.

Then STOP.

Do not modify files.

Do not implement the plan.

Wait for my approval.