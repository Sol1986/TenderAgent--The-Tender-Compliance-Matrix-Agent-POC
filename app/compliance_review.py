"""Deterministic browser views of an already validated ComplianceReport."""

from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any

STAGES = {
    "BID_SUBMISSION": "Bid submission",
    "BID_CLOSING": "Closing",
    "CONTRACT_AWARD": "Contract award",
    "BEFORE_WORK_BEGINS": "Before work begins",
    "DURING_CONTRACT": "During contract",
    "CONDITIONAL": "Depends on conditions",
    "UNCLEAR": "Unclear or not stated",
}

REVIEW_CSS = """
.review {color:#e9eef8; font-family:Arial,sans-serif; line-height:1.65; padding:20px 4px; overflow-wrap:anywhere}
.review h2 {font-size:30px!important; line-height:1.25; color:#f2f5ff!important; margin:12px 0 20px!important}
.review h3 {font-size:22px!important; color:#f2f5ff!important; margin:28px 0 14px!important}
.review p {margin:10px 0}.review .muted {color:#a8b4c9; font-size:13px}
.review .metrics {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:28px 0}
.review .metric {padding:18px;background:#111521;border:1px solid #293245;border-radius:8px}
.review .metric strong {display:block;font-size:34px;color:#79B2FF}
.review .callout {padding:20px;background:#111521;border-left:3px solid #79B2FF;border-radius:6px}
.review .risk {border-left:3px solid #ed9696;padding:16px 20px;background:#111521;margin:12px 0;border-radius:6px}
.review .badge {display:inline-block;background:#202a40;color:#c6dcff;padding:3px 9px;border-radius:5px;font-size:12px;margin:2px 5px 2px 0}
.review details {border:1px solid #293245;border-radius:6px;padding:14px;margin:9px 0;background:#111521}
.review summary {cursor:pointer}.review summary strong {color:#79B2FF}
.review .detail {padding:8px 4px}.review blockquote {border-left:2px solid #53617a;padding-left:14px;color:#c0cadb}
.review .stages {display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}
.review .stages span {padding:8px 12px;border:1px solid #293245;border-radius:6px;background:#111521}
.review table {width:100%;border-collapse:collapse;color:inherit}.review th,.review td {text-align:left;padding:10px;border-bottom:1px solid #293245;vertical-align:top}
@media(max-width:700px){.review .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.review h2{font-size:24px!important}}
"""


def label(value: str | None) -> str:
    """Turn stored enums into readable labels without changing their meaning."""
    if value == "UNKNOWN":
        return "Not yet rated"
    return (value or "Unclear or not stated").replace("_", " ").title()


def reference_group(name: str) -> str:
    """Group reference names for navigation only, without inferring retrieval."""
    name = name.casefold()
    if name.startswith("specification"):
        return "Technical specifications"
    if name.startswith("gi") or "general instructions" in name:
        return "General instructions"
    if name.startswith(("si", "sc", "ba")) or "bid and acceptance" in name:
        return "Tender clauses and forms"
    if name.startswith("gc") or "general conditions" in name:
        return "General conditions"
    if name.startswith("it") or "insurance" in name:
        return "Insurance terms"
    return "Other references"


def build_review_data(report: dict[str, Any]) -> dict[str, Any]:
    """Project final active rows and compute counts using the same row population."""
    rows = [r for r in report["requirements"] if r["analysis"]["is_active"]]
    refs: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        for ref in row["sources"]["external_references"]:
            if ref["retrieved"]:
                continue
            name, section = ref["reference_name"], ref.get("reference_section") or ""
            key = (
                " ".join(name.casefold().split()),
                " ".join(section.casefold().split()),
            )
            entry = refs.setdefault(
                key,
                {
                    "name": name,
                    "section": section,
                    "ids": [],
                    "group": reference_group(name),
                },
            )
            if row["item_id"] not in entry["ids"]:
                entry["ids"].append(row["item_id"])
    documents = report["documents_analyzed"]
    counts = {
        "total": len(rows),
        "mandatory": sum(
            r["requirement"]["requirement_type"] == "MANDATORY" for r in rows
        ),
        "disqualifying": sum(
            r["requirement"]["compliance_severity"] == "DISQUALIFYING" for r in rows
        ),
        "review": sum(r["analysis"]["requires_human_review"] for r in rows),
        "unknown": sum(
            r["requirement"]["compliance_severity"] == "UNKNOWN" for r in rows
        ),
        "unclear": sum(
            r["requirement"]["required_at"] in (None, "UNCLEAR") for r in rows
        ),
        "dependent": sum(
            any(not ref["retrieved"] for ref in r["sources"]["external_references"])
            for r in rows
        ),
        "references": len(refs),
        "failed": sum(d["processing_status"] == "FAILED" for d in documents),
    }
    return {
        "title": report.get("solicitation_title")
        or ", ".join(d["filename"] for d in documents)
        or "Solicitation package",
        "number": report.get("solicitation_number"),
        "rows": rows,
        "counts": counts,
        "stages": dict(
            Counter(r["requirement"]["required_at"] or "UNCLEAR" for r in rows)
        ),
        "references": sorted(
            refs.values(),
            key=lambda r: (r["group"], r["name"].casefold(), r["section"]),
        ),
        "documents": documents,
        "issues": report["unresolved_issues"],
    }


