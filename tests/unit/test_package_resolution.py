"""Deterministic coverage for Phase D amendments and external references."""

from typing import Any

import pytest

from app.main import (
    AmendmentResolutionDraft,
    DocumentExtractionResult,
    Evidence,
    ExternalReferenceDraft,
    FindingRelationshipDecision,
    GroundedCandidate,
    PackageReconciliationResult,
    PackageResolutionDraft,
    ReconciledRequirement,
    Requirement,
    resolve_package,
)
from app.solicitation_package import SolicitationDocument


class ResolutionModel:
    """Return a supplied Phase D draft without external model calls."""

    def __init__(self, draft: PackageResolutionDraft) -> None:
        self.draft = draft
        self.prompt = ""

    def with_structured_output(self, schema: type) -> Any:
        model = self

        class Runnable:
            def invoke(self, prompt: str) -> PackageResolutionDraft:
                if schema is not PackageResolutionDraft:
                    raise AssertionError(f"Unexpected schema invocation: {schema}")
                model.prompt = prompt
                return model.draft

        return Runnable()


def document(
    number: int,
    filename: str,
    document_type: str,
    *,
    status: str = "COMPLETE",
    error: str | None = None,
) -> SolicitationDocument:
    """Create a registry document with predictable identity."""
    return SolicitationDocument(
        document_id=f"DOC-{number:012X}",
        filename=filename,
        document_type=document_type,
        processing_status=status,
        processing_error=error,
    )


def candidate(
    number: int,
    source: SolicitationDocument,
    requirement: str,
    evidence: str,
    *,
    status: str = "FOUND",
) -> GroundedCandidate:
    """Create a grounded requirement candidate from one registry document."""
    return GroundedCandidate(
        candidate_id=f"CAND-{number:04d}",
        document_id=source.document_id,
        document_name=source.filename,
        finding=Requirement(
            category="bonding_security",
            requirement=requirement,
            status=status,
            source_section=f"Section {number}",
            evidence=evidence,
        ),
    )


def reconciled_requirement(
    candidates: list[GroundedCandidate],
    requirement: str,
    *,
    extraction_status: str = "FOUND",
    relationship: str | None = None,
) -> ReconciledRequirement:
    """Create one Phase C result while preserving every source excerpt."""
    relationships = []
    if relationship is not None:
        relationships.append(
            FindingRelationshipDecision(
                left_candidate_id=candidates[0].candidate_id,
                right_candidate_id=candidates[1].candidate_id,
                relationship=relationship,
                reason="The amendment explicitly changes the original clause.",
            )
        )
    return ReconciledRequirement(
        requirement_id="REQ-0001",
        requirement=requirement,
        category="bonding_security",
        extraction_status=extraction_status,
        candidate_ids=[item.candidate_id for item in candidates],
        active_candidate_ids=[item.candidate_id for item in candidates],
        evidence=[
            Evidence(
                document_id=item.document_id,
                document_name=item.document_name,
                section=item.finding.source_section,
                text=item.finding.evidence,
            )
            for item in candidates
        ],
        relationships=relationships,
        requires_human_review=relationship == "SUPERSEDES",
        review_reason=(
            "Amendment precedence awaits Phase D."
            if relationship == "SUPERSEDES"
            else None
        ),
    )


def package(
    documents: list[SolicitationDocument],
    candidates: list[GroundedCandidate],
    requirement: ReconciledRequirement,
) -> PackageReconciliationResult:
    """Wrap a Phase C result for direct Phase D testing."""
    results = []
    for source in documents:
        findings = [
            item.finding
            for item in candidates
            if item.document_id == source.document_id
        ]
        results.append(
            DocumentExtractionResult(
                document=source,
                findings=findings,
                text_chunks=1 if source.processing_status == "COMPLETE" else 0,
            )
        )
    return PackageReconciliationResult(
        documents=documents,
        document_results=results,
        candidate_requirements=candidates,
        reconciled_requirements=[requirement],
    )


