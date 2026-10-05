"""Deterministic coverage for Phase C package-level reconciliation."""

from typing import Any

import pytest

from backend.main import (
    DocumentExtractionResult,
    FindingRelationshipDecision,
    GroundedCandidate,
    PackageExtractionResult,
    ReconciliationDraft,
    ReconciliationGroupDraft,
    Requirement,
    reconcile_package,
)
from backend.solicitation_package import SolicitationDocument


class ReconciliationModel:
    """Return a supplied reconciliation draft without external model calls."""

    def __init__(
        self,
        draft: ReconciliationDraft | list[ReconciliationDraft],
    ) -> None:
        self.drafts = draft if isinstance(draft, list) else [draft]
        self.prompt = ""
        self.prompts: list[str] = []

    def with_structured_output(self, schema: type) -> Any:
        model = self

        class Runnable:
            def invoke(self, prompt: str) -> ReconciliationDraft:
                if schema is not ReconciliationDraft:
                    raise AssertionError(f"Unexpected schema invocation: {schema}")
                model.prompt = prompt
                model.prompts.append(prompt)
                index = min(len(model.prompts) - 1, len(model.drafts) - 1)
                return model.drafts[index]

        return Runnable()


def make_candidate(
    number: int,
    document_number: int,
    requirement: str,
    evidence: str,
    *,
    category: str = "bonding_security",
    status: str = "FOUND",
) -> GroundedCandidate:
    """Create one valid grounded candidate with predictable identity."""
    return GroundedCandidate(
        candidate_id=f"CAND-{number:04d}",
        document_id=f"DOC-{document_number:012X}",
        document_name=f"document_{document_number}.pdf",
        finding=Requirement(
            category=category,
            requirement=requirement,
            status=status,
            source_section=f"Section {number}",
            evidence=evidence,
        ),
    )


def make_extraction(candidates: list[GroundedCandidate]) -> PackageExtractionResult:
    """Wrap candidates in the Phase B package contract."""
    documents: list[SolicitationDocument] = []
    results: list[DocumentExtractionResult] = []
    for document_id in dict.fromkeys(candidate.document_id for candidate in candidates):
        document_candidates = [
            candidate
            for candidate in candidates
            if candidate.document_id == document_id
        ]
        document = SolicitationDocument(
            document_id=document_id,
            filename=document_candidates[0].document_name,
            processing_status="COMPLETE",
        )
        documents.append(document)
        results.append(
            DocumentExtractionResult(
                document=document,
                findings=[candidate.finding for candidate in document_candidates],
                text_chunks=1,
            )
        )
    return PackageExtractionResult(
        documents=documents,
        document_results=results,
        candidate_requirements=candidates,
    )


def relationship(
    left: str,
    right: str,
    kind: str,
    reason: str,
) -> FindingRelationshipDecision:
    """Build a relationship decision for concise fixtures."""
    return FindingRelationshipDecision(
        left_candidate_id=left,
        right_candidate_id=right,
        relationship=kind,
        reason=reason,
    )


def test_exact_duplicates_merge_and_aggregate_trusted_evidence() -> None:
    """One obligation keeps evidence from both source documents."""
    candidates = [
        make_candidate(1, 1, "Bid security is required.", "Bid security required."),
        make_candidate(2, 2, "Bid security is required.", "Provide bid security."),
    ]
    draft = ReconciliationDraft(
        groups=[
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0001", "CAND-0002"],
                requirement="Provide bid security.",
                category="bonding_security",
                extraction_status="FOUND",
                relationships=[
                    relationship(
                        "CAND-0001",
                        "CAND-0002",
                        "SAME_REQUIREMENT",
                        "Both clauses impose the same bid-security duty.",
                    )
                ],
            )
        ]
    )

    model = ReconciliationModel(draft)
    result = reconcile_package(make_extraction(candidates), model)

    assert len(result.reconciled_requirements) == 1
    assert "CLIENT COMPLIANCE MATRIX SCOPE" in model.prompt
    assert "one group for each distinct client-scope check" in model.prompt
    assert "A citation or detail of one check is not a new duty" in model.prompt
    requirement = result.reconciled_requirements[0]
    assert requirement.requirement_id == "REQ-0001"
    assert requirement.candidate_ids == ["CAND-0001", "CAND-0002"]
    assert [item.document_name for item in requirement.evidence] == [
        "document_1.pdf",
        "document_2.pdf",
    ]
    assert requirement.evidence[0].page is None


