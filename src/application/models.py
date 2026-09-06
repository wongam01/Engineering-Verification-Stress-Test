from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.core.assurance_report import (
    AssuranceReport,
)
from src.core.assured_pipeline import (
    AssuredPipelineResult,
)
from src.core.human_review_gate import (
    HumanReviewRecord,
)
from src.core.models import (
    EngineeringCase,
)
from src.core.review_completeness import (
    RequiredReviewTarget,
)


def _json_safe(
    value: Any,
) -> Any:
    """
    Application/UI 경계에서 Decimal 등
    Core 값을 안전하게 표현하기 위한 helper.

    Core 내부 계산 표현은 변경하지 않는다.
    """

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item)
            for item in value
        ]

    return value


@dataclass(frozen=True)
class EvidenceTrace:
    """
    하나의 formal engineering 항목과
    원문 evidence 사이의 추적 정보.

    Phase 4A에서는 Application Result schema를
    먼저 고정한다.

    Phase 4B에서 document/page/block 수준의
    Evidence Trace를 실제 parser 결과와 연결한다.
    """

    role: str
    target_id: str
    source_name: str
    source_text: str

    source_page: int | None = None
    source_pages: tuple[int, ...] = ()
    source_block_id: str | None = None
    source_reference: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "role": self.role,
            "target_id": self.target_id,
            "source_name": self.source_name,
            "source_text": self.source_text,
        }

        if self.source_page is not None:
            data["source_page"] = (
                self.source_page
            )

        if self.source_pages:
            data["source_pages"] = list(
                self.source_pages
            )

        if self.source_block_id is not None:
            data["source_block_id"] = (
                self.source_block_id
            )

        if self.source_reference is not None:
            data["source_reference"] = (
                self.source_reference
            )

        return data


@dataclass
class VerificationWorkflowResult:
    """
    제품/Application 계층에서 사용하는
    단일 Verification Workflow 결과.

    기존 Core 결과를 다시 계산하거나 해석하지 않고,
    이미 검증된 객체들을 하나의 결과에 묶는다.
    """

    status: str

    case: EngineeringCase

    required_review_targets: list[
        RequiredReviewTarget
    ]

    review_records: list[
        HumanReviewRecord
    ]

    assured_result: AssuredPipelineResult

    assurance_report: AssuranceReport

    rendered_report: str

    evidence: list[
        EvidenceTrace
    ] = field(
        default_factory=list
    )

    @property
    def core_executed(
        self,
    ) -> bool:
        return self.assured_result.core_executed

    @property
    def pipeline_result(
        self,
    ):
        return (
            self.assured_result.pipeline_result
        )

    @property
    def has_escape(
        self,
    ) -> bool:
        pipeline_result = self.pipeline_result

        if pipeline_result is None:
            return False

        return pipeline_result.has_escape

    @property
    def has_solver_indeterminate(
        self,
    ) -> bool:
        pipeline_result = self.pipeline_result

        if pipeline_result is None:
            return False

        return (
            pipeline_result
            .has_solver_indeterminate
        )

    @property
    def assurance_status(
        self,
    ) -> str:
        return (
            self.assurance_report
            .overall_status
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        UI / CLI / JSON adapter가 사용할 수 있는
        Application-level summary.

        Solver를 다시 실행하지 않는다.
        """

        return {
            "status": self.status,
            "case_name": self.case.name,
            "core_executed": (
                self.core_executed
            ),
            "has_escape": self.has_escape,
            "has_solver_indeterminate": (
                self.has_solver_indeterminate
            ),
            "assurance_status": (
                self.assurance_status
            ),
            "formal_case": _json_safe(
                self.case.to_dict()
            ),
            "required_review_targets": [
                {
                    "target_type": (
                        target.target_type
                    ),
                    "target_id": (
                        target.target_id
                    ),
                }
                for target
                in self.required_review_targets
            ],
            "evidence": [
                item.to_dict()
                for item in self.evidence
            ],
        }