def test_amendment_replaces_original_and_preserves_traceability() -> None:
    """The current value comes from the amendment while both excerpts remain."""
    original = document(1, "main_solicitation.pdf", "MAIN_SOLICITATION")
    amendment = document(2, "amendment_002.pdf", "AMENDMENT")
    candidates = [
        candidate(1, original, "Provide bid security of 5%.", "Bid security = 5%."),
        candidate(
            2,
            amendment,
            "Provide bid security of 10%.",
            "The bid security requirement is amended from 5% to 10%.",
        ),
    ]
    requirement = reconciled_requirement(
        candidates,
        "Bid security amount is unresolved.",
        relationship="SUPERSEDES",
    )
    draft = PackageResolutionDraft(
        amendments=[
            AmendmentResolutionDraft(
                requirement_id="REQ-0001",
                action="REPLACE",
                superseding_candidate_id="CAND-0002",
                superseded_candidate_ids=["CAND-0001"],
                current_requirement="Provide bid security equal to 10% of the bid price.",
                reason="Amendment 002 explicitly replaces 5% with 10%.",
            )
        ]
    )

    result = resolve_package(
        package([original, amendment], candidates, requirement),
        ResolutionModel(draft),
    )

    current = result.reconciled_requirements[0]
    assert current.requirement == "Provide bid security equal to 10% of the bid price."
    assert current.active_candidate_ids == ["CAND-0002"]
    assert current.superseded_candidate_ids == ["CAND-0001"]
    assert current.version_status == "CURRENT"
    assert current.is_active is True
    assert current.requires_human_review is False
    assert len(current.evidence) == 2
    assert result.unresolved_issues == []


@pytest.mark.parametrize(
    ("action", "current_requirement", "expected_active", "expected_status"),
    [
        ("ADD", "Submit the new certification form.", True, "CURRENT"),
        ("DELETE", None, False, "DELETED"),
    ],
)
def test_amendment_addition_and_deletion_are_explicit(
    action: str,
    current_requirement: str | None,
    expected_active: bool,
    expected_status: str,
) -> None:
    """Added duties stay active and deleted duties remain only for traceability."""
    original = document(1, "main_solicitation.pdf", "MAIN_SOLICITATION")
    amendment = document(2, "addendum_001.pdf", "ADDENDUM")
    if action == "ADD":
        candidates = [
            candidate(
                1, amendment, current_requirement or "", "A new form is required."
            )
        ]
        requirement = reconciled_requirement(candidates, current_requirement or "")
        superseded_ids: list[str] = []
        superseding_id = "CAND-0001"
    else:
        candidates = [
            candidate(
                1, original, "Attend the site meeting.", "Attendance is mandatory."
            ),
            candidate(
                2,
                amendment,
                "The mandatory site meeting is deleted.",
                "Delete the mandatory site meeting requirement.",
            ),
        ]
        requirement = reconciled_requirement(
            candidates,
            "Attend the site meeting.",
            relationship="SUPERSEDES",
        )
        superseded_ids = ["CAND-0001"]
        superseding_id = "CAND-0002"
    draft = PackageResolutionDraft(
        amendments=[
            AmendmentResolutionDraft(
                requirement_id="REQ-0001",
                action=action,
                superseding_candidate_id=superseding_id,
                superseded_candidate_ids=superseded_ids,
                current_requirement=current_requirement,
                reason=f"The addendum explicitly performs {action}.",
            )
        ]
    )

    result = resolve_package(
        package([original, amendment], candidates, requirement),
        ResolutionModel(draft),
    )

    resolved = result.reconciled_requirements[0]
    assert resolved.is_active is expected_active
    assert resolved.version_status == expected_status


