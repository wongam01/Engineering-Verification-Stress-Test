from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


RoleGroundingStatus = Literal[
    "SUPPORTED",
    "REJECTED",
    "REVIEW_REQUIRED",
]

ProposedEngineeringRole = Literal[
    "requirement",
    "verification",
    "feasible",
]

_ALLOWED_STATUSES = {
    "SUPPORTED",
    "REJECTED",
    "REVIEW_REQUIRED",
}

_ALLOWED_ROLES = {
    "requirement",
    "verification",
    "feasible",
}


@dataclass(frozen=True)
class RoleGroundingResult:
    """
    Independent semantic-role grounding result.

    This answers a different question from adapter acceptance:

    - adapter acceptance:
      Can the extracted structure be represented by the Formal Model?

    - role grounding:
      Does the source evidence actually support the proposed
      Requirement / Verification / Feasible-Evidence role?

    Only SUPPORTED grounding may pass the grounding gate.
    """

    candidate_id: str
    proposed_role: str
    status: RoleGroundingStatus
    basis_type: str
    explanation: str
    supporting_text: str

    @property
    def supported(self) -> bool:
        return self.status == "SUPPORTED"


@dataclass(frozen=True)
class RoleGroundingGateResult:
    """
    Result of filtering Engineer-approved candidate IDs through
    the independent Role Grounding gate.
    """

    eligible_candidate_ids: tuple[str, ...]
    issues: tuple[str, ...]


def _review_required_result(
    *,
    candidate_id: str,
    proposed_role: str,
    basis_type: str,
    explanation: str,
    supporting_text: str = "",
) -> RoleGroundingResult:
    return RoleGroundingResult(
        candidate_id=candidate_id,
        proposed_role=proposed_role,
        status="REVIEW_REQUIRED",
        basis_type=basis_type,
        explanation=explanation,
        supporting_text=supporting_text,
    )


def normalize_role_grounding_payload(
    *,
    candidate_id: str,
    proposed_role: str,
    payload: Mapping[str, Any] | None,
) -> RoleGroundingResult:
    """
    Convert an external semantic-grounding result into the
    Application-layer grounding contract.

    Fail-safe rules:
    - unknown role -> REVIEW_REQUIRED
    - missing/malformed output -> REVIEW_REQUIRED
    - unknown status -> REVIEW_REQUIRED
    - SUPPORTED without explanation/source support -> REVIEW_REQUIRED

    This function does not infer engineering meaning itself.
    It validates the output of a grounding evaluator.
    """

    if proposed_role not in _ALLOWED_ROLES:
        return _review_required_result(
            candidate_id=candidate_id,
            proposed_role=proposed_role,
            basis_type="UNSUPPORTED_PROPOSED_ROLE",
            explanation=(
                "The proposed engineering role is outside the "
                "supported Requirement / Verification / "
                "Feasible-Evidence roles."
            ),
        )

    if payload is None or not isinstance(payload, Mapping):
        return _review_required_result(
            candidate_id=candidate_id,
            proposed_role=proposed_role,
            basis_type="GROUNDING_OUTPUT_MISSING",
            explanation=(
                "No valid Role Grounding result was supplied."
            ),
        )

    raw_status = str(
        payload.get("status", "")
    ).strip().upper()

    if raw_status not in _ALLOWED_STATUSES:
        return _review_required_result(
            candidate_id=candidate_id,
            proposed_role=proposed_role,
            basis_type="GROUNDING_STATUS_INVALID",
            explanation=(
                "Role Grounding returned an unsupported status."
            ),
        )

    basis_type = str(
        payload.get("basis_type", "")
    ).strip()

    explanation = str(
        payload.get("explanation", "")
    ).strip()

    supporting_text = str(
        payload.get("supporting_text", "")
    ).strip()

    if not basis_type or not explanation:
        return _review_required_result(
            candidate_id=candidate_id,
            proposed_role=proposed_role,
            basis_type="GROUNDING_EVIDENCE_INCOMPLETE",
            explanation=(
                "Role Grounding did not provide sufficient "
                "basis and explanation."
            ),
            supporting_text=supporting_text,
        )

    if (
        raw_status == "SUPPORTED"
        and not supporting_text
    ):
        return _review_required_result(
            candidate_id=candidate_id,
            proposed_role=proposed_role,
            basis_type="GROUNDING_SOURCE_SUPPORT_MISSING",
            explanation=(
                "A SUPPORTED engineering role requires "
                "source-backed supporting text."
            ),
        )

    return RoleGroundingResult(
        candidate_id=candidate_id,
        proposed_role=proposed_role,
        status=raw_status,
        basis_type=basis_type,
        explanation=explanation,
        supporting_text=supporting_text,
    )


