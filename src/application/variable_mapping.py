from copy import deepcopy
from dataclasses import dataclass

from src.ai.core_adapter import (
    convert_ai_constraint,
)
from src.ai.variable_mapper import (
    apply_variable_mappings,
    get_constraint_variables,
)
from src.application.semantic_ingress import (
    SemanticAnalysisResult,
)


@dataclass(frozen=True)
class VariableMappingTarget:
    candidate_id: str
    constraint_id: str
    role: str
    source_variable: str
    unit: str | None


def build_variable_mapping_targets(
    analysis: SemanticAnalysisResult,
) -> list[VariableMappingTarget]:
    """
    고정된 Semantic Candidate에서
    Engineer가 검토해야 할 source variable을 수집한다.
    """

    targets: list[
        VariableMappingTarget
    ] = []

    for candidate in analysis.candidates:
        source_variables = (
            get_constraint_variables(
                candidate.extraction
            )
        )

        for source_variable in source_variables:
            targets.append(
                VariableMappingTarget(
                    candidate_id=(
                        candidate.candidate_id
                    ),
                    constraint_id=(
                        candidate.constraint_id
                    ),
                    role=candidate.role,
                    source_variable=(
                        source_variable
                    ),
                    unit=(
                        candidate.extraction.get(
                            "unit"
                        )
                    ),
                )
            )

    return targets


def apply_analysis_variable_mappings(
    analysis: SemanticAnalysisResult,
    mappings_by_candidate: dict[
        str,
        dict[str, str],
    ],
) -> SemanticAnalysisResult:
    """
    Engineer가 명시적으로 선택한
    source variable → canonical variable mapping을
    이미 고정된 Semantic Analysis에 적용한다.

    AI extraction은 다시 실행하지 않는다.
    """

    updated = deepcopy(
        analysis
    )

    for candidate in updated.candidates:
        source_variables = (
            get_constraint_variables(
                candidate.extraction
            )
        )

        if not source_variables:
            continue

        candidate_decisions = (
            mappings_by_candidate.get(
                candidate.candidate_id,
                {},
            )
        )

        mappings: list[dict] = []

        for source_variable in source_variables:
            canonical = (
                candidate_decisions.get(
                    source_variable
                )
            )

            if not canonical:
                raise ValueError(
                    "Canonical Variable mapping이 "
                    "누락되었습니다: "
                    f"{candidate.candidate_id} / "
                    f"{source_variable}"
                )

            mappings.append(
                {
                    "source_variable": (
                        source_variable
                    ),
                    "canonical_variable": (
                        canonical
                    ),
                    "rationale": (
                        "Explicit engineer-approved "
                        "Application UI mapping."
                    ),
                    "needs_review": False,
                    "review_reason": None,
                }
            )

        mapped_extraction = (
            apply_variable_mappings(
                candidate.extraction,
                mappings,
                approved=True,
            )
        )

        adapter_result = (
            convert_ai_constraint(
                mapped_extraction
            )
        )

        if not adapter_result.accepted:
            raise ValueError(
                "Variable Mapping 적용 후 "
                "Core Adapter가 Constraint를 "
                "수락하지 않았습니다: "
                f"{candidate.candidate_id} / "
                f"{adapter_result.message}"
            )

        candidate.extraction = (
            mapped_extraction
        )

        candidate.adapter_result = (
            adapter_result
        )

    return updated



def normalize_source_variable_group_key(
    source_variable: str,
) -> str:
    """
    UI grouping용 key.

    Rules:
    - standalone engineering symbols preserve case:
      H != h
    - natural-language labels ending in a short engineering
      symbol are grouped with that symbol:
      "Hardness H" -> H
      "Pressure P" -> P
    - ordinary words are not reduced to their last word:
      "Outlet Temperature" != "Temperature"
    """

    normalized = " ".join(
        source_variable.split()
    )

    if not normalized:
        return "label:"

    parts = normalized.split()

    def is_identifier(
        value: str,
    ) -> bool:
        return (
            bool(value)
            and (
                value[0].isalpha()
                or value[0] == "_"
            )
            and all(
                character.isalnum()
                or character == "_"
                for character in value
            )
        )

    def is_short_engineering_symbol(
        value: str,
    ) -> bool:
        if not is_identifier(value):
            return False

        return (
            len(value) == 1
            or any(
                character.isdigit()
                for character in value
            )
            or "_" in value
            or (
                len(value) <= 4
                and value.isupper()
            )
        )

    # Standalone identifier.
    # Preserve exact case so H and h remain distinct.
    if len(parts) == 1:
        if is_identifier(normalized):
            return "symbol:" + normalized

        return "label:" + normalized.casefold()

    # Natural-language alias ending with a short
    # engineering symbol, e.g. "Hardness H".
    trailing = parts[-1]

    if is_short_engineering_symbol(
        trailing
    ):
        return "symbol:" + trailing

    return "label:" + normalized.casefold()
