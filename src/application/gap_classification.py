"""Deterministic post-processing for Verification Gap results.

This module compares the reviewed formal Requirement and Verification
structures after the existing pipeline has run.  It does not invoke a solver,
perform unit conversion, or infer semantics with AI.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)
from src.core.pipeline import (
    PipelineResult,
    RequirementPipelineResult,
)


CLASSIFIED = "CLASSIFIED"
NO_GAP = "NO_GAP"
INDETERMINATE = "INDETERMINATE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
NOT_EVALUATED = "NOT_EVALUATED"
PARTIALLY_CLASSIFIED = "PARTIALLY_CLASSIFIED"

ACCEPTANCE_BOUNDARY_GAP = (
    "ACCEPTANCE_BOUNDARY_GAP"
)
RELATIONAL_ACCEPTANCE_BOUNDARY_GAP = (
    "RELATIONAL_ACCEPTANCE_BOUNDARY_GAP"
)
COVERAGE_GAP = "COVERAGE_GAP"
UNCLASSIFIED = "UNCLASSIFIED"

_SCALAR_TYPES = {
    "range",
    "lower_bound",
    "upper_bound",
}
_RELATIONAL_TYPES = {
    "difference_min",
    "abs_difference_max",
    "sum_upper",
}

_DISPLAY_LABELS = {
    ACCEPTANCE_BOUNDARY_GAP: (
        "Acceptance Boundary Gap"
    ),
    RELATIONAL_ACCEPTANCE_BOUNDARY_GAP: (
        "Relational Acceptance Boundary Gap"
    ),
    COVERAGE_GAP: "Coverage Gap",
    UNCLASSIFIED: "Unclassified",
}


@dataclass(frozen=True)
class GapClassification:
    """One Requirement's deterministic classification outcome."""

    requirement_id: str
    status: str
    classification_code: str | None
    display_label: str | None
    verification_ids: tuple[str, ...]
    missing_verification: bool
    rationale: str
    solver_status: str | None = None
    escape_found: bool = False
    effective_verification_lower: Decimal | None = None
    effective_verification_upper: Decimal | None = None
    ambiguity_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "status": self.status,
            "classification_code": self.classification_code,
            "display_label": self.display_label,
            "verification_ids": list(self.verification_ids),
            "missing_verification": self.missing_verification,
            "rationale": self.rationale,
            "solver_status": self.solver_status,
            "escape_found": self.escape_found,
            "effective_verification_lower": (
                str(self.effective_verification_lower)
                if self.effective_verification_lower is not None
                else None
            ),
            "effective_verification_upper": (
                str(self.effective_verification_upper)
                if self.effective_verification_upper is not None
                else None
            ),
            "ambiguity_reasons": list(
                self.ambiguity_reasons
            ),
        }


@dataclass(frozen=True)
class GapClassificationReport:
    """Case-level collection with a deterministic aggregate status."""

    case_name: str
    status: str
    items: tuple[GapClassification, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_name": self.case_name,
            "status": self.status,
            "items": [
                item.to_dict()
                for item in self.items
            ],
        }


@dataclass(frozen=True)
class _VerificationAtom:
    atom_id: str
    constraint_type: str
    unit: str
    variable: str | None = None
    lower: Decimal | None = None
    upper: Decimal | None = None
    relation_target: tuple[str, ...] | None = None
    declared_variables: tuple[str, ...] = ()


def _classified(
    requirement: RequirementSpec,
    code: str,
    verification_ids: tuple[str, ...],
    rationale: str,
    *,
    lower: Decimal | None = None,
    upper: Decimal | None = None,
) -> GapClassification:
    return GapClassification(
        requirement_id=requirement.id,
        status=CLASSIFIED,
        classification_code=code,
        display_label=_DISPLAY_LABELS[code],
        verification_ids=verification_ids,
        missing_verification=(code == COVERAGE_GAP),
        rationale=rationale,
        solver_status="SOLVED",
        escape_found=True,
        effective_verification_lower=lower,
        effective_verification_upper=upper,
    )


