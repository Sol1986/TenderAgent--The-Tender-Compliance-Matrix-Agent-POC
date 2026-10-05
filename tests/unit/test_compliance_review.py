"""Report projection, filtering, and escaping checks without model calls."""

from copy import deepcopy
from typing import Any

from backend.compliance_review import (
    build_review_data,
    filter_rows,
    render_matrix,
    render_overview,
    render_references,
)


def sample_report() -> dict[str, Any]:
    """Provide multiple rows and reference states to exercise report boundaries."""
    row = {
        "item_id": "REQ-0001",
        "requirement": {
            "text": "Provide insurance for Montréal <script>alert(1)</script>",
            "category": "insurance",
            "required_at": "BID_SUBMISSION",
            "requirement_type": "MANDATORY",
            "compliance_severity": "DISQUALIFYING",
            "parameters": {"limit": "$5,000,000"},
            "consequence": "May reject",
        },
        "analysis": {
            "is_active": True,
            "requires_human_review": True,
            "review_reason": "Confirm timing",
        },
        "sources": {
            "evidence": [
                {
                    "document_name": "a.pdf",
                    "page": 3,
                    "section": "2",
                    "text": "Evidence <img src=x>",
                }
            ],
            "external_references": [
                {
                    "reference_name": "Policy",
                    "reference_section": "1",
                    "retrieved": False,
                },
                {
                    "reference_name": "Policy",
                    "reference_section": "1",
                    "retrieved": False,
                },
                {
                    "reference_name": "Provided annex",
                    "reference_section": None,
                    "retrieved": True,
                },
            ],
        },
    }
    second = deepcopy(row)
    second["item_id"] = "REQ-0002"
    second["requirement"].update(
        text="Complete the work", required_at=None, compliance_severity="UNKNOWN"
    )
    second["analysis"]["requires_human_review"] = False
    second["sources"]["external_references"].append(
        {"reference_name": "Policy", "reference_section": "2", "retrieved": False}
    )
    inactive = deepcopy(row)
    inactive["item_id"] = "REQ-0003"
    inactive["analysis"]["is_active"] = False
    return {
        "requirements": [row, second, inactive],
        "documents_analyzed": [
            {"filename": "a.pdf", "processing_status": "COMPLETE"},
            {
                "filename": "b.pdf",
                "processing_status": "FAILED",
                "processing_error": "Unreadable",
            },
        ],
        "unresolved_issues": [],
    }


def test_counts_reference_deduplication_and_active_rows() -> None:
    """Reference sections stay distinct and superseded rows cannot inflate counts."""
    d = build_review_data(sample_report())
    assert d["counts"]["total"] == 2
    assert d["counts"]["disqualifying"] == d["counts"]["review"] == 1
    assert d["counts"]["references"] == 2
    assert d["references"][0]["ids"] == ["REQ-0001", "REQ-0002"]
    assert d["counts"]["failed"] == 1
    assert "Incomplete package" in render_overview(d)


def test_filters_and_untrusted_text() -> None:
    """Search intersects the structured filters and input markup stays inert."""
    d = build_review_data(sample_report())
    assert (
        len(
            filter_rows(
                d,
                "policy",
                "BID_SUBMISSION",
                "insurance",
                "MANDATORY",
                "DISQUALIFYING",
                True,
            )
        )
        == 1
    )
    assert not filter_rows(d, stage="UNCLEAR", review_only=True)
    html = render_matrix(d) + render_overview(d) + render_references(d)
    assert "<script>" not in html and "<img src=x>" not in html
    assert "&lt;script&gt;" in html and "&lt;img src=x&gt;" in html
    assert "REQ-0003" not in html
    assert "Showing 0 of 2" in render_matrix(d, search="no matching phrase")
