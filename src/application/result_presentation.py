from dataclasses import dataclass
from typing import Any

from src.application.formal_review import (
    format_code_label,
    format_value_with_unit,
)
from src.application.gap_classification import (
    GapClassificationReport,
)
from src.core.models import RequirementSpec


def format_constraint(
    extraction: dict[str, Any],
) -> str:
    kind = extraction.get("type")
    unit = extraction.get("unit") or ""
    variable = extraction.get("variable")

    if kind == "range":
        return (
            f"{extraction.get('min')} ≤ {variable} ≤ "
            f"{extraction.get('max')} {unit}"
        ).strip()

    if kind == "lower_bound":
        return (
            f"{variable} ≥ {extraction.get('min')} {unit}"
        ).strip()

    if kind == "upper_bound":
        return (
            f"{variable} ≤ {extraction.get('max')} {unit}"
        ).strip()

    if kind == "difference_min":
        return (
            f"{extraction.get('left')} - "
            f"{extraction.get('right')} ≥ "
            f"{extraction.get('min')} {unit}"
        ).strip()

    if kind == "abs_difference_max":
        return (
            f"|{extraction.get('left')} - "
            f"{extraction.get('right')}| ≤ "
            f"{extraction.get('limit')} {unit}"
        ).strip()

    if kind == "sum_upper":
        variables = " + ".join(
            extraction.get("variables", [])
        )
        return (
            f"{variables} ≤ {extraction.get('limit')} {unit}"
        ).strip()

    return str(extraction)


@dataclass(frozen=True)
class DerivedValueView:
    label: str
    expression: str
    value: str


def build_derived_value_view(
    requirement: RequirementSpec,
    actual_value: Any,
) -> DerivedValueView | None:
    if actual_value is None:
        return None

    if requirement.type in {
        "range",
        "lower_bound",
        "upper_bound",
    }:
        expression = requirement.variable or "Value"
    elif requirement.type == "difference_min":
        expression = (
            f"{requirement.left} - {requirement.right}"
        )
    elif requirement.type == "abs_difference_max":
        expression = (
            f"|{requirement.left} - {requirement.right}|"
        )
    elif requirement.type == "sum_upper":
        expression = " + ".join(
            requirement.variables
        )
    else:
        expression = "Derived Value"

    return DerivedValueView(
        label="Derived Value",
        expression=expression,
        value=format_value_with_unit(
            actual_value,
            requirement.unit,
        ),
    )


def build_gap_classification_rows(
    report: GapClassificationReport,
) -> list[dict[str, str]]:
    return [
        {
            "Requirement": item.requirement_id,
            "Status": format_code_label(
                item.status
            ),
            "Classification": (
                item.display_label or "—"
            ),
            "Explanation": item.rationale,
        }
        for item in report.items
    ]