def _normalize_grounding_source_quote(
    value: str,
) -> str:
    """
    Normalize formatting only for deterministic source-quote
    traceability.

    Whitespace is collapsed and one or more matching outer
    quotation-mark pairs may be removed.

    No fuzzy matching, paraphrase matching, or semantic
    rewriting is performed.
    """

    normalized = " ".join(
        str(value or "").split()
    )

    quote_pairs = {
        '"': '"',
        "'": "'",
        "“": "”",
        "‘": "’",
        "«": "»",
    }

    while len(normalized) >= 2:
        closing = quote_pairs.get(
            normalized[0]
        )

        if (
            closing is None
            or normalized[-1] != closing
        ):
            break

        normalized = normalized[1:-1].strip()

    return normalized


def evaluate_candidate_role_grounding(
    *,
    candidate_id: str,
    proposed_role: str,
    source_text: str,
    source_name: str = "unknown_source",
    evaluator=None,
) -> RoleGroundingResult:
    """
    Application entry point for Role Grounding.

    The semantic evaluator may be replaced in tests. Regardless of
    evaluator implementation, its result must pass through the
    deterministic normalization contract before it can be used.
    """

    if evaluator is None:
        from src.ai import (
            role_grounding_evaluator,
        )
        from src.ai.role_grounding_cache import (
            cached_role_grounding_payload,
        )

        def selected_evaluator(
            source_text_value,
            proposed_role_value,
            source_name_value,
        ):
            return cached_role_grounding_payload(
                source_text=source_text_value,
                proposed_role=proposed_role_value,
                source_name=source_name_value,
                model="gpt-5.6-terra",
                implementation_files=(
                    role_grounding_evaluator.__file__,
                ),
                compute=lambda: (
                    role_grounding_evaluator
                    .evaluate_role_grounding_from_source(
                        source_text_value,
                        proposed_role_value,
                        source_name_value,
                    )
                ),
            )
    else:
        selected_evaluator = evaluator

    try:
        payload = selected_evaluator(
            source_text,
            proposed_role,
            source_name,
        )
    except Exception:
        payload = {
            "status": "REVIEW_REQUIRED",
            "basis_type": "GROUNDING_EVALUATOR_ERROR",
            "explanation": (
                "Role Grounding evaluator failed before a "
                "usable result was produced."
            ),
            "supporting_text": "",
        }

    result = normalize_role_grounding_payload(
        candidate_id=candidate_id,
        proposed_role=proposed_role,
        payload=payload,
    )

    # A SUPPORTED result must point back to text that actually
    # exists in the supplied source evidence. The AI cannot create
    # its own grounding quote.
    if result.status == "SUPPORTED":
        normalized_source = " ".join(
            str(source_text or "").split()
        )
        normalized_support = (
            _normalize_grounding_source_quote(
                result.supporting_text
            )
        )

        if (
            not normalized_support
            or normalized_support
            not in normalized_source
        ):
            return _review_required_result(
                candidate_id=candidate_id,
                proposed_role=proposed_role,
                basis_type=(
                    "GROUNDING_SOURCE_TEXT_MISMATCH"
                ),
                explanation=(
                    "The claimed Role Grounding support "
                    "could not be traced verbatim to the "
                    "supplied source evidence."
                ),
            )

    return result