def test_uploaded_reference_is_linked_without_review_issue() -> None:
    """A unique Annex E file satisfies the package reference lookup."""
    main = document(1, "main_solicitation.pdf", "MAIN_SOLICITATION")
    annex = document(2, "Annex_E.pdf", "ANNEX")
    candidates = [
        candidate(
            1,
            main,
            "Complete the Security Requirements Checklist in Annex E.",
            "Bidders must complete Annex E, Security Requirements Checklist.",
            status="EXTERNAL_REFERENCE",
        )
    ]
    requirement = reconciled_requirement(
        candidates,
        "Complete the Security Requirements Checklist in Annex E.",
        extraction_status="EXTERNAL_REFERENCE",
    )
    draft = PackageResolutionDraft(
        external_references=[
            ExternalReferenceDraft(
                requirement_id="REQ-0001",
                reference_name="Annex E, Security Requirements Checklist",
            )
        ]
    )

    result = resolve_package(
        package([main, annex], candidates, requirement),
        ResolutionModel(draft),
    )

    reference = result.external_references[0]
    assert reference.retrieved is True
    assert reference.matched_document_id == annex.document_id
    assert result.reconciled_requirements[0].external_references == [reference]
    assert result.unresolved_issues == []


def test_missing_and_ambiguous_references_create_review_issues() -> None:
    """Reference lookup surfaces absent and non-unique documents without guessing."""
    main = document(1, "main_solicitation.pdf", "MAIN_SOLICITATION")
    annex_one = document(2, "Annex_E.pdf", "ANNEX")
    annex_two = document(3, "Annex_E_Security.pdf", "ANNEX")
    candidates = [
        candidate(
            1,
            main,
            "Follow Annex E and Standard Instructions 2003.",
            "Comply with Annex E and Standard Instructions 2003.",
            status="EXTERNAL_REFERENCE",
        )
    ]
    requirement = reconciled_requirement(
        candidates,
        "Follow Annex E and Standard Instructions 2003.",
        extraction_status="EXTERNAL_REFERENCE",
    )
    draft = PackageResolutionDraft(
        external_references=[
            ExternalReferenceDraft(
                requirement_id="REQ-0001",
                reference_name="Annex E",
            ),
            ExternalReferenceDraft(
                requirement_id="REQ-0001",
                reference_name="Standard Instructions 2003",
            ),
        ]
    )

    result = resolve_package(
        package([main, annex_one, annex_two], candidates, requirement),
        ResolutionModel(draft),
    )

    assert [item.retrieved for item in result.external_references] == [False, False]
    assert {issue.issue_type for issue in result.unresolved_issues} == {
        "MISSING_REFERENCED_DOCUMENT",
        "UNRESOLVED_CROSS_REFERENCE",
    }
    assert result.reconciled_requirements[0].requires_human_review is True


def test_unresolved_supersession_and_unidentified_reference_are_reported() -> None:
    """Omitted model resolutions become visible issues instead of silent loss."""
    original = document(1, "main_solicitation.pdf", "MAIN_SOLICITATION")
    amendment = document(2, "amendment_001.pdf", "AMENDMENT")
    candidates = [
        candidate(1, original, "Provide a five-page plan.", "Maximum five pages."),
        candidate(2, amendment, "Provide a ten-page plan.", "Maximum ten pages."),
    ]
    requirement = reconciled_requirement(
        candidates,
        "The page limit is unresolved.",
        extraction_status="EXTERNAL_REFERENCE",
        relationship="SUPERSEDES",
    )

    result = resolve_package(
        package([original, amendment], candidates, requirement),
        ResolutionModel(PackageResolutionDraft()),
    )

    resolved = result.reconciled_requirements[0]
    assert resolved.version_status == "UNRESOLVED"
    assert resolved.requires_human_review is True
    assert {issue.issue_type for issue in result.unresolved_issues} == {
        "UNRESOLVED_AMENDMENT",
        "UNRESOLVED_CROSS_REFERENCE",
    }


