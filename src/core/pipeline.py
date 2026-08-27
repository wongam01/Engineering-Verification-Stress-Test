from dataclasses import dataclass, field

from src.core.models import (
    EngineeringCase,
)

from src.core.validator import (
    ValidationResult,
    validate_case,
)

from src.core.conflict_analyzer import (
    ConflictAnalysisResult,
    analyze_conflicts,
)

from src.core.stress_tester import (
    StressTestResult,
    stress_test_case,
)

from src.core.patch_engine import (
    PatchEvaluation,
    evaluate_patch_candidates,
    select_practical_patch,
)


# =========================================================
# REQUIREMENT RESULT
# =========================================================

@dataclass
class RequirementPipelineResult:
    """
    하나의 Requirement에 대한
    전체 검증 결과.
    """

    requirement_id: str

    stress_result: StressTestResult

    patch_evaluations: list[
        PatchEvaluation
    ] = field(
        default_factory=list
    )

    selected_patch: (
        PatchEvaluation | None
    ) = None


# =========================================================
# PIPELINE RESULT
# =========================================================

@dataclass
class PipelineResult:
    """
    Engineering Verification Pipeline의
    전체 실행 결과.
    """

    status: str

    validation: ValidationResult

    consistency: (
        ConflictAnalysisResult | None
    ) = None

    requirement_results: list[
        RequirementPipelineResult
    ] = field(
        default_factory=list
    )

    @property
    def has_escape(self) -> bool:
        """
        Requirement 중 하나라도
        Verification Escape가 있는지 확인.
        """

        return any(
            result.stress_result.escape_found
            for result
            in self.requirement_results
        )


# =========================================================
# MAIN PIPELINE
# =========================================================

def run_pipeline(
    case: EngineeringCase,
    generate_patches: bool = True,
) -> PipelineResult:
    """
    하나의 EngineeringCase를 받아
    전체 Verification 흐름을 실행한다.

    순서:

    1. 입력 오류 검사
    2. Requirement 논리 모순 검사
    3. Verification Stress Test
    4. Escape 발견 시 Patch 후보 생성
    5. Patch 재검증
    """

    # =====================================================
    # STEP 1
    # 입력 검증
    # =====================================================

    validation = validate_case(
        case
    )

    if not validation.valid:

        return PipelineResult(
            status="INVALID_INPUT",
            validation=validation,
        )

    # =====================================================
    # STEP 2
    # Requirement 논리 일관성
    # =====================================================

    consistency = analyze_conflicts(
        case
    )

    if not consistency.consistent:

        return PipelineResult(
            status="INCONSISTENT_MODEL",
            validation=validation,
            consistency=consistency,
        )

    # =====================================================
    # STEP 3
    # Verification Stress Test
    # =====================================================

    stress_results = stress_test_case(
        case
    )

    requirement_results = []

    # =====================================================
    # STEP 4
    # Requirement별 결과 처리
    # =====================================================

    for stress_result in stress_results:

        patch_evaluations = []
        selected_patch = None

        # -------------------------------------------------
        # Escape가 있는 경우에만 Patch 분석
        # -------------------------------------------------

        if (
            stress_result.escape_found
            and
            generate_patches
        ):

            patch_evaluations = (
                evaluate_patch_candidates(
                    case,
                    stress_result.requirement_id,
                )
            )

            selected_patch = (
                select_practical_patch(
                    patch_evaluations
                )
            )

        requirement_results.append(
            RequirementPipelineResult(
                requirement_id=(
                    stress_result.requirement_id
                ),

                stress_result=(
                    stress_result
                ),

                patch_evaluations=(
                    patch_evaluations
                ),

                selected_patch=(
                    selected_patch
                ),
            )
        )

    # =====================================================
    # STEP 5
    # 최종 상태
    # =====================================================

    escape_found = any(
        result.stress_result.escape_found
        for result
        in requirement_results
    )

    if escape_found:

        status = (
            "VERIFICATION_GAP_FOUND"
        )

    else:

        status = (
            "NO_ESCAPE_FOUND"
        )

    return PipelineResult(
        status=status,

        validation=validation,

        consistency=consistency,

        requirement_results=(
            requirement_results
        ),
    )