import re
from collections.abc import Sequence

from src.application.models import (
    EvidenceTrace,
)
from src.core.models import (
    EngineeringCase,
)


_PAGE_MARKER_PATTERN = re.compile(
    r"(?m)^\s*===== PDF PAGE (\d+) =====\s*$"
)


def extract_explicit_source_pages(
    source_text: str,
) -> tuple[int, ...]:
    """
    source_text 안에 명시적으로 보존된
    synthetic PDF page marker만 읽는다.

    페이지 번호를 추측하지 않는다.
    """

    pages: list[int] = []
    seen: set[int] = set()

    for match in _PAGE_MARKER_PATTERN.finditer(
        source_text
    ):
        page = int(
            match.group(1)
        )

        if page <= 0:
            continue

        if page in seen:
            continue

        seen.add(page)
        pages.append(page)

    return tuple(pages)


def select_single_source_page(
    source_pages: Sequence[int],
) -> int | None:
    """
    정확히 하나의 명시적 page만 확인된 경우에만
    source_page 단일값을 제공한다.

    여러 page에 걸친 evidence라면
    단일 page라고 축약하지 않는다.
    """

    if len(source_pages) != 1:
        return None

    return int(
        source_pages[0]
    )


def build_source_reference(
    *,
    source_name: str,
    source_block_id: str | None,
    source_pages: Sequence[int],
) -> str | None:
    """
    사람이 읽을 수 있는 deterministic source reference.

    예:
    requirement.pdf:p3:L2
    requirement.pdf:p3,p4:L2
    requirement.pdf:L2
    """

    parts = [
        source_name
    ]

    if source_pages:
        pages = ",".join(
            f"p{page}"
            for page in source_pages
        )

        parts.append(
            pages
        )

    if source_block_id:
        parts.append(
            source_block_id
        )

    if len(parts) == 1:
        return None

    return ":".join(
        parts
    )


def build_feasible_domain_evidence(
    case: EngineeringCase,
) -> list[EvidenceTrace]:
    """
    EngineeringCase의 evidence-backed Feasible Domain을
    Application-level Evidence Trace로 변환한다.

    Core의 FeasibleDomainEvidence 모델을 변경하지 않고,
    최종 workflow 결과에서 F와 그 출처를 R/V evidence와
    함께 추적할 수 있게 한다.
    """

    traces = []

    for variable_id, variable in (
        case.variables.items()
    ):
        evidence = (
            variable.feasible_evidence
        )

        if evidence is None:
            continue

        domain = (
            f"{variable.feasible_min} <= "
            f"{variable_id} <= "
            f"{variable.feasible_max} "
            f"{variable.unit}"
        ).strip()

        details = [
            "Feasible Domain: " + domain,
            (
                "Evidence Type: "
                + evidence.source_type
            ),
            (
                "Approval Status: "
                + evidence.approval_status
            ),
        ]

        if evidence.note:
            details.append(
                "Note: " + evidence.note
            )

        traces.append(
            EvidenceTrace(
                role="feasible_domain",
                target_id=variable_id,
                source_name=(
                    evidence.source_type
                ),
                source_text="\n".join(
                    details
                ),
                source_reference=(
                    evidence.source_reference
                ),
            )
        )

    return traces


def assemble_workflow_evidence(
    case: EngineeringCase,
    evidence: Sequence[
        EvidenceTrace
    ] | None = None,
) -> list[EvidenceTrace]:
    """
    전달된 document evidence와 Feasible Domain evidence를
    하나의 재사용 가능한 workflow trace로 조립한다.

    호출자가 이미 같은 variable의 feasible-domain trace를
    제공했다면 더 풍부한 기존 trace를 보존하고 중복 생성하지
    않는다.
    """

    traces = []
    feasible_identities = set()

    def evidence_identity(
        trace: EvidenceTrace,
    ) -> tuple:
        return (
            trace.role,
            trace.target_id,
            trace.source_name,
            trace.source_sha256,
            trace.source_text,
            trace.source_reference,
            trace.source_page,
            trace.source_pages,
            trace.source_block_id,
        )

    for trace in (
        evidence
        if evidence is not None
        else []
    ):
        if trace.role != "feasible_domain":
            traces.append(
                trace
            )
            continue

        identity = evidence_identity(
            trace
        )

        if identity in feasible_identities:
            continue

        feasible_identities.add(
            identity
        )
        traces.append(
            trace
        )

    for trace in (
        build_feasible_domain_evidence(
            case
        )
    ):
        identity = (
            evidence_identity(
                trace
            )
        )

        if identity in feasible_identities:
            continue

        feasible_identities.add(
            identity
        )
        traces.append(
            trace
        )

    return traces