def _map_grounding_tasks(
    items,
    evaluate_one,
    *,
    max_workers: int,
):
    """
    Preserve deterministic result ordering while allowing
    independent AI grounding calls to execute concurrently.
    """
    item_list = list(items)

    if max_workers < 1:
        raise ValueError(
            "max_workers must be at least 1."
        )

    if (
        max_workers == 1
        or len(item_list) < 2
    ):
        return [
            evaluate_one(item)
            for item in item_list
        ]

    from concurrent.futures import (
        ThreadPoolExecutor,
    )

    with ThreadPoolExecutor(
        max_workers=min(
            max_workers,
            len(item_list),
        )
    ) as executor:
        return list(
            executor.map(
                evaluate_one,
                item_list,
            )
        )


def semantic_candidate_grounding_eligibility(
    candidate,
) -> tuple[bool, str]:
    """
    Determine whether a semantic candidate may enter
    Role Grounding.

    This is intentionally different from Core adapter
    acceptance.

    needs_review=True may still enter Role Grounding because
    the purpose of grounding is to resolve semantic role
    uncertainty before Engineer Review.

    Unsupported or structurally invalid constraints remain
    deterministically blocked.
    """

    extraction = getattr(
        candidate,
        "extraction",
        None,
    )

    # Preserve conservative behavior for legacy/minimal
    # candidate objects used by older tests.
    if not isinstance(extraction, dict):
        if not getattr(
            candidate,
            "adapter_accepted",
            True,
        ):
            return (
                False,
                "No structured extraction is available and "
                "the existing Core adapter rejected the candidate.",
            )

        return True, ""

    role = extraction.get(
        "constraint_role",
        getattr(candidate, "role", None),
    )

    if role not in {
        "requirement",
        "verification",
    }:
        return (
            False,
            "Requirement / Verification role is invalid.",
        )

    if extraction.get("type") == "unsupported":
        return (
            False,
            "The candidate uses unsupported constraint semantics.",
        )

    from src.ai.core_adapter import (
        validate_ai_extraction_structure,
    )

    try:
        structure_valid, structure_message = (
            validate_ai_extraction_structure(
                extraction
            )
        )
    except Exception as exc:
        return (
            False,
            "Deterministic structure validation failed: "
            f"{exc}",
        )

    if not structure_valid:
        return (
            False,
            "Deterministic structure validation rejected "
            f"the candidate: {structure_message}",
        )

    source_text = str(
        getattr(
            candidate,
            "source_text",
            "",
        )
        or ""
    ).strip()

    if not source_text:
        return (
            False,
            "Source text is missing.",
        )

    return True, ""


def ground_semantic_candidates(
    analysis,
    *,
    evaluator=None,
    max_workers: int = 1,
) -> dict[str, RoleGroundingResult]:
    """
    Ground all Requirement / Verification candidates in one
    SemanticAnalysisResult.

    Candidate objects are not modified. Grounding state is kept
    separately by candidate_id.
    """

    deterministic_results = {}
    eligible_candidates = []

    for candidate in analysis.candidates:
        (
            grounding_eligible,
            grounding_reason,
        ) = semantic_candidate_grounding_eligibility(
            candidate
        )

        if not grounding_eligible:
            extraction = getattr(
                candidate,
                "extraction",
                None,
            )

            basis_type = (
                "ADAPTER_REJECTED"
                if (
                    not isinstance(extraction, dict)
                    and not getattr(
                        candidate,
                        "adapter_accepted",
                        True,
                    )
                )
                else "GROUNDING_PRECHECK_BLOCKED"
            )

            deterministic_results[
                candidate.candidate_id
            ] = _review_required_result(
                candidate_id=candidate.candidate_id,
                proposed_role=candidate.role,
                basis_type=basis_type,
                explanation=grounding_reason,
            )
            continue

        eligible_candidates.append(candidate)

    def evaluate_one(candidate):
        return (
            candidate.candidate_id,
            evaluate_candidate_role_grounding(
                candidate_id=candidate.candidate_id,
                proposed_role=candidate.role,
                source_text=candidate.source_text,
                source_name=candidate.source_name,
                evaluator=evaluator,
            ),
        )

    evaluated = _map_grounding_tasks(
        eligible_candidates,
        evaluate_one,
        max_workers=max_workers,
    )

    evaluated_results = dict(evaluated)

    # Preserve original candidate ordering and a complete
    # candidate_id -> grounding-result mapping.
    return {
        candidate.candidate_id: (
            deterministic_results[candidate.candidate_id]
            if candidate.candidate_id
            in deterministic_results
            else evaluated_results[candidate.candidate_id]
        )
        for candidate in analysis.candidates
    }