def review_guidance(data: dict[str, Any]) -> list[str]:
    """Describe observed gaps and next actions without inventing causal claims."""
    c = data["counts"]
    messages = [
        (
            f"{c['mandatory']} requirements are marked mandatory. {c['review']} are flagged for human review. "
            f"{c['unknown']} have no confirmed severity and {c['unclear']} have unclear or unstated timing. "
            "An unknown rating does not mean low risk."
        ),
    ]
    if c["references"]:
        messages.append(
            f"{c['dependent']} requirements have at least one unresolved reference. "
            f"The list contains {c['references']} distinct name-and-section entries, not necessarily that many missing PDFs. "
            "Some may be internal clauses or alternate names for the same document. "
            "Confirm them against the uploaded package, obtain any genuinely missing documents, and rerun the analysis."
        )
    messages.append(
        "Assign owners to the priority items and review their timing, conditions, and evidence before submission. The coordinator makes the final decision."
    )
    if c["failed"]:
        messages.insert(
            0,
            f"Incomplete package: {c['failed']} document(s) failed processing. Review the document register and rerun those files before relying on coverage.",
        )
    if not c["total"]:
        messages.insert(
            0,
            "No active requirements were produced. This does not establish that the solicitation has no obligations.",
        )
    return messages


def source_location(row: dict[str, Any]) -> str:
    """Keep all known source locations and explicitly mark absent page metadata."""
    locations = []
    for e in row["sources"]["evidence"]:
        parts = [
            e["document_name"],
            e.get("section"),
            f"PDF page {e['page']}" if e.get("page") else "Page not recorded",
        ]
        location = " | ".join(str(p) for p in parts if p)
        if location not in locations:
            locations.append(location)
    return "; ".join(locations) or "Source location not recorded"


def review_notes(row: dict[str, Any]) -> list[str]:
    """Retain review, contradiction, ambiguity, amendment and consequence notes."""
    a, r = row["analysis"], row["requirement"]
    pairs = [
        ("Review", a.get("review_reason")),
        ("Ambiguity", a.get("ambiguity_reason")),
        ("Contradiction", a.get("contradiction_reason")),
        ("Amendment", a.get("amendment_details")),
        ("Consequence", r.get("consequence")),
    ]
    return [f"{name}: {text}" for name, text in pairs if text]


def metadata(row: dict[str, Any]) -> str:
    """Provide identical requirement labels in the HTML and PDF views."""
    r = row["requirement"]
    return " | ".join(
        [
            row["item_id"],
            label(r["requirement_type"]),
            STAGES.get(r["required_at"] or "UNCLEAR", label(r["required_at"])),
            label(r["category"]),
            label(r["compliance_severity"]),
            "Needs review"
            if row["analysis"]["requires_human_review"]
            else "No review flag",
        ]
    )


def render_overview(data: dict[str, Any] | None) -> str:
    """Render metrics and priority cards using escaped report text."""
    if not data:
        return ""
    c = data["counts"]
    cards = "".join(
        f'<div class="metric"><strong>{c[key]}</strong>{caption}</div>'
        for key, caption in [
            ("total", "active requirements"),
            ("disqualifying", "flagged disqualifying"),
            ("review", "need human review"),
            ("references", "unresolved reference entries"),
        ]
    )
    paragraphs = "".join(f"<p>{escape(p)}</p>" for p in review_guidance(data))
    risk = "".join(
        f'<article class="risk"><div class="muted">{escape(metadata(row))}</div>'
        f'<p>{escape(row["requirement"]["text"])}</p><div class="muted">{escape(source_location(row))}</div></article>'
        for row in data["rows"]
        if row["requirement"]["compliance_severity"] == "DISQUALIFYING"
    )
    stages = "".join(
        f"<span><b>{data['stages'].get(key, 0)}</b> {caption}</span>"
        for key, caption in STAGES.items()
    )
    return (
        f'<section class="review"><p class="muted">Compliance review of {escape(data["title"])}</p>'
        f"<h2>{c['total']} requirements found.<br>{c['disqualifying']} flagged for disqualification risk.</h2>"
        f"<p>Reconciled requirements organized by timing and risk, with evidence and review notes.</p>"
        f'<div class="metrics">{cards}</div><h3>What this means for the bid</h3>'
        f'<div class="callout">{paragraphs}</div><h3>Priority items</h3>'
        '<p class="muted">These retain the report’s disqualifying classification. Consequences may apply at submission or during the contract.</p>'
        f"{risk or '<p>No items are classified as disqualifying; review unknown ratings before relying on that result.</p>'}"
        f"<h3>Full compliance matrix</h3><p>Filter the list, then expand a requirement to review its evidence and dependencies.</p>"
        f'<div class="stages">{stages}</div></section>'
    )


