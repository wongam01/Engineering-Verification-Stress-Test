from dataclasses import dataclass
from typing import Any

from src.application.models import (
    EvidenceTrace,
)
from src.core.models import (
    EngineeringCase,
)


@dataclass(frozen=True)
class ConstraintTraceEntry:
    """
    하나의 Formal Constraint와
    연결된 Source Evidence의 UI-ready view.
    """

    role: str
    target_id: str
    constraint_type: str
    formal_constraint: dict[str, Any]

    trace_status: str

    evidence: tuple[
        EvidenceTrace,
        ...,
    ] = ()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "role": self.role,
            "target_id": self.target_id,
            "constraint_type": (
                self.constraint_type
            ),
            "formal_constraint": (
                self.formal_constraint
            ),
            "trace_status": (
                self.trace_status
            ),
            "evidence": [
                item.to_dict()
                for item in self.evidence
            ],
        }


@dataclass(frozen=True)
class ConstraintTraceReport:
    """
    Formal Case 전체의 Constraint ↔ Evidence
    traceability view.

    Formal Constraint에 연결되지 않은 Evidence도
    버리지 않고 unmatched_evidence로 보존한다.
    """

    entries: tuple[
        ConstraintTraceEntry,
        ...,
    ]

    unmatched_evidence: tuple[
        EvidenceTrace,
        ...,
    ] = ()

    @property
    def has_unmatched_evidence(
        self,
    ) -> bool:
        return bool(
            self.unmatched_evidence
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "entries": [
                entry.to_dict()
                for entry in self.entries
            ],
            "unmatched_evidence": [
                item.to_dict()
                for item
                in self.unmatched_evidence
            ],
        }


def build_constraint_trace_view(
    case: EngineeringCase,
    evidence: list[
        EvidenceTrace
    ],
) -> ConstraintTraceReport:
    """
    Formal Constraint와 Evidence를
    role + target_id의 정확한 key로만 연결한다.

    추측이나 fuzzy matching은 수행하지 않는다.

    Evidence가 없는 Formal Constraint도
    EVIDENCE_NOT_LINKED 상태로 명시적으로 보존한다.
    """

    evidence_by_key: dict[
        tuple[str, str],
        list[EvidenceTrace],
    ] = {}

    for trace in evidence:
        key = (
            trace.role,
            trace.target_id,
        )

        evidence_by_key.setdefault(
            key,
            [],
        ).append(
            trace
        )

    formal_keys: set[
        tuple[str, str]
    ] = set()

    entries: list[
        ConstraintTraceEntry
    ] = []

    # =====================================================
    # REQUIREMENTS
    # =====================================================

    for constraint in case.requirements:
        key = (
            "requirement",
            constraint.id,
        )

        formal_keys.add(
            key
        )

        linked = tuple(
            evidence_by_key.get(
                key,
                [],
            )
        )

        entries.append(
            ConstraintTraceEntry(
                role="requirement",
                target_id=constraint.id,
                constraint_type=(
                    constraint.type
                ),
                formal_constraint=(
                    constraint.to_dict()
                ),
                trace_status=(
                    "EVIDENCE_LINKED"
                    if linked
                    else "EVIDENCE_NOT_LINKED"
                ),
                evidence=linked,
            )
        )

    # =====================================================
    # VERIFICATION CONSTRAINTS
    # =====================================================

    for constraint in (
        case.verification_constraints
    ):
        key = (
            "verification",
            constraint.id,
        )

        formal_keys.add(
            key
        )

        linked = tuple(
            evidence_by_key.get(
                key,
                [],
            )
        )

        entries.append(
            ConstraintTraceEntry(
                role="verification",
                target_id=constraint.id,
                constraint_type=(
                    constraint.type
                ),
                formal_constraint=(
                    constraint.to_dict()
                ),
                trace_status=(
                    "EVIDENCE_LINKED"
                    if linked
                    else "EVIDENCE_NOT_LINKED"
                ),
                evidence=linked,
            )
        )

    # =====================================================
    # FEASIBLE DOMAINS
    # =====================================================

    for variable_id, variable in (
        case.variables.items()
    ):
        key = (
            "feasible_domain",
            variable_id,
        )

        formal_keys.add(
            key
        )

        linked = tuple(
            evidence_by_key.get(
                key,
                [],
            )
        )

        entries.append(
            ConstraintTraceEntry(
                role="feasible_domain",
                target_id=variable_id,
                constraint_type=(
                    "feasible_domain"
                ),
                formal_constraint={
                    "variable": variable_id,
                    "unit": variable.unit,
                    "feasible_min": (
                        variable.feasible_min
                    ),
                    "feasible_max": (
                        variable.feasible_max
                    ),
                },
                trace_status=(
                    "EVIDENCE_LINKED"
                    if linked
                    else "EVIDENCE_NOT_LINKED"
                ),
                evidence=linked,
            )
        )

    # =====================================================
    # UNMATCHED / ORPHAN EVIDENCE
    # =====================================================

    unmatched = tuple(
        trace
        for trace in evidence
        if (
            trace.role,
            trace.target_id,
        )
        not in formal_keys
    )

    return ConstraintTraceReport(
        entries=tuple(
            entries
        ),
        unmatched_evidence=(
            unmatched
        ),
    )
