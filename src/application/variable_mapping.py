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

    자연어 변수명은 대소문자/공백 차이를 묶지만,
    H / h 같은 순수 symbol은 서로 다른 변수로 보존한다.
    """

    normalized = " ".join(
        source_variable.split()
    )

    is_symbol = (
        bool(normalized)
        and (
            normalized[0].isalpha()
            or normalized[0] == "_"
        )
        and all(
            character.isalnum()
            or character == "_"
            for character in normalized
        )
    )

    if is_symbol:
        return "symbol:" + normalized

    return "label:" + normalized.casefold()