def ground_feasible_candidates(
    analysis,
    *,
    evaluator=None,
    max_workers: int = 1,
) -> dict[str, RoleGroundingResult]:
    """
    Ground all Feasible / Observed Evidence candidates.

    FeasibleEvidenceCandidate intentionally has no semantic role
    field, so the Application layer explicitly evaluates each
    candidate against the 'feasible' engineering role.
    """

    def evaluate_one(candidate):
        return (
            candidate.candidate_id,
            evaluate_candidate_role_grounding(
                candidate_id=candidate.candidate_id,
                proposed_role="feasible",
                source_text=candidate.source_text,
                source_name=candidate.source_name,
                evaluator=evaluator,
            ),
        )

    evaluated = _map_grounding_tasks(
        analysis.candidates,
        evaluate_one,
        max_workers=max_workers,
    )

    return {
        candidate_id: result
        for candidate_id, result in evaluated
    }


def apply_role_grounding_gate(
    *,
    approved_candidate_ids: Sequence[str],
    grounding_by_candidate_id: Mapping[
        str,
        RoleGroundingResult,
    ],
) -> RoleGroundingGateResult:
    """
    Fail-safe gate placed before existing semantic/formal
    application logic.

    Engineer approval alone is insufficient.

    A candidate passes this gate only when:
        Role Grounding status == SUPPORTED

    Missing, REJECTED, or REVIEW_REQUIRED grounding is blocked.
    """

    eligible: list[str] = []
    issues: list[str] = []
    seen: set[str] = set()

    for candidate_id in approved_candidate_ids:
        if candidate_id in seen:
            continue

        seen.add(candidate_id)

        grounding = grounding_by_candidate_id.get(
            candidate_id
        )

        if grounding is None:
            issues.append(
                f"{candidate_id}: Role Grounding is missing."
            )
            continue

        if grounding.status != "SUPPORTED":
            issues.append(
                (
                    f"{candidate_id}: Role Grounding "
                    f"{grounding.status} "
                    f"({grounding.basis_type})."
                )
            )
            continue

        eligible.append(candidate_id)

    return RoleGroundingGateResult(
        eligible_candidate_ids=tuple(eligible),
        issues=tuple(issues),
    )
@dataclass(frozen=True)
class GroundedDownstreamResult:
    """
    Result of applying the independent Role Grounding gate before
    an existing downstream Application workflow.

    downstream_result is None when Role Grounding blocks execution.
    """

    grounding_gate: RoleGroundingGateResult
    downstream_result: Any | None

    @property
    def grounding_blocked(self) -> bool:
        return bool(self.grounding_gate.issues)


def build_engineer_reviewed_semantic_adapter(
    candidate,
    grounding,
):
    """
    Build a strict Core adapter result after semantic Engineer Review.

    This does NOT weaken convert_ai_constraint().

    Allowed review resolution:
    - needs_review: True -> False
    - missing/UNSPECIFIED constraint_id -> deterministic internal ID

    Numeric values, units, variables, constraint type, role,
    source text, and provenance are not rewritten.
    """

    if grounding is None or not bool(
        getattr(
            grounding,
            "supported",
            False,
        )
    ):
        return None

    if not bool(
        getattr(
            candidate,
            "source_location_ready",
            False,
        )
    ):
        return None

    extraction = getattr(
        candidate,
        "extraction",
        None,
    )

    if not isinstance(extraction, dict):
        return None

    role = str(
        getattr(
            candidate,
            "role",
            "",
        )
    ).strip()

    if role not in {
        "requirement",
        "verification",
    }:
        return None

    if extraction.get("constraint_role") != role:
        return None

    from copy import deepcopy
    from hashlib import sha256

    from src.ai.core_adapter import (
        convert_ai_constraint,
    )

    reviewed = deepcopy(
        extraction
    )

    raw_constraint_id = str(
        reviewed.get(
            "constraint_id",
            "",
        )
        or ""
    ).strip()

    if (
        not raw_constraint_id
        or raw_constraint_id.upper()
        == "UNSPECIFIED"
    ):
        candidate_id = str(
            getattr(
                candidate,
                "candidate_id",
                "",
            )
        )

        digest = sha256(
            candidate_id.encode("utf-8")
        ).hexdigest()[:12]

        prefix = (
            "R"
            if role == "requirement"
            else "V"
        )

        reviewed["constraint_id"] = (
            f"{prefix}_REVIEWED_{digest}"
        )

    # Preserve the original review_reason as audit provenance.
    # Only the unresolved-review flag is cleared by the
    # explicit human-review workflow.
    reviewed["needs_review"] = False

    return convert_ai_constraint(
        reviewed
    )