def test_non_amendment_cannot_become_authoritative() -> None:
    """A normal annex cannot replace a requirement even if the model proposes it."""
    original = document(1, "main_solicitation.pdf", "MAIN_SOLICITATION")
    annex = document(2, "Annex_A.pdf", "ANNEX")
    candidates = [
        candidate(1, original, "Provide 5% security.", "Security is 5%."),
        candidate(2, annex, "Provide 10% security.", "Security is 10%."),
    ]
    requirement = reconciled_requirement(
        candidates,
        "Security amount conflicts.",
        relationship="SUPERSEDES",
    )
    draft = PackageResolutionDraft(
        amendments=[
            AmendmentResolutionDraft(
                requirement_id="REQ-0001",
                action="REPLACE",
                superseding_candidate_id="CAND-0002",
                superseded_candidate_ids=["CAND-0001"],
                current_requirement="Provide 10% security.",
                reason="The annex appears newer.",
            )
        ]
    )

    with pytest.raises(ValueError, match="amendments or addenda"):
        resolve_package(
            package([original, annex], candidates, requirement),
            ResolutionModel(draft),
        )


def test_processing_failure_is_reported_when_no_requirements_exist() -> None:
    """Document failures survive even when extraction produced no candidates."""
    failed = document(
        1,
        "broken_annex.pdf",
        "ANNEX",
        status="FAILED",
        error="The PDF could not be parsed.",
    )
    reconciliation = PackageReconciliationResult(
        documents=[failed],
        document_results=[DocumentExtractionResult(document=failed)],
        candidate_requirements=[],
        reconciled_requirements=[],
    )

    result = resolve_package(reconciliation)

    assert result.reconciled_requirements == []
    assert len(result.unresolved_issues) == 1
    issue = result.unresolved_issues[0]
    assert issue.issue_type == "PROCESSING_FAILURE"
    assert issue.source_document_id == failed.document_id


def test_omitted_amendment_addition_becomes_unresolved() -> None:
    """An amendment-only obligation cannot silently pass through as unchanged."""
    amendment = document(1, "amendment_003.pdf", "AMENDMENT")
    candidates = [
        candidate(
            1,
            amendment,
            "Submit the revised pricing form.",
            "Bidders must submit the revised pricing form.",
        )
    ]
    requirement = reconciled_requirement(
        candidates,
        "Submit the revised pricing form.",
    )

    result = resolve_package(
        package([amendment], candidates, requirement),
        ResolutionModel(PackageResolutionDraft()),
    )

    resolved = result.reconciled_requirements[0]
    assert resolved.version_status == "UNRESOLVED"
    assert resolved.requires_human_review is True
    assert result.unresolved_issues[0].issue_type == "UNRESOLVED_AMENDMENT"


def test_failed_uploaded_reference_affects_requirement() -> None:
    """A matched but unreadable referenced PDF still requires human review."""
    main = document(1, "main_solicitation.pdf", "MAIN_SOLICITATION")
    failed_annex = document(
        2,
        "Annex_E.pdf",
        "ANNEX",
        status="FAILED",
        error="The annex could not be parsed.",
    )
    candidates = [
        candidate(
            1,
            main,
            "Complete Annex E.",
            "Bidders must complete Annex E.",
            status="EXTERNAL_REFERENCE",
        )
    ]
    requirement = reconciled_requirement(
        candidates,
        "Complete Annex E.",
        extraction_status="EXTERNAL_REFERENCE",
    )
    draft = PackageResolutionDraft(
        external_references=[
            ExternalReferenceDraft(
                requirement_id="REQ-0001",
                reference_name="Annex E",
            )
        ]
    )

    result = resolve_package(
        package([main, failed_annex], candidates, requirement),
        ResolutionModel(draft),
    )

    assert result.external_references[0].retrieved is True
    assert result.reconciled_requirements[0].requires_human_review is True
    issue = result.unresolved_issues[0]
    assert issue.issue_type == "PROCESSING_FAILURE"
    assert issue.affected_requirement_ids == ["REQ-0001"]