def _review_required(
    requirement: RequirementSpec,
    verification_ids: tuple[str, ...],
    reason: str,
) -> GapClassification:
    return GapClassification(
        requirement_id=requirement.id,
        status=REVIEW_REQUIRED,
        classification_code=UNCLASSIFIED,
        display_label=_DISPLAY_LABELS[UNCLASSIFIED],
        verification_ids=verification_ids,
        missing_verification=False,
        rationale=(
            "The confirmed escape cannot be assigned a gap type "
            "deterministically from the reviewed formal structure."
        ),
        solver_status="SOLVED",
        escape_found=True,
        ambiguity_reasons=(reason,),
    )


def _declared_variables(
    constraint: RequirementSpec,
) -> tuple[str, ...]:
    values: list[str] = []

    if constraint.variable is not None:
        values.append(constraint.variable)
    if constraint.left is not None:
        values.append(constraint.left)
    if constraint.right is not None:
        values.append(constraint.right)
    values.extend(constraint.variables)

    return tuple(values)


def _relation_target(
    constraint: RequirementSpec,
) -> tuple[str, ...] | None:
    if constraint.type == "difference_min":
        if constraint.left is None or constraint.right is None:
            return None
        return (constraint.left, constraint.right)

    if constraint.type == "abs_difference_max":
        if constraint.left is None or constraint.right is None:
            return None
        return tuple(sorted((constraint.left, constraint.right)))

    if constraint.type == "sum_upper":
        if not constraint.variables:
            return None
        return tuple(sorted(constraint.variables))

    return None


def _relation_variable_multiset(
    constraint: RequirementSpec,
) -> tuple[str, ...] | None:
    variables = _declared_variables(constraint)
    if not variables:
        return None
    return tuple(sorted(variables))


def _explicit_atom(
    constraint: RequirementSpec,
) -> _VerificationAtom:
    lower = None
    upper = None

    if constraint.type in {"range", "lower_bound"}:
        lower = constraint.min_value
    if constraint.type in {"range", "upper_bound"}:
        upper = constraint.max_value
    if constraint.type == "difference_min":
        lower = constraint.min_value
    if constraint.type in {
        "abs_difference_max",
        "sum_upper",
    }:
        upper = constraint.limit

    return _VerificationAtom(
        atom_id=constraint.id,
        constraint_type=constraint.type,
        unit=constraint.unit,
        variable=constraint.variable,
        lower=lower,
        upper=upper,
        relation_target=_relation_target(constraint),
        declared_variables=_declared_variables(constraint),
    )


def _verification_atoms(
    case: EngineeringCase,
) -> tuple[_VerificationAtom, ...]:
    atoms = [
        _explicit_atom(constraint)
        for constraint in case.verification_constraints
    ]

    for name, variable in case.variables.items():
        if (
            variable.verification_min is None
            and variable.verification_max is None
        ):
            continue

        atoms.append(
            _VerificationAtom(
                atom_id=f"variable:{name}",
                constraint_type="scalar_interval",
                unit=variable.unit,
                variable=name,
                lower=variable.verification_min,
                upper=variable.verification_max,
                declared_variables=(name,),
            )
        )

    return tuple(atoms)


def _effective_lower(
    values: list[Decimal],
) -> Decimal | None:
    if not values:
        return None
    return max(values)


def _effective_upper(
    values: list[Decimal],
) -> Decimal | None:
    if not values:
        return None
    return min(values)