def apply_grounded_semantic_approvals(
    base_case,
    analysis,
    approved_candidate_ids: Sequence[str],
    grounding_by_candidate_id: Mapping[
        str,
        RoleGroundingResult,
    ],
    *,
    apply_func=None,
) -> GroundedDownstreamResult:
    """
    Role-grounded wrapper around the existing semantic approval
    workflow.

    Existing semantic_ingress behavior remains unchanged.
    This wrapper prevents any Engineer-approved candidate from
    reaching it unless Role Grounding is SUPPORTED.
    """

    unique_approved_ids = tuple(
        dict.fromkeys(approved_candidate_ids)
    )

    gate = apply_role_grounding_gate(
        approved_candidate_ids=unique_approved_ids,
        grounding_by_candidate_id=grounding_by_candidate_id,
    )

    if (
        gate.eligible_candidate_ids
        != unique_approved_ids
    ):
        return GroundedDownstreamResult(
            grounding_gate=gate,
            downstream_result=None,
        )

    if apply_func is None:
        from src.application.semantic_ingress import (
            apply_semantic_approvals,
        )

        selected_apply_func = (
            apply_semantic_approvals
        )
    else:
        selected_apply_func = apply_func

    # Engineer approval resolves the review state, but it does not
    # bypass the strict Core adapter. Build a private analysis copy
    # and re-adapt only the approved + grounded candidates.
    from copy import deepcopy

    reviewed_analysis = deepcopy(
        analysis
    )

    reviewed_candidates = getattr(
        reviewed_analysis,
        "candidates",
        None,
    )

    if reviewed_candidates is None:
        # Compatibility path for legacy/minimal test doubles.
        # Production SemanticAnalysisResult always carries
        # candidates. Never silently bypass strict review in
        # the production path.
        if apply_func is None:
            strict_gate = RoleGroundingGateResult(
                eligible_candidate_ids=(),
                issues=(
                    "Semantic analysis candidates are missing "
                    "during strict Engineer-review re-adaptation.",
                ),
            )

            return GroundedDownstreamResult(
                grounding_gate=strict_gate,
                downstream_result=None,
            )

        downstream_result = selected_apply_func(
            base_case,
            reviewed_analysis,
            list(gate.eligible_candidate_ids),
        )

        return GroundedDownstreamResult(
            grounding_gate=gate,
            downstream_result=downstream_result,
        )

    candidate_by_id = {
        candidate.candidate_id: candidate
        for candidate in reviewed_candidates
    }

    strict_eligible_ids = []
    strict_issues = []

    for candidate_id in gate.eligible_candidate_ids:
        candidate = candidate_by_id.get(
            candidate_id
        )

        if candidate is None:
            strict_issues.append(
                f"{candidate_id}: Candidate is missing "
                "during strict Engineer-review re-adaptation."
            )
            continue

        grounding = (
            grounding_by_candidate_id.get(
                candidate_id
            )
        )

        extraction = getattr(
            candidate,
            "extraction",
            None,
        )

        if isinstance(extraction, dict):
            reviewed_adapter = (
                build_engineer_reviewed_semantic_adapter(
                    candidate,
                    grounding,
                )
            )

            if (
                reviewed_adapter is None
                or not reviewed_adapter.accepted
            ):
                message = (
                    reviewed_adapter.message
                    if reviewed_adapter is not None
                    else (
                        "Strict Engineer-review "
                        "re-adaptation was not available."
                    )
                )

                strict_issues.append(
                    f"{candidate_id}: {message}"
                )
                continue

            candidate.adapter_result = (
                reviewed_adapter
            )

        else:
            # Preserve compatibility with legacy/minimal objects
            # used by existing orchestration tests.
            if not bool(
                getattr(
                    candidate,
                    "adapter_accepted",
                    False,
                )
            ):
                strict_issues.append(
                    f"{candidate_id}: Existing adapter "
                    "result is not accepted."
                )
                continue

        strict_eligible_ids.append(
            candidate_id
        )

    if strict_issues:
        strict_gate = RoleGroundingGateResult(
            eligible_candidate_ids=tuple(
                strict_eligible_ids
            ),
            issues=tuple(
                strict_issues
            ),
        )

        return GroundedDownstreamResult(
            grounding_gate=strict_gate,
            downstream_result=None,
        )

    downstream_result = selected_apply_func(
        base_case,
        reviewed_analysis,
        strict_eligible_ids,
    )

    return GroundedDownstreamResult(
        grounding_gate=gate,
        downstream_result=downstream_result,
    )