def test_supplements_merge_while_separate_duty_stays_independent() -> None:
    """Complementary details combine without absorbing an unrelated obligation."""
    candidates = [
        make_candidate(1, 1, "Bid security is required.", "Bid security required."),
        make_candidate(
            2,
            2,
            "Acceptable security is a bid bond or letter of credit.",
            "Bid bond or irrevocable standby letter of credit.",
        ),
        make_candidate(
            3,
            1,
            "Submit a signed offer.",
            "The offer must be signed.",
            category="signatures",
        ),
    ]
    draft = ReconciliationDraft(
        groups=[
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0001", "CAND-0002"],
                requirement=(
                    "Provide bid security as a bid bond or irrevocable standby "
                    "letter of credit."
                ),
                category="bonding_security",
                extraction_status="FOUND",
                relationships=[
                    relationship(
                        "CAND-0001",
                        "CAND-0002",
                        "SUPPLEMENTS",
                        "The second clause supplies acceptable forms.",
                    )
                ],
            ),
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0003"],
                requirement="Submit a signed offer.",
                category="signatures",
                extraction_status="FOUND",
            ),
        ]
    )

    result = reconcile_package(make_extraction(candidates), ReconciliationModel(draft))

    assert len(result.reconciled_requirements) == 2
    assert result.reconciled_requirements[0].relationships[0].relationship == (
        "SUPPLEMENTS"
    )
    assert result.reconciled_requirements[1].candidate_ids == ["CAND-0003"]


def test_contradiction_is_preserved_for_human_review() -> None:
    """Conflicting timing remains unresolved instead of selecting one clause."""
    candidates = [
        make_candidate(
            1,
            1,
            "Security clearance is required before award.",
            "Clearance required before award.",
            category="security",
        ),
        make_candidate(
            2,
            2,
            "Security clearance is required at bid submission.",
            "Personnel must hold clearance at bid submission.",
            category="security",
        ),
    ]
    draft = ReconciliationDraft(
        groups=[
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0001", "CAND-0002"],
                requirement="Security clearance timing is unresolved.",
                category="security",
                extraction_status="FOUND",
                relationships=[
                    relationship(
                        "CAND-0001",
                        "CAND-0002",
                        "CONTRADICTS",
                        "The clauses specify different compliance stages.",
                    )
                ],
                ambiguity_detected=True,
                ambiguity_reason="The required compliance stage is unclear.",
                contradiction_detected=True,
                contradiction_reason="Before award conflicts with bid submission.",
                requires_human_review=True,
                review_reason="Confirm the controlling clearance deadline.",
            )
        ]
    )

    result = reconcile_package(make_extraction(candidates), ReconciliationModel(draft))

    requirement = result.reconciled_requirements[0]
    assert requirement.contradiction_detected is True
    assert requirement.requires_human_review is True
    assert len(requirement.evidence) == 2


@pytest.mark.parametrize("mode", ["missing", "split_duplicate"])
def test_repeated_invalid_reconciliation_uses_recall_safe_fallback(mode: str) -> None:
    """Retain all candidates when both semantic reconciliation attempts fail."""
    candidates = [
        make_candidate(1, 1, "Bid security is required.", "First source."),
        make_candidate(2, 2, "Bid security is required.", "Second source."),
    ]
    groups = [
        ReconciliationGroupDraft(
            candidate_ids=["CAND-0001"],
            requirement="Bid security is required.",
            category="bonding_security",
            extraction_status="FOUND",
        )
    ]
    if mode == "split_duplicate":
        groups.append(
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0002"],
                requirement="Bid security is required.",
                category="bonding_security",
                extraction_status="FOUND",
            )
        )
    draft = ReconciliationDraft(groups=groups)

    model = ReconciliationModel(draft)
    result = reconcile_package(make_extraction(candidates), model)

    assert len(model.prompts) == 2
    assert "failed deterministic validation" in model.prompts[1]
    assert len(result.reconciled_requirements) == 1
    requirement = result.reconciled_requirements[0]
    assert requirement.candidate_ids == ["CAND-0001", "CAND-0002"]
    assert requirement.ambiguity_detected is True
    assert requirement.requires_human_review is True


def test_invalid_first_attempt_can_be_repaired_by_model_retry() -> None:
    """Use a corrected second response before falling back conservatively."""
    candidates = [
        make_candidate(1, 1, "Provide bid security.", "Bid security is required."),
        make_candidate(
            2,
            2,
            "Submit the signed offer.",
            "The signed offer is required.",
            category="signatures",
        ),
    ]
    invalid = ReconciliationDraft(
        groups=[
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0001", "CAND-0001"],
                requirement="Provide bid security.",
                category="bonding_security",
                extraction_status="FOUND",
            )
        ]
    )
    corrected = ReconciliationDraft(
        groups=[
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0001"],
                requirement="Provide bid security.",
                category="bonding_security",
                extraction_status="FOUND",
            ),
            ReconciliationGroupDraft(
                candidate_ids=["CAND-0002"],
                requirement="Submit the signed offer.",
                category="signatures",
                extraction_status="FOUND",
            ),
        ]
    )
    model = ReconciliationModel([invalid, corrected])

    result = reconcile_package(make_extraction(candidates), model)

    assert len(model.prompts) == 2
    assert [item.candidate_ids for item in result.reconciled_requirements] == [
        ["CAND-0001"],
        ["CAND-0002"],
    ]
    assert all(
        item.requires_human_review is False for item in result.reconciled_requirements
    )