def filter_rows(
    data: dict[str, Any],
    search: str = "",
    stage: str = "All",
    category: str = "All",
    requirement_type: str = "All",
    severity: str = "All",
    review_only: bool = False,
) -> list[dict[str, Any]]:
    """Combine filters without changing the full-report download population."""
    rows = []
    for row in data["rows"]:
        r = row["requirement"]
        if any(
            selected != "All" and selected != actual
            for selected, actual in [
                (stage, r["required_at"] or "UNCLEAR"),
                (category, r["category"]),
                (requirement_type, r["requirement_type"]),
                (severity, r["compliance_severity"]),
            ]
        ):
            continue
        if review_only and not row["analysis"]["requires_human_review"]:
            continue
        haystack = " ".join(
            [
                row["item_id"],
                r["text"],
                source_location(row),
                *review_notes(row),
                *(
                    ref["reference_name"]
                    for ref in row["sources"]["external_references"]
                ),
            ]
        )
        if search.strip().casefold() not in haystack.casefold():
            continue
        rows.append(row)
    return rows


def render_matrix(
    data: dict[str, Any] | None,
    search: str = "",
    stage: str = "All",
    category: str = "All",
    requirement_type: str = "All",
    severity: str = "All",
    review_only: bool = False,
) -> str:
    """Produce accessible expandable rows; source strings never become markup."""
    if not data:
        return ""
    rows = filter_rows(
        data, search, stage, category, requirement_type, severity, review_only
    )
    output = [
        f'<section class="review"><p class="muted">Showing {len(rows)} of {len(data["rows"])} requirements. PDF includes the complete report.</p>'
    ]
    for row in rows:
        r = row["requirement"]
        output.append(
            f"<details><summary><strong>{escape(row['item_id'])}</strong> "
            f'{escape(r["text"])}<br><span class="muted">{escape(metadata(row))}</span></summary><div class="detail">'
        )
        output.append(f'<p class="muted">Source: {escape(source_location(row))}</p>')
        output.extend(f"<p>{escape(note)}</p>" for note in review_notes(row))
        output.extend(
            f"<p><b>{escape(str(k))}:</b> {escape(str(v))}</p>"
            for k, v in r["parameters"].items()
        )
        for ref in row["sources"]["external_references"]:
            status = "Retrieved" if ref["retrieved"] else "Unresolved"
            output.append(
                f"<p><b>{status} reference:</b> {escape(ref['reference_name'])} {escape(ref.get('reference_section') or '')}</p>"
            )
        for e in row["sources"]["evidence"]:
            output.append(f"<blockquote>{escape(e['text'])}</blockquote>")
        output.append("</div></details>")
    return "".join(output) + "</section>"


def render_references(data: dict[str, Any] | None) -> str:
    """List unresolved references, processing status and package-level issues."""
    if not data:
        return ""
    output = [
        '<section class="review"><h3>References to verify</h3><p>Distinct unresolved names and sections reported by the agent. Check internal clauses before requesting more PDFs.</p>'
    ]
    group = None
    for ref in data["references"]:
        if group != ref["group"]:
            if group:
                output.append("</ul>")
            group = ref["group"]
            output.append(f"<h4>{escape(group)}</h4><ul>")
        output.append(
            f'<li>{escape(ref["name"])} {escape(ref["section"])} <span class="muted">({escape(", ".join(ref["ids"]))})</span></li>'
        )
    if group:
        output.append("</ul>")
    else:
        output.append("<p>No unresolved references recorded.</p>")
    output.append("<h3>Document register</h3><ul>")
    for d in data["documents"]:
        output.append(
            f"<li>{escape(d['filename'])} - {escape(label(d['processing_status']))} {escape(d.get('processing_error') or '')}</li>"
        )
    output.append("</ul><h3>Package issues</h3>")
    for issue in data["issues"]:
        output.append(
            f"<details><summary>{escape(issue['title'])}</summary><p>{escape(issue['description'])}</p>"
            f'<p class="muted">{escape(", ".join(issue["affected_requirement_ids"]))}</p></details>'
        )
    if not data["issues"]:
        output.append("<p>No unresolved package issues recorded.</p>")
    return "".join(output) + "</section>"