def build_grounded_feasible_evidence_prefills(
    analysis,
    *,
    approved_candidate_ids: Sequence[str],
    grounding_by_candidate_id: Mapping[
        str,
        RoleGroundingResult,
    ],
    canonical_variable_by_candidate: Mapping[
        str,
        str,
    ],
    prefill_builder=None,
) -> GroundedDownstreamResult:
    """
    Role-grounded wrapper around the existing source-bound
    Feasible Evidence prefill workflow.

    A candidate must have SUPPORTED Feasible/Observed-Evidence
    grounding before the existing deterministic prefill checks run.
    """

    unique_approved_ids = tuple(
        dict.fromkeys(approved_candidate_ids)
    )

    gate = apply_role_grounding_gate(
        approved_candidate_ids=unique_approved_ids,
        grounding_by_candidate_id=grounding_by_candidate_id,
    )

    if (
        gate.eligible_candidate_ids
        != unique_approved_ids
    ):
        return GroundedDownstreamResult(
            grounding_gate=gate,
            downstream_result=None,
        )

    if prefill_builder is None:
        from src.application.feasible_evidence_ingress import (
            build_feasible_evidence_prefills,
        )

        selected_builder = (
            build_feasible_evidence_prefills
        )
    else:
        selected_builder = prefill_builder

    downstream_result = selected_builder(
        analysis,
        approved_candidate_ids=list(
            gate.eligible_candidate_ids
        ),
        canonical_variable_by_candidate=dict(
            canonical_variable_by_candidate
        ),
    )

    return GroundedDownstreamResult(
        grounding_gate=gate,
        downstream_result=downstream_result,
    )


@dataclass(frozen=True)
class RoleCompletenessResult:
    """
    Deterministic product-level completeness gate.

    FOUND means that an extraction candidate exists.
    ESTABLISHED means that a candidate is grounded,
    engineer-approved, and eligible for downstream use.
    """

    requirement_candidate_count: int
    verification_candidate_count: int
    feasible_candidate_count: int

    requirement_established: bool
    verification_established: bool
    feasible_established: bool

    established_semantic_candidate_ids: tuple[str, ...]
    established_feasible_candidate_ids: tuple[str, ...]

    issues: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return (
            self.requirement_established
            and self.verification_established
            and self.feasible_established
            and not self.issues
        )