def _classify_scalar_escape(
    requirement: RequirementSpec,
    direction: str | None,
    atoms: tuple[_VerificationAtom, ...],
) -> GapClassification:
    if requirement.variable is None:
        return _review_required(
            requirement,
            (),
            "The scalar Requirement target is incomplete.",
        )

    candidates = tuple(
        atom
        for atom in atoms
        if atom.variable == requirement.variable
        and atom.constraint_type in (
            _SCALAR_TYPES | {"scalar_interval"}
        )
    )
    ids = tuple(sorted(atom.atom_id for atom in candidates))

    unsupported_overlap = any(
        atom.constraint_type not in (
            _SCALAR_TYPES | _RELATIONAL_TYPES | {"scalar_interval"}
        )
        and requirement.variable in atom.declared_variables
        for atom in atoms
    )
    if unsupported_overlap:
        return _review_required(
            requirement,
            ids,
            "An unsupported Verification structure overlaps the target.",
        )

    if not candidates:
        return _classified(
            requirement,
            COVERAGE_GAP,
            (),
            "No Verification constraint evaluates the Requirement's "
            "canonical scalar target.",
        )

    if any(atom.unit != requirement.unit for atom in candidates):
        return _review_required(
            requirement,
            ids,
            "Requirement and Verification canonical units do not match.",
        )

    lower = _effective_lower(
        [atom.lower for atom in candidates if atom.lower is not None],
    )
    upper = _effective_upper(
        [atom.upper for atom in candidates if atom.upper is not None],
    )

    if lower is not None and upper is not None and lower > upper:
        return _review_required(
            requirement,
            ids,
            "The effective Verification interval is internally empty.",
        )

    if requirement.type == "range":
        if direction == "below_minimum":
            boundary = requirement.min_value
            looser = lower is None or (
                boundary is not None and lower < boundary
            )
        elif direction == "above_maximum":
            boundary = requirement.max_value
            looser = upper is None or (
                boundary is not None and upper > boundary
            )
        else:
            return _review_required(
                requirement,
                ids,
                "The range escape direction is unavailable or unsupported.",
            )
    elif requirement.type == "lower_bound":
        boundary = requirement.min_value
        looser = lower is None or (
            boundary is not None and lower < boundary
        )
    else:
        boundary = requirement.max_value
        looser = upper is None or (
            boundary is not None and upper > boundary
        )

    if boundary is None:
        return _review_required(
            requirement,
            ids,
            "The Requirement boundary is incomplete.",
        )

    if not looser:
        return _review_required(
            requirement,
            ids,
            "The effective Verification boundary is not looser than the "
            "Requirement despite the confirmed escape.",
        )

    return _classified(
        requirement,
        ACCEPTANCE_BOUNDARY_GAP,
        ids,
        "The Verification criterion evaluates the same scalar target but "
        "allows a wider acceptance boundary than the engineering "
        "requirement.",
        lower=lower,
        upper=upper,
    )


def _classify_relational_escape(
    requirement: RequirementSpec,
    atoms: tuple[_VerificationAtom, ...],
) -> GapClassification:
    target = _relation_target(requirement)
    variable_multiset = _relation_variable_multiset(requirement)
    if target is None or variable_multiset is None:
        return _review_required(
            requirement,
            (),
            "The relational Requirement target is incomplete.",
        )

    same_variables = tuple(
        atom
        for atom in atoms
        if tuple(sorted(atom.declared_variables)) == variable_multiset
    )
    incompatible = tuple(
        atom
        for atom in same_variables
        if atom.constraint_type != requirement.type
        or atom.relation_target != target
    )
    matching = tuple(
        atom
        for atom in same_variables
        if atom.constraint_type == requirement.type
        and atom.relation_target == target
    )
    all_ids = tuple(sorted(atom.atom_id for atom in same_variables))

    if incompatible:
        return _review_required(
            requirement,
            all_ids,
            "Verification constraints on the same variables use "
            "incompatible relation semantics or orientation.",
        )

    if not matching:
        return _classified(
            requirement,
            COVERAGE_GAP,
            (),
            "No Verification constraint evaluates the Requirement's "
            "canonical relationship target.",
        )

    ids = tuple(sorted(atom.atom_id for atom in matching))
    if any(atom.unit != requirement.unit for atom in matching):
        return _review_required(
            requirement,
            ids,
            "Requirement and Verification canonical units do not match.",
        )

    if requirement.type == "difference_min":
        lower = _effective_lower(
            [atom.lower for atom in matching if atom.lower is not None],
        )
        if requirement.min_value is None or lower is None:
            return _review_required(
                requirement,
                ids,
                "A required relational lower boundary is incomplete.",
            )
        looser = lower < requirement.min_value
        upper = None
    else:
        upper = _effective_upper(
            [atom.upper for atom in matching if atom.upper is not None],
        )
        if requirement.limit is None or upper is None:
            return _review_required(
                requirement,
                ids,
                "A required relational upper boundary is incomplete.",
            )
        looser = upper > requirement.limit
        lower = None

    if not looser:
        return _review_required(
            requirement,
            ids,
            "The effective Verification boundary is not looser than the "
            "Requirement despite the confirmed escape.",
        )

    return _classified(
        requirement,
        RELATIONAL_ACCEPTANCE_BOUNDARY_GAP,
        ids,
        "The Verification criterion evaluates the same relationship but "
        "allows a wider acceptance boundary than the engineering "
        "requirement.",
        lower=lower,
        upper=upper,
    )