def evaluate_role_completeness(
    semantic_analysis,
    approved_semantic_candidate_ids,
    semantic_grounding_by_candidate_id,
    feasible_analysis,
    approved_feasible_candidate_ids,
    feasible_grounding_by_candidate_id,
) -> RoleCompletenessResult:
    """
    Establish R / V / F only from candidates that survive
    the complete deterministic gate.

    This function does not infer engineering semantics.
    It only evaluates previously extracted, grounded,
    source-located, and engineer-approved candidate state.
    """

    approved_semantic_ids = set(
        approved_semantic_candidate_ids
    )
    approved_feasible_ids = set(
        approved_feasible_candidate_ids
    )

    semantic_candidates = list(
        getattr(
            semantic_analysis,
            "candidates",
            (),
        )
        or ()
    )

    feasible_candidates = list(
        getattr(
            feasible_analysis,
            "candidates",
            (),
        )
        or ()
    )

    requirement_candidate_count = sum(
        candidate.role == "requirement"
        for candidate in semantic_candidates
    )

    verification_candidate_count = sum(
        candidate.role == "verification"
        for candidate in semantic_candidates
    )

    feasible_candidate_count = len(
        feasible_candidates
    )

    established_semantic_ids = []

    for candidate in semantic_candidates:
        grounding = (
            semantic_grounding_by_candidate_id.get(
                candidate.candidate_id
            )
        )

        approved = (
            candidate.candidate_id
            in approved_semantic_ids
        )

        source_ready = bool(
            getattr(
                candidate,
                "source_location_ready",
                False,
            )
        )

        grounding_supported = (
            grounding is not None
            and grounding.supported
        )

        extraction = getattr(
            candidate,
            "extraction",
            None,
        )

        if (
            approved
            and source_ready
            and grounding_supported
            and isinstance(
                extraction,
                dict,
            )
        ):
            reviewed_adapter = (
                build_engineer_reviewed_semantic_adapter(
                    candidate,
                    grounding,
                )
            )

            strict_adapter_ready = (
                reviewed_adapter is not None
                and reviewed_adapter.accepted
            )

        else:
            # Compatibility for legacy/minimal candidates that
            # predate explicit extraction-backed re-adaptation.
            strict_adapter_ready = bool(
                getattr(
                    candidate,
                    "adapter_accepted",
                    False,
                )
            )

        eligible = (
            approved
            and source_ready
            and grounding_supported
            and strict_adapter_ready
        )

        if eligible:
            established_semantic_ids.append(
                candidate.candidate_id
            )

    established_semantic_id_set = set(
        established_semantic_ids
    )

    requirement_established = any(
        candidate.role == "requirement"
        and candidate.candidate_id
        in established_semantic_id_set
        for candidate in semantic_candidates
    )

    verification_established = any(
        candidate.role == "verification"
        and candidate.candidate_id
        in established_semantic_id_set
        for candidate in semantic_candidates
    )

    established_feasible_ids = []

    for candidate in feasible_candidates:
        grounding = (
            feasible_grounding_by_candidate_id.get(
                candidate.candidate_id
            )
        )

        extraction = (
            getattr(
                candidate,
                "extraction",
                {},
            )
            or {}
        )

        eligible = (
            candidate.candidate_id
            in approved_feasible_ids
            and bool(
                getattr(
                    candidate,
                    "source_location_ready",
                    False,
                )
            )
            and not bool(
                extraction.get(
                    "needs_review",
                    True,
                )
            )
            and grounding is not None
            and grounding.supported
        )

        if eligible:
            established_feasible_ids.append(
                candidate.candidate_id
            )

    feasible_established = bool(
        established_feasible_ids
    )

    issues = []

    if not requirement_established:
        issues.append(
            "Requirement role is not established."
        )

    if not verification_established:
        issues.append(
            "Verification role is not established."
        )

    if not feasible_established:
        issues.append(
            "Observed Evidence role is not established."
        )

    return RoleCompletenessResult(
        requirement_candidate_count=(
            requirement_candidate_count
        ),
        verification_candidate_count=(
            verification_candidate_count
        ),
        feasible_candidate_count=(
            feasible_candidate_count
        ),
        requirement_established=(
            requirement_established
        ),
        verification_established=(
            verification_established
        ),
        feasible_established=(
            feasible_established
        ),
        established_semantic_candidate_ids=tuple(
            established_semantic_ids
        ),
        established_feasible_candidate_ids=tuple(
            established_feasible_ids
        ),
        issues=tuple(
            issues
        ),
    )