def _classify_confirmed_escape(
    requirement: RequirementSpec,
    direction: str | None,
    atoms: tuple[_VerificationAtom, ...],
) -> GapClassification:
    if requirement.type in _SCALAR_TYPES:
        return _classify_scalar_escape(
            requirement,
            direction,
            atoms,
        )
    if requirement.type in _RELATIONAL_TYPES:
        return _classify_relational_escape(
            requirement,
            atoms,
        )
    return _review_required(
        requirement,
        (),
        "The Requirement schema is unsupported by the classifier.",
    )


def _aggregate_report_status(
    items: tuple[GapClassification, ...],
) -> str:
    if not items:
        return NOT_EVALUATED

    statuses = {item.status for item in items}
    if statuses == {NO_GAP}:
        return NO_GAP
    if statuses <= {CLASSIFIED, NO_GAP} and CLASSIFIED in statuses:
        return CLASSIFIED
    if CLASSIFIED in statuses:
        return PARTIALLY_CLASSIFIED
    if INDETERMINATE in statuses:
        return INDETERMINATE
    if REVIEW_REQUIRED in statuses:
        return REVIEW_REQUIRED
    if NOT_EVALUATED in statuses:
        return NOT_EVALUATED
    return NO_GAP


def classify_verification_gap(
    case: EngineeringCase,
    pipeline_result: PipelineResult | None,
) -> GapClassificationReport:
    """Classify existing per-Requirement results without solver execution."""

    atoms = _verification_atoms(case)
    result_groups: dict[
        str,
        list[RequirementPipelineResult],
    ] = {}

    if pipeline_result is not None:
        for result in pipeline_result.requirement_results:
            result_groups.setdefault(result.requirement_id, []).append(result)

    items: list[GapClassification] = []
    for requirement in case.requirements:
        results = result_groups.get(requirement.id, [])

        if pipeline_result is None or not results:
            items.append(
                GapClassification(
                    requirement_id=requirement.id,
                    status=NOT_EVALUATED,
                    classification_code=None,
                    display_label=None,
                    verification_ids=(),
                    missing_verification=False,
                    rationale=(
                        "No pipeline result is available for this Requirement."
                    ),
                )
            )
            continue

        if len(results) != 1:
            items.append(
                _review_required(
                    requirement,
                    (),
                    "Multiple pipeline results exist for one Requirement.",
                )
            )
            continue

        stress = results[0].stress_result
        if (
            stress.requirement_id != requirement.id
            or stress.requirement_type != requirement.type
        ):
            items.append(
                _review_required(
                    requirement,
                    (),
                    "The pipeline result identity does not match the "
                    "formal Requirement.",
                )
            )
            continue

        if stress.solver_status == "UNKNOWN":
            items.append(
                GapClassification(
                    requirement_id=requirement.id,
                    status=INDETERMINATE,
                    classification_code=None,
                    display_label=None,
                    verification_ids=(),
                    missing_verification=False,
                    rationale=(
                        "The solver result is indeterminate; no gap type "
                        "is assigned."
                    ),
                    solver_status=stress.solver_status,
                    escape_found=stress.escape_found,
                )
            )
            continue

        if not stress.escape_found:
            items.append(
                GapClassification(
                    requirement_id=requirement.id,
                    status=NO_GAP,
                    classification_code=None,
                    display_label=None,
                    verification_ids=(),
                    missing_verification=False,
                    rationale=(
                        "No Verification Escape was found for this "
                        "Requirement."
                    ),
                    solver_status=stress.solver_status,
                    escape_found=False,
                )
            )
            continue

        if stress.solver_status != "SOLVED":
            items.append(
                GapClassification(
                    requirement_id=requirement.id,
                    status=INDETERMINATE,
                    classification_code=None,
                    display_label=None,
                    verification_ids=(),
                    missing_verification=False,
                    rationale=(
                        "The solver status is not a supported decisive state; "
                        "no gap type is assigned."
                    ),
                    solver_status=stress.solver_status,
                    escape_found=stress.escape_found,
                )
            )
            continue

        items.append(
            _classify_confirmed_escape(
                requirement,
                stress.direction,
                atoms,
            )
        )

    frozen_items = tuple(items)
    return GapClassificationReport(
        case_name=case.name,
        status=_aggregate_report_status(frozen_items),
        items=frozen_items,
    )
