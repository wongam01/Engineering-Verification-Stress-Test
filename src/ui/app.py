import hashlib
from time import perf_counter
import re
from copy import deepcopy

import streamlit as st

# STREAMLIT CLOUD IMPORT BOOTSTRAP
import sys as _sys
from pathlib import Path as _BootstrapPath

_REPO_ROOT = _BootstrapPath(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
    apply_semantic_approvals,
    build_semantic_documents_signature,
    build_semantic_review_signature,
    confirm_ambiguous_source_location,
)
from src.application.pdf_vision_restore import (
    restore_pdf_document_from_vision_cache,
)

from src.application.pdf_ingress import (
    DEFAULT_MAX_VISION_PAGES,
    DEFAULT_MAX_DEEP_VISION_PAGES,
    build_pdf_page_preview,
    build_semantic_document,
    ingest_pdf_document,
    pdf_document_can_attempt_vision,
    pdf_document_requires_vision,
    pdf_document_should_attempt_automatic_vision,
    pdf_document_source_coverage_status,
    pdf_document_vision_candidate_page_numbers,
    prepare_pdf_document_for_semantic_analysis,
    prepare_pdf_document_with_deep_vision,
    prepare_pdf_document_views_with_vision,
    rebind_pdf_document_role,
    validate_pdf_document_set,
)
from src.ai.pdf_page_vision import (
    extract_pdf_page_with_vision,
)
from src.ai.pdf_vision_cache import (
    is_pdf_page_vision_cached,
    load_cached_pdf_page_transcription,
    warm_pdf_page_vision_cache,
)
from src.application.feasible_evidence_set import (
    analyze_feasible_evidence_documents,
)
from src.application.feasible_evidence_ingress import (
    analyze_feasible_evidence_pdf,
    build_feasible_evidence_trace,
    confirm_ambiguous_feasible_source_location,
)
from src.application.evidence_trace import (
    build_source_reference,
)
from src.application.example_source_sets import (
    FORD_REAL_WORLD_SOURCE_SET,
    load_example_source_set,
)
from src.application.role_grounding import (
    apply_grounded_semantic_approvals,
    build_engineer_reviewed_semantic_adapter,
    build_grounded_feasible_evidence_prefills,
    evaluate_role_completeness,
    ground_feasible_candidates,
    ground_semantic_candidates,
    semantic_candidate_grounding_eligibility,
)
from src.application.result_presentation import (
    build_derived_value_view,
    format_constraint,
)
from src.application.escape_execution import (
    run_verification_escape_workflow,
)
from src.application.formal_review import (
    build_exact_approved_review_records,
    build_review_state_signature,
    build_review_summary_rows,
    format_code_label,
    format_value_with_unit,
    has_review_state_changed,
)
from src.application.variable_mapping import (
    apply_analysis_variable_mappings,
    build_variable_mapping_targets,
    normalize_source_variable_group_key,
)
from src.core.review_completeness import (
    build_required_review_targets,
)
from src.core.models import (
    EngineeringCase,
)

from src.ui.ui_shell import (
    inject_ui_shell_css,
    render_hero_banner,
    render_stage_strip,
    render_section_header,
    render_soft_note,
)


st.set_page_config(
    page_title="공학 검증 스트레스 테스트",
    layout="wide",
)

inject_ui_shell_css()
render_hero_banner()
render_stage_strip()

# =========================================================
# HELPERS
# =========================================================

def safe_key(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:10]


def grounding_display_status(
    grounding,
) -> str:
    if grounding is None:
        return "NOT ESTABLISHED"

    if bool(
        getattr(
            grounding,
            "supported",
            False,
        )
    ):
        return "SUPPORTED"

    if (
        getattr(
            grounding,
            "status",
            None,
        )
        == "REJECTED"
    ):
        return "REJECTED"

    return "REVIEW REQUIRED"


def render_review_focus(
    stage: str,
    focus: str,
) -> None:
    st.markdown(
        f"""
        <div style="
            margin: 0.75rem 0 1.25rem 0;
            padding: 0.95rem 1.1rem;
            border-left: 4px solid #2F6FED;
            border-radius: 0.55rem;
            background: rgba(47, 111, 237, 0.08);
        ">
            <div style="
                font-size: 0.78rem;
                font-weight: 700;
                color: #2F6FED;
                letter-spacing: 0.02em;
                margin-bottom: 0.2rem;
            ">
                현재 단계
            </div>
            <div style="
                font-size: 1.02rem;
                font-weight: 700;
                margin-bottom: 0.7rem;
            ">
                {stage}
            </div>
            <div style="
                font-size: 0.78rem;
                font-weight: 700;
                color: #2F6FED;
                margin-bottom: 0.15rem;
            ">
                검토 포인트
            </div>
            <div style="
                font-size: 0.92rem;
                line-height: 1.55;
            ">
                {focus}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_grounding_filter_label(
    status: str,
) -> str:
    labels = {
        "전체": "전체 후보",
        "SUPPORTED": (
            "SUPPORTED · 원문이 해당 역할을 뒷받침"
        ),
        "REVIEW REQUIRED": (
            "REVIEW REQUIRED · 사람의 추가 검토 필요"
        ),
        "REJECTED": (
            "REJECTED · 현재 역할의 근거로 부적합"
        ),
        "NOT ESTABLISHED": (
            "NOT ESTABLISHED · 아직 판정되지 않음"
        ),
    }

    return labels.get(
        status,
        status,
    )


def normalize_connection_unit(
    value,
) -> str:
    return " ".join(
        str(value or "").strip().upper().split()
    )


def candidate_connection_state(
    candidate,
    anchors,
) -> str:
    """
    Display-only deterministic connection guidance.

    DIRECT:
        variable group and engineering unit exactly align.

    REVIEW:
        unit aligns, but variable wording/group differs.
        Engineer mapping is required.

    MISMATCH:
        engineering unit does not align.

    NO_CONTEXT:
        prerequisite evidence has not been selected yet.

    Numeric min/max values are intentionally NOT used.
    """
    anchors = [
        anchor
        for anchor in anchors
        if anchor is not None
    ]

    if not anchors:
        return "NO_CONTEXT"

    extraction = candidate.extraction or {}

    candidate_variable = str(
        extraction.get("variable") or ""
    ).strip()

    candidate_unit = normalize_connection_unit(
        extraction.get("unit")
    )

    anchor_variables = [
        str(
            (anchor.extraction or {}).get(
                "variable"
            )
            or ""
        ).strip()
        for anchor in anchors
    ]

    anchor_units = [
        normalize_connection_unit(
            (anchor.extraction or {}).get(
                "unit"
            )
        )
        for anchor in anchors
    ]

    if (
        not candidate_unit
        or any(not unit for unit in anchor_units)
    ):
        return "REVIEW"

    if any(
        candidate_unit != unit
        for unit in anchor_units
    ):
        return "MISMATCH"

    candidate_group = (
        normalize_source_variable_group_key(
            candidate_variable
        )
        if candidate_variable
        else ""
    )

    anchor_groups = [
        normalize_source_variable_group_key(
            variable
        )
        if variable
        else ""
        for variable in anchor_variables
    ]

    if (
        candidate_group
        and all(anchor_groups)
        and all(
            candidate_group == group
            for group in anchor_groups
        )
    ):
        return "DIRECT"

    return "REVIEW"


def connection_state_label(
    state: str,
) -> str:
    return {
        "DIRECT": "직접 연결 가능",
        "REVIEW": "Mapping 검토 필요",
        "MISMATCH": "현재 조합과 바로 연결되지 않음",
        "NO_CONTEXT": "선행 근거 선택 필요",
    }.get(
        state,
        state,
    )


def connection_state_priority(
    state: str,
) -> int:
    return {
        "DIRECT": 0,
        "REVIEW": 1,
        "MISMATCH": 2,
        "NO_CONTEXT": 3,
    }.get(
        state,
        9,
    )


def format_candidate_review_summary(
    extraction,
) -> str:
    """
    Compact, display-only summary of an extracted candidate.
    No semantic judgment is performed here.
    """

    extraction = extraction or {}

    variable = (
        extraction.get("variable")
        or "Unnamed variable"
    )

    variable = " ".join(
        str(variable).split()
    )

    constraint_type = str(
        extraction.get("type")
        or ""
    )

    minimum = extraction.get("min")
    maximum = extraction.get("max")
    unit = extraction.get("unit")

    unit_text = (
        " " + str(unit)
        if unit
        else ""
    )

    if (
        constraint_type == "range"
        and minimum is not None
        and maximum is not None
    ):
        value_text = (
            f"{minimum}–{maximum}{unit_text}"
        )

    elif (
        constraint_type == "lower_bound"
        and minimum is not None
    ):
        value_text = (
            f"≥ {minimum}{unit_text}"
        )

    elif (
        constraint_type == "upper_bound"
        and maximum is not None
    ):
        value_text = (
            f"≤ {maximum}{unit_text}"
        )

    elif (
        minimum is not None
        and maximum is not None
    ):
        value_text = (
            f"{minimum}–{maximum}{unit_text}"
        )

    elif minimum is not None:
        value_text = (
            f"{minimum}{unit_text}"
        )

    elif maximum is not None:
        value_text = (
            f"{maximum}{unit_text}"
        )

    elif constraint_type:
        value_text = constraint_type

    else:
        value_text = "Structured candidate"

    return (
        variable
        + " · "
        + value_text
    )


def build_candidate_review_title(
    *,
    proposed_role,
    extraction,
    grounding,
    source_name,
    approved=False,
) -> str:
    """
    Display-only candidate title.

    The grounding result and Engineer Approval state are
    shown, not inferred or changed.
    """

    grounding_status = grounding_display_status(
        grounding
    )

    title = (
        f"[{grounding_status}] "
        f"{proposed_role} · "
        f"{format_candidate_review_summary(extraction)} · "
        f"{source_name}"
    )

    if approved:
        title += " · SELECTED ✓"

    return title


def valid_variable_id(
    value: str,
) -> bool:
    return bool(
        re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*",
            value,
        )
    )


def build_feasible_review_signature(
    feasible_analysis,
    approved_candidate_ids,
):
    """
    F source-location review + Engineer Approval state.

    A changed signature means an already prepared model
    must no longer be reused.
    """

    if feasible_analysis is None:
        return None

    approved_ids = set(
        approved_candidate_ids
    )

    parts = [
        str(
            feasible_analysis.source_sha256
        )
    ]

    for candidate in sorted(
        feasible_analysis.candidates,
        key=lambda item: item.candidate_id,
    ):
        extraction = candidate.extraction

        parts.append(
            "|".join(
                [
                    candidate.candidate_id,
                    candidate.source_sha256,
                    candidate.source_location_status,
                    str(candidate.source_page),
                    repr(
                        tuple(
                            candidate.source_pages
                        )
                    ),
                    str(
                        candidate.candidate_id
                        in approved_ids
                    ),
                    str(
                        extraction.get(
                            "variable"
                        )
                    ),
                    str(
                        extraction.get(
                            "min"
                        )
                    ),
                    str(
                        extraction.get(
                            "max"
                        )
                    ),
                    str(
                        extraction.get(
                            "unit"
                        )
                    ),
                    str(
                        extraction.get(
                            "evidence_type"
                        )
                    ),
                    str(
                        extraction.get(
                            "needs_review"
                        )
                    ),
                ]
            )
        )

    return hashlib.sha256(
        "\n".join(
            parts
        ).encode("utf-8")
    ).hexdigest()


# =========================================================
# EVST CAPTION READABILITY
st.markdown(
    """
    <style>
    /* Streamlit caption / secondary explanatory text */
    [data-testid="stCaptionContainer"] {
        color: #52647a !important;
        font-size: 0.94rem !important;
        line-height: 1.58 !important;
        font-weight: 500 !important;
    }

    [data-testid="stCaptionContainer"] p,
    [data-testid="stCaptionContainer"] span {
        color: #52647a !important;
        font-size: 0.94rem !important;
        line-height: 1.58 !important;
        font-weight: 500 !important;
    }

    /* Small markdown text should not become excessively faint */
    .stMarkdown small {
        color: #52647a !important;
        font-size: 0.92rem !important;
        line-height: 1.55 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# SESSION STATE
# =========================================================

for key, default in {
    "semantic_analysis": None,
    "analysis_signature": None,
    "feasible_analysis": None,
    "feasible_approved_candidate_ids": [],
    "semantic_approved_candidate_ids": [],
    "semantic_role_grounding": {},
    "feasible_role_grounding": {},
    "mapped_analysis": None,
    "base_case": None,
    "verification_result": None,
    "verification_review_state": None,
    "prepared_semantic_review_signature": None,
    "prepared_feasible_review_signature": None,
    "prepared_feasible_evidence_traces": [],
    "vision_prepared_pdf_documents": {},
    "vision_prepared_physical_sources": {},
    "vision_prepared_pdf_signature": None,
    "formal_model_revision": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def build_pdf_source_set_signature(
    pdf_documents,
):
    source_hashes = sorted({
        document.content_sha256
        for document in pdf_documents
    })

    if not source_hashes:
        return None

    if len(source_hashes) == 1:
        return source_hashes[0]

    return hashlib.sha256(
        "\n".join(
            source_hashes
        ).encode("utf-8")
    ).hexdigest()


# =========================================================
# STEP 1 — DOCUMENTS
# =========================================================

# DOCUMENT PIPELINE STATE DEFAULTS
documents = []
pdf_documents = []
source_pdfs = {}
feasible_pdf_document = None
feasible_pdf_documents = []
document_input_ready = False
pdf_input_signature = None

render_section_header(
    "STAGE 01",
    "검사에 합격했는데, 설계 기준은 어길 수 있을까?",
    "EVST(Engineering Verification Stress Test)는 설계 요구조건, 실제 검사 기준, "
    "측정·시험 근거를 서로 연결해 검사에는 합격하지만 설계 요구조건을 위반하는 "
    "상태가 실제로 가능한지 찾는 공학 검증 도구입니다.",
)

st.markdown(
    "**각 숫자를 따로 비교하는 것이 아니라, 여러 변수와 조건을 동시에 적용했을 때 "
    "검사 기준은 모두 만족하면서도 설계 요구조건을 위반하는 상태가 존재하는지 검증합니다.**"
)

with st.container(border=True):
    st.markdown("#### 예시로 바로 이해하기")

    st.caption(
        "고온 압력 장비 · 관계형 조건의 동작 원리를 설명하기 위한 단순화된 가상 예시 "
        "· P = 압력, T = 온도"
    )

    example_a, example_b, example_c = st.columns(3)

    with example_a:
        st.markdown("**설계 요구조건**")
        st.markdown("### P ≤ 12 − 0.02(T − 200)")
        st.caption(
            "온도가 높아질수록 허용되는 압력이 낮아지는 조건"
        )

    with example_b:
        st.markdown("**실제 검사 기준**")
        st.markdown("### P ≤ 11 MPa")
        st.markdown("### T ≤ 300 °C")
        st.caption(
            "검사에서는 압력과 온도를 각각 따로 확인"
        )

    with example_c:
        st.markdown("**실제 관측 범위**")
        st.markdown("### 9.5 ≤ P ≤ 11 MPa")
        st.markdown("### 240 ≤ T ≤ 300 °C")
        st.caption(
            "측정 근거에서 확인된 실제 가능한 범위"
        )

    st.divider()

    st.markdown("**EVST가 가능한 상태들 중 찾아낸 조합**")
    st.markdown("### P = 11 MPa · T = 300 °C")

    state_f, state_v, state_r = st.columns(3)

    with state_f:
        st.success("✓ 실제 관측 범위 안")

    with state_v:
        st.success("✓ 개별 검사 기준 모두 통과")

    with state_r:
        st.error("✕ 설계 요구조건 위반")

    st.info(
        "검사에서는 압력과 온도를 각각 따로 확인하므로 "
        "P = 11 MPa와 T = 300 °C는 모두 검사 기준을 통과합니다. "
        "하지만 설계 요구조건에서는 온도에 따라 허용압력이 달라집니다. "
        "T = 300 °C를 설계식에 적용하면 허용압력은 10 MPa가 되므로, "
        "P = 11 MPa 상태는 설계 요구조건을 위반합니다. "
        "EVST는 이처럼 개별 검사는 모두 통과하더라도 여러 변수와 조건을 "
        "함께 적용했을 때 위반이 발생하는 실제 가능한 상태를 탐색합니다."
    )

    st.caption(
        "실제 분석에서는 더 많은 변수와 제약조건을 동시에 연결해, "
        "검사 기준을 만족하면서 설계 요구조건을 위반하는 상태가 "
        "존재하는지를 수학적으로 검증합니다."
    )


# LANDING REAL-WORLD COVERAGE GAP
st.markdown(
    "**이런 검증 누락은 실제 산업 문서에서도 확인됩니다.**"
)
st.caption(
    "아래 내용은 가상 예시가 아니라 NHTSA가 공개한 실제 recall 문서를 근거로 합니다."
)

with st.expander(
    "공식 사례 근거 보기 · Haldex / ZF",
    expanded=False,
):
    st.markdown("#### Haldex / ZF Inversion Relay Valve")
    st.caption(
        "NHTSA Recall 24E-011 · 자동차 공압식 제동장치"
    )

    source_left, source_right = st.columns(2)

    with source_left:
        st.markdown("**요구조건**")
        st.markdown("### Parking brake ≤ 3초")
        st.write(
            "주차 브레이크가 작동 후 3초 이내 완전히 작동하지 않으면 "
            "FMVSS No. 121 요구조건을 충족하지 못할 수 있습니다."
        )

    with source_right:
        st.markdown("**기존 검사에서 빠진 항목**")
        st.markdown("### 작동 지연 시간 미검사")
        st.write(
            "공급업체의 기존 시험으로 부품을 검사했지만, "
            "해당 시험에서는 작동 지연 시간을 직접 확인하지 않았습니다."
        )

    st.divider()

    st.markdown("**NHTSA 원문에서 확인되는 내용**")

    st.info(
        "2023년 조사 당시 기존 공급업체 시험에서는 작동 지연 시간을 확인하지 않았고, "
        "이후 Haldex는 주차 브레이크 작동 시간에 대한 "
        "출하 전 100% 전수 검사(EOL)를 추가했습니다."
    )

    st.write(
        "리콜 보고서에서는 inversion relay valve 문제로 주차 브레이크가 "
        "3초 이내 완전히 작동하지 않을 수 있으며, 이 경우 FMVSS No. 121 "
        "요구조건을 충족하지 못할 수 있다고 설명합니다."
    )

    link_left, link_right = st.columns(2)

    with link_left:
        st.link_button(
            "NHTSA Recall Report 원문 PDF ↗",
            "https://static.nhtsa.gov/odi/rcl/2024/RCLRPT-24E011-6939.PDF",
            use_container_width=True,
        )

    with link_right:
        st.link_button(
            "NHTSA Chronology 원문 PDF ↗",
            "https://static.nhtsa.gov/odi/rcl/2024/RMISC-24E011-6421.pdf",
            use_container_width=True,
        )

    st.caption(
        "리콜 보고서의 3초 기준은 PDF 2페이지에서 확인할 수 있습니다. "
        "사건 경과 문서에서 기존 시험의 작동 지연 시간 미검사와 이후 100% EOL 검사 추가는 "
        "1페이지에서 확인할 수 있습니다."
    )

    st.warning(
        "이 사례는 실제 검증 범위 누락(Verification Coverage Gap) 사례입니다. "
        "Ford 사례처럼 R / V / F의 수치 근거를 모두 연결해 Solver가 반례 상태까지 "
        "확정한 전체 Verification Escape 검증 사례와는 구분합니다."
    )

st.markdown("### 시작 방법")

entry_left, entry_right = st.columns(2)

with entry_left:
    with st.container(border=True):
        st.markdown(
            "#### 내 문서 분석하기"
        )
        st.markdown(
            """
            <div style="min-height: 3.4rem;">
                Engineering PDF를 업로드하면 설계 기준, 검사 기준,
                측정 근거를 찾아 서로 연결 가능한지 확인합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "내 문서 분석하기",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.get(
                    "engineering_source_entry_mode",
                    "upload",
                )
                == "upload"
                else "secondary"
            ),
            key="select_upload_entry",
        ):
            st.session_state[
                "engineering_source_entry_mode"
            ] = "upload"
            st.rerun()

with entry_right:
    with st.container(border=True):
        st.markdown(
            "#### 실제 사례로 먼저 이해하기"
        )
        st.markdown(
            """
            <div style="min-height: 3.4rem;">
                공개된 Ford 실제 문서로 검사 기준의 빈틈을
                어떻게 찾아냈는지 빠르게 확인합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Ford 실제 검증 사례 보기",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.get(
                    "engineering_source_entry_mode",
                    "upload",
                )
                == "ford"
                else "secondary"
            ),
            key="select_ford_entry",
        ):
            st.session_state[
                "engineering_source_entry_mode"
            ] = "ford"
            st.rerun()


ford_mode = (
    st.session_state.get(
        "engineering_source_entry_mode",
        "upload",
    )
    == "ford"
)

if ford_mode:
    st.subheader(
        FORD_REAL_WORLD_SOURCE_SET.title
    )

    st.caption(
        FORD_REAL_WORLD_SOURCE_SET.description
    )

    try:
        ford_sources = load_example_source_set(
            FORD_REAL_WORLD_SOURCE_SET
        )

        st.success(
            "Validated Reference Case 준비 완료 · "
            + str(len(ford_sources))
            + "개 실제 공개 원본 PDF"
        )

        st.caption(
            'Ford 실제 사례의 검증 결과와 근거 연결 과정을 먼저 보여줍니다. 필요한 경우 원본 PDF도 직접 확인할 수 있습니다.'
        )

        with st.expander(
            "원본 문서 Provenance · "
            + str(len(ford_sources))
            + " PDFs",
            expanded=False,
        ):
            for index, source in enumerate(
                ford_sources,
                start=1,
            ):
                st.markdown(
                    f"**{index:02d} · {source.filename}**"
                )
                st.caption(
                    "SHA-256 · "
                    + source.sha256
                )

        for index, source in enumerate(
            ford_sources,
            start=1,
        ):
            physical_document = ingest_pdf_document(
                role="requirement",
                filename=source.filename,
                content=source.content,
            )

            cached_physical_document = (
                st.session_state[
                    "vision_prepared_physical_sources"
                ].get(
                    physical_document.content_sha256
                )
            )

            if cached_physical_document is not None:
                physical_document = (
                    cached_physical_document
                )
            else:
                physical_document = (
                    restore_pdf_document_from_vision_cache(
                        physical_document
                    )
                )

            for role in (
                "requirement",
                "verification",
                "feasible",
            ):
                pdf_documents.append(
                    rebind_pdf_document_role(
                        physical_document,
                        role,
                    )
                )

        registered_pdf_documents = tuple(
            pdf_documents
        )

        coverage_representatives = {}

        for document in registered_pdf_documents:
            coverage_representatives.setdefault(
                document.content_sha256,
                document,
            )

        coverage_status_by_sha = {
            source_sha256: (
                pdf_document_source_coverage_status(
                    document
                )
            )
            for source_sha256, document
            in coverage_representatives.items()
        }

        usable_source_hashes = {
            source_sha256
            for source_sha256, status
            in coverage_status_by_sha.items()
            if status in {
                "TEXT_READY",
                "AUTO_VISION",
                "PARTIAL_TEXT",
            }
        }

        vision_deferred_hashes = {
            source_sha256
            for source_sha256, status
            in coverage_status_by_sha.items()
            if status == "VISION_DEFERRED"
        }

        full_source_coverage = all(
            status == "TEXT_READY"
            for status
            in coverage_status_by_sha.values()
        )

        deep_vision_source_hashes = {
            source_sha256
            for source_sha256, document
            in coverage_representatives.items()
            if (
                pdf_document_can_attempt_vision(
                    document
                )
                and pdf_document_vision_candidate_page_numbers(
                    document
                )
            )
        }

        deep_vision_source_count = len(
            deep_vision_source_hashes
        )

        full_analysis_supported = all(
            (
                not pdf_document_vision_candidate_page_numbers(
                    document
                )
            )
            or (
                pdf_document_can_attempt_vision(
                    document
                )
                and len(
                    pdf_document_vision_candidate_page_numbers(
                        document
                    )
                )
                <= DEFAULT_MAX_DEEP_VISION_PAGES
            )
            for document
            in coverage_representatives.values()
        )

        st.markdown("#### 문서 처리 범위")

        coverage_columns = st.columns(
            [1.0, 3.0]
        )

        coverage_columns[0].metric(
            "등록 문서",
            len(coverage_representatives),
        )

        with coverage_columns[1]:
            capability_text = (
                "✓ 전체 문서 분석 지원"
                if full_analysis_supported
                else "△ 일부 문서 분석 제한"
            )

            st.markdown(
                f"""
                <div class="ev-assurance-line">
                    <span>✓ 즉시 분석 {len(usable_source_hashes)}개</span>
                    <span>✓ Deep Vision 확장 {deep_vision_source_count}개</span>
                    <span>{capability_text}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        coverage_rows = []

        for source in ford_sources:
            document = coverage_representatives.get(
                source.sha256
            )

            if document is None:
                coverage_rows.append(
                    (
                        source.filename,
                        "처리 불가",
                        "문서 등록 상태를 확인할 수 없습니다.",
                    )
                )
                continue

            status = coverage_status_by_sha[
                source.sha256
            ]

            candidate_pages = (
                pdf_document_vision_candidate_page_numbers(
                    document
                )
            )

            text_page_count = (
                document.total_pages
                - len(candidate_pages)
            )

            if status == "TEXT_READY":
                state_label = "분석 가능"
                detail = (
                    "텍스트 기반 전체 페이지 준비 완료"
                )

            elif status == "AUTO_VISION":
                state_label = "자동 Vision"
                detail = (
                    f"텍스트가 없는 {len(candidate_pages)}개 "
                    "페이지를 자동 Vision으로 보완합니다."
                )

            elif status == "PARTIAL_TEXT":
                state_label = "기본 분석"
                detail = (
                    "기본 분석 준비 · "
                    "이미지 기반 페이지는 Deep Vision으로 "
                    "전체 분석 가능"
                )

            elif status == "VISION_DEFERRED":
                state_label = "Deep Vision"
                detail = (
                    "이미지 기반 문서 · "
                    "Deep Vision으로 전체 페이지 분석 가능"
                )

            else:
                state_label = "처리 불가"
                detail = (
                    "현재 지원하지 않는 PDF 처리 상태입니다."
                )

            coverage_rows.append(
                (
                    source.filename,
                    state_label,
                    detail,
                )
            )

        coverage_html = [
            '<div class="ev-coverage-list">'
        ]

        for filename, state_label, detail in coverage_rows:
            coverage_html.append(
                '<div class="ev-coverage-row">'
                f'<div class="ev-coverage-file">{filename}</div>'
                '<div>'
                f'<span class="ev-coverage-state">{state_label}</span>'
                '</div>'
                f'<div class="ev-coverage-detail">{detail}</div>'
                '</div>'
            )

        coverage_html.append("</div>")

        st.markdown(
            "".join(coverage_html),
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="ev-analysis-ready">'
            '<span class="ev-analysis-ready-dot"></span>'
            f'분석 준비 완료 · {len(usable_source_hashes)}개 즉시 분석 · '
            f'{deep_vision_source_count}개 Deep Vision 지원'
            '</div>',
            unsafe_allow_html=True,
        )

        remaining_vision_pages = sum(
            len(
                pdf_document_vision_candidate_page_numbers(
                    document
                )
            )
            for document
            in coverage_representatives.values()
            if pdf_document_can_attempt_vision(
                document
            )
        )

        remaining_vision_sources = sum(
            1
            for document
            in coverage_representatives.values()
            if (
                pdf_document_can_attempt_vision(
                    document
                )
                and pdf_document_vision_candidate_page_numbers(
                    document
                )
            )
        )

        if remaining_vision_pages <= 0:
            st.caption(
                "Deep Vision 지원 · 텍스트만으로 근거가 충분하지 않은 경우 "
                "이미지 기반 분석으로 문서 근거를 보완할 수 있습니다."
            )

            with st.expander(
                "Advanced · Optional Re-analysis",
                expanded=False,
            ):
                st.markdown(
                    "##### 원본 문서 Deep Vision 재분석"
                )
                st.info(
                    "현재 등록된 Ford reference source에는 "
                    "추가 Deep Vision 분석이 필요한 후보 페이지가 없습니다."
                )
                st.caption(
                    "Deep Vision 기능은 지원되지만, "
                    "Validated Case 결과를 확인하기 위해 "
                    "추가 재분석을 수행할 필요는 없습니다."
                )

        if remaining_vision_pages > 0:
            st.caption(
                "Deep Vision 지원 · 텍스트만으로 근거가 충분하지 않은 경우 "
                f"{remaining_vision_pages}개 후보 페이지를 이미지 기반으로 "
                "추가 분석할 수 있습니다."
            )

            with st.expander(
                "Advanced · Optional Re-analysis",
                expanded=False,
            ):
                st.markdown(
                    "##### 원본 문서 Deep Vision 재분석"
                )

                st.caption(
                    f"{remaining_vision_sources}개 문서에 "
                    "추가 이미지 분석이 가능합니다. "
                    "동일한 원본 PDF는 한 번만 처리하고, "
                    "결과를 Requirement · Verification · "
                    "실제 관측 근거 분석에 재사용합니다. "
                    "이 기능은 원본 문서를 다시 분석하기 위한 선택 기능이며, "
                    "Validated Case 결과를 확인하는 데에는 필요하지 않습니다."
                )

                if st.button(
                    "Optional · 전체 페이지 Deep Vision 재분석",
                    key="run_deep_vision_source_set",
                    type="secondary",
                    use_container_width=True,
                ):
                    try:
                        from src.ai.constraint_parser import (
                            client as vision_client,
                        )

                        unique_physical_documents = {
                            document.content_sha256: document
                            for document
                            in registered_pdf_documents
                        }

                        def cached_deep_vision_page_extractor(
                            pdf_bytes,
                            page_number,
                        ):
                            transcription = (
                                load_cached_pdf_page_transcription(
                                    pdf_bytes,
                                    page_number=page_number,
                                )
                            )

                            if transcription is None:
                                raise RuntimeError(
                                    "Vision page cache is missing "
                                    f"for page {page_number}."
                                )

                            return transcription

                        with st.spinner(
                            f"Deep Vision으로 "
                            f"{remaining_vision_pages}페이지를 "
                            "분석하고 있습니다. "
                            "문서 크기에 따라 몇 분 정도 "
                            "걸릴 수 있습니다..."
                        ):
                            for physical_document in (
                                unique_physical_documents.values()
                            ):
                                candidate_pages = (
                                    pdf_document_vision_candidate_page_numbers(
                                        physical_document
                                    )
                                )

                                if not candidate_pages:
                                    continue

                                warm_pdf_page_vision_cache(
                                    physical_document.raw_bytes,
                                    page_numbers=candidate_pages,
                                    client=vision_client,
                                    max_workers=4,
                                )

                            prepared_views = (
                                prepare_pdf_document_views_with_vision(
                                    registered_pdf_documents,
                                    vision_page_extractor=(
                                        cached_deep_vision_page_extractor
                                    ),
                                    deep_vision=True,
                                )
                            )

                        prepared_by_sha = {}

                        for document in prepared_views:
                            prepared_by_sha.setdefault(
                                document.content_sha256,
                                document,
                            )

                        physical_cache = dict(
                            st.session_state[
                                "vision_prepared_physical_sources"
                            ]
                        )

                        prepared_source_count = 0

                        for source_sha256, prepared in (
                            prepared_by_sha.items()
                        ):
                            original = (
                                coverage_representatives.get(
                                    source_sha256
                                )
                            )

                            if original is None:
                                continue

                            before_count = len(
                                pdf_document_vision_candidate_page_numbers(
                                    original
                                )
                            )

                            after_count = len(
                                pdf_document_vision_candidate_page_numbers(
                                    prepared
                                )
                            )

                            if after_count < before_count:
                                physical_cache[
                                    source_sha256
                                ] = prepared
                                prepared_source_count += 1

                        if prepared_source_count == 0:
                            raise RuntimeError(
                                "Deep Vision이 추가 페이지를 "
                                "처리하지 못했습니다."
                            )

                        st.session_state[
                            "vision_prepared_physical_sources"
                        ] = physical_cache

                        # Source text changed, so every downstream result
                        # derived from the previous source state is stale.
                        reset_values = {
                            "analysis": None,
                            "analysis_signature": None,
                            "feasible_analysis": None,
                            "feasible_approved_candidate_ids": [],
    "semantic_approved_candidate_ids": [],
                            "semantic_role_grounding": {},
                            "feasible_role_grounding": {},
                            "mapped_analysis": None,
                            "base_case": None,
                            "verification_result": None,
                            "verification_review_state": None,
                            "prepared_semantic_review_signature": None,
                            "prepared_feasible_review_signature": None,
                            "prepared_feasible_evidence_traces": [],
                        }

                        for key, value in reset_values.items():
                            st.session_state[key] = value

                        st.rerun()

                    except Exception as exc:
                        st.error(
                            "Deep Vision 처리에 실패했습니다. "
                            "기존 분석 가능 데이터는 유지됩니다. "
                            f"상세: {exc}"
                        )

        pdf_documents = [
            document
            for document in registered_pdf_documents
            if document.content_sha256
            in usable_source_hashes
        ]

        pdf_input_signature = hashlib.sha256(
            "\n".join(
                sorted(
                    source.sha256
                    for source in ford_sources
                )
            ).encode("utf-8")
        ).hexdigest()

        document_set_validation = (
            validate_pdf_document_set(
                pdf_documents
            )
        )

        blocking_document_set_issue = any(
            issue.severity == "ERROR"
            and issue.code
            != "PDF_DOCUMENT_NOT_READY"
            for issue
            in document_set_validation.issues
        )

        documents_supported_for_analysis = all(
            (
                document.ready_for_semantic_analysis
                or pdf_document_should_attempt_automatic_vision(
                    document
                )
            )
            for document in pdf_documents
        )

        document_input_ready = (
            bool(pdf_documents)
            and not blocking_document_set_issue
            and documents_supported_for_analysis
        )

        pdf_documents_fully_prepared = (
            document_input_ready
            and all(
                document.ready_for_semantic_analysis
                and not
                pdf_document_should_attempt_automatic_vision(
                    document
                )
                for document in pdf_documents
            )
        )

        if pdf_documents_fully_prepared:
            documents = [
                build_semantic_document(
                    document
                )
                for document in pdf_documents
                if document.role in {
                    "requirement",
                    "verification",
                }
            ]

            feasible_pdf_documents = [
                document
                for document in pdf_documents
                if document.role == "feasible"
            ]

            feasible_pdf_document = (
                feasible_pdf_documents[0]
                if len(
                    feasible_pdf_documents
                )
                == 1
                else None
            )

            source_pdfs = {
                (
                    document.role,
                    document.content_sha256,
                ): document
                for document in pdf_documents
            }


        elif document_input_ready:
            st.info(
                "Source set registered · Vision recovery "
                "will run when Evidence Discovery starts."
            )

        else:
            st.error(
                "The Ford source set could not be prepared "
                "for Evidence Discovery."
            )

    except Exception as exc:
        document_input_ready = False

        st.error(
            "Ford source set could not be loaded: "
            + str(exc)
        )


if ford_mode:
    st.markdown(
        """
        <style>
        div[data-testid="stCaptionContainer"] p {
            font-size: 0.94rem !important;
            line-height: 1.62 !important;
            font-weight: 500 !important;
            color: #60758d !important;
        }

        div[data-testid="stCaptionContainer"] {
            opacity: 1 !important;
        }

        button[data-baseweb="tab"] {
            color: #435a72 !important;
            opacity: 1 !important;
        }

        button[data-baseweb="tab"] p,
        button[data-baseweb="tab"] span {
            color: inherit !important;
            font-weight: 650 !important;
            opacity: 1 !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: #d94d4d !important;
        }

        button[data-baseweb="tab"]:hover {
            color: #263d55 !important;
        }

        div[data-testid="stSelectbox"] label p {
            color: #526a82 !important;
            font-size: 0.92rem !important;
            font-weight: 600 !important;
            opacity: 1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        """
        <style>
        /* Ford evidence tabs: inactive labels must remain readable */
        div[data-baseweb="tab-list"] button[role="tab"] {
            color: #445f79 !important;
            opacity: 1 !important;
            font-weight: 650 !important;
        }

        div[data-baseweb="tab-list"] button[role="tab"] * {
            color: inherit !important;
            opacity: 1 !important;
            font-weight: inherit !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"] {
            color: #445f79 !important;
            opacity: 1 !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"] * {
            color: #445f79 !important;
            opacity: 1 !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="true"] {
            color: #d84d4d !important;
            opacity: 1 !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="true"] * {
            color: #d84d4d !important;
            opacity: 1 !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"]:hover {
            color: #253f59 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    render_review_focus(
        "검증된 실제 사례",
        (
            "실제 공개된 Ford 문서를 이용해 EVST가 원문에서 근거를 찾고, "
            "엔지니어 검토와 수학적 검증을 거쳐 최종 결과에 도달하는 "
            "전체 과정을 보여줍니다."
        ),
    )

    st.markdown("## Ford Nano 흡기밸브 경도 사례")

    st.caption(
        "실제 공개된 Ford 공학 문서를 이용한 검증 사례입니다. "
        "설계 요구조건(R), 당시 검사 기준(V), 실제 관측 근거(F)를 "
        "원문에서 찾아 서로 연결한 뒤 Solver로 최종 검증합니다."
    )

    with st.expander(
        "원본 공개 문서 확인 / 다운로드 · 4 PDFs",
        expanded=False,
    ):
        st.caption(
            "Ford reference case에 사용된 실제 공개 원본 PDF입니다. "
            "파일명과 SHA-256을 확인하고 원본 전체 파일을 직접 내려받을 수 있습니다."
        )

        for source_index, source in enumerate(
            ford_sources,
            start=1,
        ):
            with st.container(border=True):
                source_left, source_right = st.columns(
                    [3.0, 1.0]
                )

                with source_left:
                    st.markdown(
                        "**"
                        + f"{source_index:02d} · "
                        + source.filename
                        + "**"
                    )

                    st.caption(
                        "SHA-256 · "
                        + source.sha256
                    )

                with source_right:
                    st.download_button(
                        "원본 PDF 다운로드",
                        data=source.content,
                        file_name=source.filename,
                        mime="application/pdf",
                        key=(
                            "ford_original_download_"
                            + safe_key(
                                source.filename
                                + source.sha256
                            )
                        ),
                        use_container_width=True,
                    )

        st.caption(
            "다운로드한 파일의 SHA-256은 위 표시값과 비교하여 "
            "reference source identity를 확인할 수 있습니다."
        )

    st.markdown("### 1. EVST 분석 과정")

    st.caption(
        "공개 원문 문서를 불러온 뒤 필요한 근거를 찾고, "
        "엔지니어 검토와 수학적 검증을 거쳐 최종 결과를 확인합니다."
    )

    pipeline_row_1 = st.columns(3)

    with pipeline_row_1[0]:
        with st.container(border=True):
            st.markdown("**01 · 원문 문서 불러오기**")
            st.metric("공개 공학 문서", "4개 PDF")
            st.caption(
                "실제 공개된 Ford 문서 4개를 원본 그대로 등록하고 "
                "분석에 사용합니다."
            )

    with pipeline_row_1[1]:
        with st.container(border=True):
            st.markdown("**02 · 문서 내용 읽기**")
            st.write("텍스트 추출 + 스캔 페이지 인식")
            st.caption(
                "일반 PDF에서는 텍스트를 추출하고, "
                "텍스트가 없는 스캔 페이지는 Vision을 이용해 "
                "읽을 수 있는 내용으로 복구합니다."
            )

    with pipeline_row_1[2]:
        with st.container(border=True):
            st.markdown("**03 · 필요한 근거 찾기**")
            st.write(
                "설계 요구조건(R) · 검사 기준(V) · 실제 관측 근거(F)"
            )
            st.caption(
                "AI는 문서에서 세 종류의 근거 후보를 찾아 정리합니다. "
                "이 단계에서는 최종 판정을 내리지 않습니다."
            )

    pipeline_row_2 = st.columns(3)

    with pipeline_row_2[0]:
        with st.container(border=True):
            st.markdown("**04 · 근거 적합성 검토**")
            st.write("원문 위치 · 역할 · 의미 확인")
            st.caption(
                '원문과 대조해 근거의 역할을 확인하고, 승인된 근거만 사용합니다.'
            )

    with pipeline_row_2[1]:
        with st.container(border=True):
            st.markdown("**05 · 조건을 수식으로 정리**")
            st.write("R / V / F를 같은 공학 변수로 연결")
            st.caption(
                '승인된 근거만 수식으로 바꾸고, 불분명한 내용은 제외합니다.'
            )

    with pipeline_row_2[2]:
        with st.container(border=True):
            st.markdown("**06 · Solver로 최종 검증**")
            st.write('정해진 규칙 + Solver')
            st.caption(
                '검사 통과와 설계 위반이 동시에 가능한지 Solver로 확인합니다.'
            )

    st.info(
        'AI는 문서에서 근거 후보를 찾아 정리합니다. 최종 판정과 반례 상태 검증은 정해진 규칙과 Solver가 수행합니다.'
    )

    st.markdown("### 2. 검증된 공학 근거 연결")

    st.caption(
        'Ford 공개 원문에서 확인한 설계 요구조건(R), 검사 기준(V), 실제 관측 근거(F)를 한눈에 보여줍니다.'
    )

    evidence_r, evidence_v, evidence_f = st.columns(3)

    with evidence_r:
        with st.container(border=True):
            st.markdown("#### 설계 요구조건 · R")

            st.markdown("**검토 항목**")
            st.write("흡기밸브 팁 경도")

            st.metric(
                "설계 요구조건 (Requirement)",
                "50–57 HRC",
            )

            st.success(
                "근거 확인 완료 · 설계 요구조건"
            )

            st.markdown("**주요 근거 문서**")
            st.caption(
                "INRD-EA23002-13504P1.pdf · Page 6"
            )

            st.markdown("**보조 근거 문서**")
            st.caption(
                "INRD-EA23002-13508P1.pdf · Page 4"
            )

            st.caption(
                "원문 근거 연결 · 엔지니어 검토 완료"
            )

    with evidence_v:
        with st.container(border=True):
            st.markdown("#### 검사 기준 · V")

            st.markdown("**검토 항목**")
            st.write("팁 경도 합격 기준")

            st.metric(
                "당시 검사 기준",
                "≥ 50 HRC",
            )

            st.success(
                "근거 확인 완료 · 당시 검사 기준"
            )

            st.markdown("**주요 근거 문서**")
            st.caption(
                "INRL-EA23002-13503.pdf · Page 2"
            )

            st.markdown("**기준 변경 이력**")
            st.caption(
                "INRL-EA23002-13503.pdf · Page 5"
            )

            st.caption(
                "원문 근거 연결 · 엔지니어 검토 완료"
            )

    with evidence_f:
        with st.container(border=True):
            st.markdown("#### 실제 관측 근거 · F")

            st.markdown("**검토 항목**")
            st.write("측정된 흡기밸브 경도")

            st.metric(
                "실제 관측 범위",
                "58–60 HRC",
            )

            st.success(
                "근거 확인 완료 · 실제 관측 근거"
            )

            st.markdown("**주요 근거 문서**")
            st.caption(
                "INRD-EA23002-13508P1.pdf · Page 4"
            )

            st.markdown("**보조 근거 문서**")
            st.caption(
                "INRD-EA23002-13506.pdf · Page 1"
            )

            st.caption(
                "문서에서 확인된 실제 관측 범위 · "
                "전체 생산 범위를 의미하지 않음"
            )


    ford_reference_pages = {
        "Requirement": [
            {
                "label": (
                    "요구조건 변경 이력 · "
                    "INRD-EA23002-13504P1.pdf · Page 6"
                ),
                "filename": "INRD-EA23002-13504P1.pdf",
                "role": "requirement",
                "page": 6,
                "support": (
                    "JT4E-6507-AB의 tip-hardness specification이 "
                    "기존 50 MIN에서 2020년 10월 "
                    "50–57 HRC로 변경된 engineering "
                    "requirement chronology를 뒷받침합니다."
                ),
            },
            {
                "label": (
                    "Drawing specification corroboration · "
                    "INRD-EA23002-13508P1.pdf · Page 4"
                ),
                "filename": "INRD-EA23002-13508P1.pdf",
                "role": "requirement",
                "page": 4,
                "support": (
                    "Ford Central Laboratory report에서 "
                    "해당 hardened region의 drawing "
                    "specification 50–57 HRC를 확인합니다."
                ),
            },
        ],
        "Verification": [
            {
                "label": (
                    "Historical SCCAF criterion · "
                    "INRL-EA23002-13503.pdf · Page 2"
                ),
                "filename": "INRL-EA23002-13503.pdf",
                "role": "verification",
                "page": 2,
                "support": (
                    "Historical SCCAF의 Tip Hardness "
                    "50 min HRC criterion과 Rockwell hardness "
                    "inspection / sampling control을 확인합니다."
                ),
            },
            {
                "label": (
                    "Upper-tolerance chronology · "
                    "INRL-EA23002-13503.pdf · Page 5"
                ),
                "filename": "INRL-EA23002-13503.pdf",
                "role": "verification",
                "page": 5,
                "support": (
                    "Ford 기록에서 SCCAF가 2021-09-07까지 "
                    "valve tip hardness upper tolerance를 "
                    "상세히 반영하지 않았던 chronology를 확인합니다."
                ),
            },
        ],
        "실제 관측 근거": [
            {
                "label": (
                    "Central Lab measured hardness · "
                    "INRD-EA23002-13508P1.pdf · Page 4"
                ),
                "filename": "INRD-EA23002-13508P1.pdf",
                "role": "feasible",
                "page": 4,
                "support": (
                    "Intake Valve 10의 실제 측정값 가운데 "
                    "58, 59, 60 HRC가 포함되고, "
                    "57 HRC upper specification을 초과한 "
                    "값이 표시된 source evidence입니다."
                ),
            },
            {
                "label": (
                    "Field-failure corroboration · "
                    "INRD-EA23002-13506.pdf · Page 1"
                ),
                "filename": "INRD-EA23002-13506.pdf",
                "role": "feasible",
                "page": 1,
                "support": (
                    "별도의 Eaton 8D record에서도 "
                    "keeper-groove region의 field-failure "
                    "valves에서 58–60 HRC 수준의 hardness가 "
                    "보고된 것을 확인합니다."
                ),
            },
        ],
    }


    def render_ford_full_width_source_preview(
        evidence,
        key_prefix,
    ):
        source = next(
            (
                item
                for item in ford_sources
                if item.filename == evidence["filename"]
            ),
            None,
        )

        if source is None:
            st.error(
                "Reference source not found · "
                + evidence["filename"]
            )
            return

        pdf_document = source_pdfs.get(
            (
                evidence["role"],
                source.sha256,
            )
        )

        if pdf_document is None:
            pdf_document = ingest_pdf_document(
                role=evidence["role"],
                filename=source.filename,
                content=source.content,
            )

        meta_left, meta_middle, meta_right = st.columns(
            [1.0, 2.3, 0.7]
        )

        meta_left.metric(
            "근거 역할",
            key_prefix,
        )

        meta_middle.caption(
            "원문 문서"
        )

        meta_middle.markdown(
            "**"
            + evidence["filename"]
            + "**"
        )

        meta_right.metric(
            "Page",
            evidence["page"],
        )

        st.info(
            evidence["support"]
        )

        try:
            st.pdf(
                build_pdf_page_preview(
                    pdf_document,
                    evidence["page"],
                ),
                height=850,
                key=(
                    "ford_full_width_source_"
                    + safe_key(
                        key_prefix
                        + ":"
                        + evidence["filename"]
                        + ":"
                        + str(evidence["page"])
                    )
                ),
            )
        except Exception as exc:
            st.error(
                "PDF page preview failed: "
                + str(exc)
            )

        detail_left, detail_right = st.columns(2)

        page_record = pdf_document.page(
            evidence["page"]
        )

        with detail_left:
            with st.expander(
                "추출된 페이지 텍스트",
                expanded=False,
            ):
                if (
                    page_record is not None
                    and str(
                        getattr(
                            page_record,
                            "text",
                            "",
                        )
                        or ""
                    ).strip()
                ):
                    st.write(
                        page_record.text
                    )
                else:
                    st.caption(
                        "이 페이지는 image-based source이며 "
                        "텍스트는 Vision recovery 경로에서 처리됩니다."
                    )

        with detail_right:
            with st.expander(
                "Source identity",
                expanded=False,
            ):
                st.caption(
                    "SHA-256 · "
                    + source.sha256
                )
                st.caption(
                    "Immutable 원문 페이지 · Page "
                    + str(evidence["page"])
                )


    st.markdown("### 2.1 원문 근거 미리보기")

    st.caption(
        "R / V / F를 구성한 실제 공개 원문 페이지를 역할별로 확인합니다. "
        "Ford 기준 근거는 하나의 PDF가 아니라 여러 engineering "
        "records에 분산되어 있으므로, primary source와 corroborating source를 "
        "함께 표시합니다."
    )

    st.markdown(
        """
        <style>
        /* EVST Ford evidence tabs — force readable inactive labels */

        div[data-baseweb="tab-list"] button[role="tab"] {
            opacity: 1 !important;
            background: transparent !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"],
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"] *,
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"] p,
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"] span,
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"] div {
            color: #34495e !important;
            -webkit-text-fill-color: #34495e !important;
            opacity: 1 !important;
            font-weight: 650 !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="true"],
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="true"] *,
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="true"] p,
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="true"] span,
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="true"] div {
            color: #e44747 !important;
            -webkit-text-fill-color: #e44747 !important;
            opacity: 1 !important;
            font-weight: 700 !important;
        }

        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"]:hover,
        div[data-baseweb="tab-list"]
        button[role="tab"][aria-selected="false"]:hover * {
            color: #172b3f !important;
            -webkit-text-fill-color: #172b3f !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if (
        "ford_source_role_view"
        not in st.session_state
    ):
        st.session_state[
            "ford_source_role_view"
        ] = "Requirement"

    source_nav_r, source_nav_v, source_nav_f = st.columns(3)

    with source_nav_r:
        if st.button(
            "설계 요구조건 근거",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state[
                    "ford_source_role_view"
                ]
                == "Requirement"
                else "secondary"
            ),
            key="ford_source_nav_requirement",
        ):
            st.session_state[
                "ford_source_role_view"
            ] = "Requirement"
            st.rerun()

    with source_nav_v:
        if st.button(
            "검사 기준 근거",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state[
                    "ford_source_role_view"
                ]
                == "Verification"
                else "secondary"
            ),
            key="ford_source_nav_verification",
        ):
            st.session_state[
                "ford_source_role_view"
            ] = "Verification"
            st.rerun()

    with source_nav_f:
        if st.button(
            "실제 관측 근거",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state[
                    "ford_source_role_view"
                ]
                == "실제 관측 근거"
                else "secondary"
            ),
            key="ford_source_nav_observed",
        ):
            st.session_state[
                "ford_source_role_view"
            ] = "실제 관측 근거"
            st.rerun()


    def render_ford_source_gallery(
        role_name,
        evidence_items,
    ):
        st.markdown(
            "#### "
            + role_name
            + " Source Evidence"
        )

        st.caption(
            role_name
            + " · "
            + str(len(evidence_items))
            + " 원문 페이지s"
        )

        for index, evidence in enumerate(
            evidence_items,
            start=1,
        ):
            with st.expander(
                (
                    f"{index:02d} · "
                    + evidence["label"]
                ),
                expanded=True,
            ):
                render_ford_full_width_source_preview(
                    evidence,
                    role_name,
                )


    selected_source_role = st.session_state[
        "ford_source_role_view"
    ]

    if selected_source_role == "Requirement":
        render_ford_source_gallery(
            "Requirement",
            ford_reference_pages[
                "Requirement"
            ],
        )

    elif selected_source_role == "Verification":
        render_ford_source_gallery(
            "Verification",
            ford_reference_pages[
                "Verification"
            ],
        )

    else:
        render_ford_source_gallery(
            "실제 관측 근거",
            ford_reference_pages[
                "실제 관측 근거"
            ],
        )


    st.markdown("### 2.2 근거 연결 요약")

    link_r, link_v, link_f = st.columns(3)

    with link_r:
        with st.container(border=True):
            st.markdown("**R · 설계 요구조건**")
            st.write("50 ≤ H ≤ 57 HRC")
            st.caption(
                "설계에서 요구하는 기준"
            )

    with link_v:
        with st.container(border=True):
            st.markdown("**V · 검사 기준**")
            st.write("H ≥ 50 HRC")
            st.caption(
                "당시 검사에서 합격으로 인정한 기준"
            )

    with link_f:
        with st.container(border=True):
            st.markdown("**F · 실제 관측 근거**")
            st.write("58 ≤ H ≤ 60 HRC")
            st.caption(
                "실제 문서에서 관측된 값"
            )

    bridge_left, bridge_middle, bridge_right = st.columns(3)

    with bridge_left:
        st.success(
            "✓ 동일한 공학 변수"
        )
        st.caption(
            "흡기밸브 경도"
        )

    with bridge_middle:
        st.success(
            "✓ 동일한 공학 단위"
        )
        st.caption(
            "Rockwell C · HRC"
        )

    with bridge_right:
        st.success(
            "✓ 원문 근거 연결 완료"
        )
        st.caption(
            "각 역할은 실제 공개 원문 근거로 추적할 수 있습니다"
        )

    st.code(
        "Source Evidence → 역할 근거 연결 → 엔지니어 검토 "
        "→ Canonical H [HRC] → R(H), V(H), F(H)",
        language="text",
    )

    st.caption(
        "R / V / F가 같은 문자열이라는 이유로 자동 연결되는 것이 아니라, "
        "같은 공학 상태를 나타내는지 검토한 뒤 "
        "공통 변수 H로 연결됩니다."
    )

    st.markdown("### 3. 수학 모델 구성")

    formal_left, formal_right = st.columns([1.4, 1.0])

    with formal_left:
        st.markdown("**공통 공학 변수**")
        st.code(
            "H = 흡기밸브 팁 경도 [HRC]",
            language="text",
        )

        st.markdown("**결정론적 제약조건**")
        st.code(
            """R(H) := 50 <= H <= 57
V(H) := H >= 50
F(H) := 58 <= H <= 60""",
            language="text",
        )

    with formal_right:
        st.markdown("**Verification Escape 탐색 조건**")
        st.code(
            """exists H:
    F(H)
AND V(H)
AND NOT R(H)""",
            language="text",
        )

        st.caption(
            "목표는 '검증은 통과하지만 실제 설계 요구조건는 "
            "위반하는 실제 가능한 상태가 존재하는가?'입니다."
        )

    st.markdown("### 4. 결정론적 검증")

    result_left, result_right = st.columns([1.0, 2.0])

    with result_left:
        with st.container(border=True):
            st.markdown("**Solver 결과**")
            st.success("검증 완료")
            st.metric(
                "확인된 반례 상태",
                "H = 60 HRC",
            )

    with result_right:
        st.markdown(
            "**반례 상태 검증 · H = 60 HRC**"
        )

        deterministic_checks = [
            (
                "실제 관측 근거 · F(60)",
                "PASS",
                (
                    '60 HRC는 문서에서 확인된 실제 관측 범위 안에 있습니다.'
                ),
            ),
            (
                "당시 검사 기준 · V(60)",
                "PASS",
                (
                    '60 HRC는 당시 검사 기준의 하한 조건을 만족합니다.'
                ),
            ),
            (
                "설계 요구조건 · R(60)",
                "FAIL",
                (
                    '60 HRC는 설계 요구조건의 상한 57 HRC를 초과합니다.'
                ),
            ),
        ]

        for (
            check_name,
            check_result,
            check_meaning,
        ) in deterministic_checks:
            with st.container(
                border=True,
            ):
                check_left, check_right = st.columns(
                    [3.0, 0.8]
                )

                with check_left:
                    st.markdown(
                        "**"
                        + check_name
                        + "**"
                    )

                    st.caption(
                        check_meaning
                    )

                with check_right:
                    if check_result == "PASS":
                        st.success(
                            "PASS"
                        )
                    else:
                        st.error(
                            "FAIL"
                        )

    st.success(
        "Verification Escape 발견 ✓ · "
        "H = 60 HRC는 F와 V를 만족하지만 R을 만족하지 않습니다."
    )

    st.markdown("### 5. 최종 판정")

    st.caption(
        'Ford 원문 근거와 수학적 검증 결과를 종합한 최종 판정입니다.'
    )

    conclusion_left, conclusion_middle, conclusion_right = (
        st.columns(3)
    )

    with conclusion_left:
        st.markdown(
            """
            <div style="
                border:1px solid rgba(120,140,165,0.28);
                border-radius:14px;
                padding:18px 20px;
                min-height:118px;
                background:rgba(255,255,255,0.58);
            ">
                <div style="
                    font-size:0.85rem;
                    font-weight:700;
                    color:#64748b;
                    margin-bottom:18px;
                ">최종 결과</div>
                <div style="
                    font-size:1.08rem;
                    font-weight:700;
                    color:#14233b;
                    line-height:1.35;
                ">Verification Escape 발견</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with conclusion_middle:
        st.markdown(
            """
            <div style="
                border:1px solid rgba(120,140,165,0.28);
                border-radius:14px;
                padding:18px 20px;
                min-height:118px;
                background:rgba(255,255,255,0.58);
            ">
                <div style="
                    font-size:0.85rem;
                    font-weight:700;
                    color:#64748b;
                    margin-bottom:18px;
                ">Solver 반례 상태</div>
                <div style="
                    font-size:1.08rem;
                    font-weight:700;
                    color:#14233b;
                ">H = 60 HRC</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with conclusion_right:
        st.markdown(
            """
            <div style="
                border:1px solid rgba(120,140,165,0.28);
                border-radius:14px;
                padding:18px 20px;
                min-height:118px;
                background:rgba(255,255,255,0.58);
            ">
                <div style="
                    font-size:0.85rem;
                    font-weight:700;
                    color:#64748b;
                    margin-bottom:18px;
                ">근거 상태</div>
                <div style="
                    font-size:1.08rem;
                    font-weight:700;
                    color:#14233b;
                ">원문 근거 확인</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='height:1.2rem'></div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### 왜 Verification Escape가 발생하는가?")

    st.caption(
        "H = 60 HRC 상태를 실제 관측 근거(F), 당시 검사 기준(V), "
        "설계 요구조건(R)에 각각 대입해 확인합니다."
    )

    reason_f, reason_v, reason_r = st.columns(3)

    with reason_f:
        with st.container(border=True):
            st.markdown("**F(60) · 실제 관측 근거**")
            st.success("통과")
            st.write(
                "60 HRC는 문서에서 확인된 "
                "58–60 HRC 실제 관측 범위 안에 있습니다."
            )

    with reason_v:
        with st.container(border=True):
            st.markdown("**V(60) · 당시 검사 기준**")
            st.success("통과")
            st.write(
                "60 HRC는 당시 검사 기준인 "
                "H ≥ 50을 만족합니다."
            )

    with reason_r:
        with st.container(border=True):
            st.markdown("**R(60) · 설계 요구조건**")
            st.error("위반")
            st.write(
                "60 HRC는 변경된 설계 요구조건의 "
                "상한 57 HRC를 초과합니다."
            )

    st.success(
        "최종 결론 · H = 60 HRC는 실제 문서에서 확인된 값이며, "
        "당시 검사 기준은 통과하지만 변경된 설계 요구조건은 위반합니다. "
        "따라서 F(H) ∧ V(H) ∧ ¬R(H)를 만족하는 "
        "Verification Escape가 존재합니다."
    )

    st.info(
        '공학적 의미 · 설계 요구조건에는 57 HRC 상한이 추가되었지만, 당시 검사 기준은 50 HRC 하한 중심으로 남아 있었습니다.\n\nEVST는 이 차이를 원문 근거와 수학 모델로 연결해 검증합니다.'
    )

    with st.expander(
        "해석 범위 / 과도한 주장 방지",
        expanded=False,
    ):
        st.write(
            "이 결과는 58–60 HRC 범위의 모든 부품이 "
            "당시 실제 검사에 합격했다는 뜻이 아닙니다."
        )

        st.write(
            "58–60 HRC는 전체 생산 범위가 아니라 "
            "공개 문서에서 확인된 실제 관측 범위입니다."
        )

        st.write(
            "또한 경도가 밸브 파손의 유일한 원인이라고 "
            "주장하지 않습니다."
        )

        st.write(
            "Verification Escape는 EVST에서 사용하는 분석 용어이며, "
            "Ford 또는 NHTSA가 사용한 표현은 아닙니다."
        )

    st.markdown("### 6. 누가 무엇을 판단하는가")

    st.caption(
        "AI가 최종 공학 판정을 내리지 않도록 "
        "문서 분석, 사람 검토, 수학적 검증의 책임을 분리합니다."
    )

    responsibility_ai, responsibility_human, responsibility_core = (
        st.columns(3)
    )

    with responsibility_ai:
        with st.container(border=True):
            st.markdown("#### AI · 문서 근거 정리")
            st.write(
                "문서에서 R / V / F 후보와 원문 위치를 찾아 "
                "검토하기 쉬운 형태로 정리합니다."
            )
            st.info("최종 판정은 하지 않습니다.")

    with responsibility_human:
        with st.container(border=True):
            st.markdown("#### 엔지니어 · 근거 검토")
            st.write(
                "찾은 근거의 역할과 의미가 맞는지, "
                "같은 공학 변수를 설명하는지 확인하고 승인합니다."
            )
            st.info("문서에 없는 조건을 새로 만들지 않습니다.")

    with responsibility_core:
        with st.container(border=True):
            st.markdown("#### 검증 코어 · 최종 검증")
            st.write(
                "승인된 조건만 수학 모델로 구성하고 "
                "Solver를 이용해 Verification Escape 여부를 판정합니다."
            )
            st.info("AI의 추측으로 결과를 바꾸지 않습니다.")

    with st.expander("세부 책임 범위 보기", expanded=False):
        detail_ai, detail_human, detail_core = st.columns(3)

        with detail_ai:
            st.markdown("**AI**")
            st.write("✓ 근거 후보 탐색")
            st.write("✓ 공학 맥락 구조화")
            st.write("✓ 원문 위치 연결")
            st.write("✕ 엔지니어 승인")
            st.write("✕ 최종 판정")

        with detail_human:
            st.markdown("**엔지니어**")
            st.write("✓ 원문 위치 검토")
            st.write("✓ 역할과 의미 검토")
            st.write("✓ 근거 승인")
            st.write("✓ 공통 변수 연결")
            st.write("✕ Solver 결과 임의 변경")

        with detail_core:
            st.markdown("**검증 코어**")
            st.write("✓ R / V / F 수학 모델")
            st.write("✓ Solver 실행")
            st.write("✓ 반례 상태 검증")
            st.write("✓ Verification Escape 판정")
            st.write("✕ 근거 없는 의미 추정")

    st.markdown("#### 근거가 부족하거나 불명확하면?")

    fail_left, fail_middle, fail_right = st.columns(3)

    with fail_left:
        with st.container(border=True):
            st.markdown("**근거 부족**")
            st.warning("수학 모델 구성 중단")
            st.caption(
                "R / V / F에 필요한 근거가 없으면 "
                "Verification Escape를 만들어내지 않습니다."
            )

    with fail_middle:
        with st.container(border=True):
            st.markdown("**의미 불명확**")
            st.warning("사람 검토 필요")
            st.caption(
                "문장의 역할이나 의미가 불분명하면 "
                "자동으로 다음 단계에 넘기지 않습니다."
            )

    with fail_right:
        with st.container(border=True):
            st.markdown("**지원 불가 / 판단 불가**")
            st.warning("확정 판정 없음")
            st.caption(
                "현재 지원하지 않는 의미나 Solver가 판단할 수 없는 상태를 "
                "Verification Escape로 보고하지 않습니다."
            )

    st.info(
        "Ford 사례의 숫자 비교는 전체 과정의 마지막 단계입니다. "
        "핵심은 실제 문서에서 근거를 찾고, 사람이 검토한 뒤, "
        "승인된 조건만 수학적으로 검증하는 것입니다."
    )

    st.divider()

    st.markdown("### 7. 다른 공학 문서는 어떻게 분석하나?")

    st.write(
        "위 Ford 사례는 실제 공개 문서를 이용해 "
        "EVST의 전체 분석 과정을 확인한 실제 검증 사례입니다. "
        "새로운 공학 PDF를 분석할 때도 같은 방식으로 "
        "원문에서 필요한 근거를 찾고, 근거의 의미를 확인하고, "
        "엔지니어 검토를 거쳐 수학 모델을 만든 뒤 Solver로 검증합니다."
    )

    st.info(
        "설계 요구조건(R), 검사 기준(V), 실제 관측 근거(F)가 "
        "충분히 확인되지 않거나 서로 같은 공학 상태를 설명하지 않는다면, "
        "시스템은 결과를 억지로 만들지 않고 수학적 검증을 시작하지 않습니다."
    )

    if st.button(
        "다른 공학 PDF 분석하기",
        type="primary",
        use_container_width=True,
        key="ford_to_generic_analysis",
    ):
        st.session_state[
            "engineering_source_entry_mode"
        ] = "upload"

        reset_keys = (
            "analysis",
            "analysis_signature",
            "feasible_analysis",
            "semantic_role_grounding",
            "feasible_role_grounding",
            "semantic_approved_candidate_ids",
            "feasible_approved_candidate_ids",
            "mapped_analysis",
            "base_case",
            "verification_result",
            "verification_review_state",
            "engineer_variable_mapping_confirmed",
            "engineer_feasible_group_override",
        )

        for key in reset_keys:
            st.session_state.pop(key, None)

        st.rerun()

    st.divider()

    st.markdown("### 8. 시스템을 어떻게 검증했나?")

    st.caption(
        "Ford 사례 하나만 맞도록 만든 시스템이 아닌지, "
        "잘못된 입력과 처음 보는 문서에서도 안전하게 동작하는지를 "
        "별도의 테스트로 확인했습니다."
    )

    validation_row_1 = st.columns(2)

    with validation_row_1[0]:
        with st.container(border=True):
            st.markdown(
                "#### 01 · 특정 숫자를 외운 시스템인가?"
            )
            st.success("아님 · 4개 변형 테스트 통과")
            st.write(
                "실제 가능한 범위와 설계 요구조건 등을 바꾸었을 때 "
                "Solver 결과도 그에 따라 달라지는지 확인했습니다."
            )

    with validation_row_1[1]:
        with st.container(border=True):
            st.markdown(
                "#### 02 · 잘못된 입력에서 안전하게 멈추는가?"
            )
            st.success("8/8 상황 안전 차단 · 14개 검증 항목 통과")
            st.write(
                "근거 부족, 지원하지 않는 의미, 사람 검토 미완료, "
                "Solver 판단 불가 등 오류 상황에서 "
                "잘못된 확정 판정을 하지 않는지 확인했습니다."
            )

    validation_row_2 = st.columns(2)

    with validation_row_2[0]:
        with st.container(border=True):
            st.markdown(
                "#### 03 · 처음 보는 실제 문서에서도 같은 원칙을 쓰는가?"
            )
            st.info("Kyogle 실제 보고서 · 경계 동작 확인")
            st.write(
                "근거 후보 추출과 원문 추적은 수행했지만, "
                "R / V / F가 서로 연결될 수 없다고 판단되어 "
                "수학 모델 구성과 Solver 실행을 차단했습니다."
            )

    with validation_row_2[1]:
        with st.container(border=True):
            st.markdown(
                "#### 04 · 지원하지 않는 의미를 억지로 수식화하는가?"
            )
            st.info("지원 범위를 벗어나면 판정 차단")
            st.write(
                "조건부·관계형 의미처럼 현재 모델이 안전하게 표현할 수 없는 "
                "내용은 억지로 단순한 수치 조건으로 바꾸지 않습니다."
            )

    st.info(
        "검증 해석 · Ford는 실제 공개 문서에서 R / V / F 근거를 모두 연결해 "
        "Solver 반례 상태까지 확인한 전체 검증 사례입니다. "
        "다른 실제 문서와 오류 입력 테스트는 일반화 범위와 "
        "안전 차단 동작을 확인하는 별도의 검증 근거입니다."
    )

    with st.expander(
        "검증 코드와 실행 기록 직접 확인",
        expanded=False,
    ):
        st.caption(
            "아래 경로는 실제 저장 위치이며, 파일이 존재하면 "
            "버튼으로 원본 파일을 직접 내려받을 수 있습니다."
        )

        anti_path = (
            _REPO_ROOT
            / "tests"
            / "test_anti_hardcoding_mutation.py"
        )

        fault_path = (
            _REPO_ROOT
            / "validation"
            / "fault_injection_03"
            / "prototype"
            / "run_01_fault_injection_output.txt"
        )

        artifact_left, artifact_right = st.columns(2)

        with artifact_left:
            st.markdown("**특정 값 의존성 검증 코드**")
            st.code(
                "tests/test_anti_hardcoding_mutation.py",
                language=None,
            )

            if anti_path.exists():
                st.download_button(
                    "검증 코드 다운로드",
                    data=anti_path.read_bytes(),
                    file_name=anti_path.name,
                    mime="text/x-python",
                    key="download_anti_hardcoding_test",
                    use_container_width=True,
                )
            else:
                st.warning("현재 실행 환경에서 파일을 찾을 수 없습니다.")

        with artifact_right:
            st.markdown("**오류 입력 안전성 검증 기록**")
            st.code(
                "validation/fault_injection_03/"
                "prototype/run_01_fault_injection_output.txt",
                language=None,
            )

            if fault_path.exists():
                st.download_button(
                    "검증 기록 다운로드",
                    data=fault_path.read_bytes(),
                    file_name=fault_path.name,
                    mime="text/plain",
                    key="download_fault_injection_log",
                    use_container_width=True,
                )
            else:
                st.warning("현재 실행 환경에서 파일을 찾을 수 없습니다.")

        _fault_output_text = ""
        _fault_lines = []

        if fault_path.exists():
            try:
                _fault_output_text = fault_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                _fault_lines = _fault_output_text.splitlines()
            except OSError:
                _fault_output_text = ""
                _fault_lines = []

        if _fault_output_text:
            st.markdown("**공식 실행 결과 요약**")

            _fault_summary_lines = [
                line
                for line in _fault_lines
                if (
                    line.startswith("Expected cases:")
                    or line.startswith("Observed cases:")
                    or line.startswith("Passed cases:")
                    or line.startswith("RESULT:")
                )
            ]

            if _fault_summary_lines:
                st.code(
                    "\n".join(_fault_summary_lines),
                    language=None,
                )

    st.stop()


if not ford_mode:

    st.subheader("내 문서 분석하기")

    with st.container(border=True):

        st.markdown("#### 어떤 문서를 분석할 수 있나요?")

        st.write(
            "EVST는 다양한 공학 PDF에서 "
            "설계 요구조건(R), 실제 검사·합격 기준(V), "
            "측정·시험 등 실제 관측 근거(F)를 찾습니다."
        )

        st.caption(
            "원문 근거가 확인되고 R / V / F가 같은 공학 상태를 "
            "설명한다고 판단될 때만 수학적 검증 단계로 진행합니다."
        )

        st.info(
            "모든 PDF에서 Verification Escape가 발견되는 것은 아닙니다. "
            "필요한 근거가 부족하거나 의미가 불명확하거나, "
            "서로 다른 공학 항목을 설명하는 근거라면 "
            "수학 모델을 만들기 전에 안전하게 차단합니다."
        )

        st.markdown(
            "**분석 결과는 다음 세 가지 중 하나입니다.**"
        )

        result_found, result_none, result_blocked = st.columns(3)

        with result_found:

            with st.container(border=True):

                st.markdown(
                    "**Verification Escape 발견**"
                )

                st.caption(
                    "실제 가능한 상태 중 검사 기준은 통과하지만 "
                    "설계 요구조건을 위반하는 상태가 존재합니다."
                )

        with result_none:

            with st.container(border=True):

                st.markdown(
                    "**Verification Escape 없음**"
                )

                st.caption(
                    "R / V / F 수학 모델은 성립하지만 "
                    "검사 기준을 통과하면서 설계 요구조건을 "
                    "위반하는 상태는 발견되지 않습니다."
                )

        with result_blocked:

            with st.container(border=True):

                st.markdown(
                    "**수학 모델 구성 차단**"
                )

                st.caption(
                    "근거 부족, 의미 불명확, 변수·단위 불일치 등으로 "
                    "신뢰할 수 있는 수학 모델을 만들 수 없는 상태입니다."
                )

    st.caption(
        "EVST는 특정 Ford 문서나 특정 수치에 맞춘 시스템이 아니라, "
        "지원되는 공학 제약조건 구조와 원문 근거를 기준으로 분석합니다."
    )

    st.caption(
        "공학 PDF 한 개를 업로드하면 동일한 원본 문서에서 "
        "설계 요구조건, 검사 기준, 실제 관측 근거 후보를 각각 탐색합니다."
    )

    uploaded_source = st.file_uploader(
        "공학 PDF",
        type=["pdf"],
        accept_multiple_files=False,
        key="engineering_single_source_upload",
    )

    st.info(
        "🔒 보안 안내 · 분석 과정에서 문서의 텍스트 또는 일부 페이지가 "
        "OpenAI API로 전송될 수 있습니다. 사내 기밀·보안 문서는 "
        "회사 정책상 외부 AI 서비스 이용이 허용된 경우에만 업로드해 주세요."
    )


    if uploaded_source is not None:
        raw_bytes = uploaded_source.getvalue()

        source_hash = hashlib.sha256(
            raw_bytes
        ).hexdigest()

        with st.container(border=True):
            st.markdown(
                "#### Registered Engineering Source"
            )

            st.write(uploaded_source.name)

            st.caption(
                "Source identity · SHA-256 "
                + source_hash
            )

            st.markdown(
                "**Automatic Evidence Discovery**"
            )

            st.caption(
                "The source is routed through three independent "
                "analysis lenses. A lens result is only a proposed "
                "engineering role; it is not treated as role truth "
                "until Role Grounding and Engineer Review are complete."
            )

            lens_columns = st.columns(3)

            with lens_columns[0]:
                st.info(
                    "Requirement Lens\n\n"
                    "Searches for normative engineering "
                    "requirements."
                )

            with lens_columns[1]:
                st.info(
                    "Verification Lens\n\n"
                    "Searches for inspection, test, or "
                    "acceptance criteria."
                )

            with lens_columns[2]:
                st.info(
                    "실제 관측 근거 Lens\n\n"
                    "Searches for actual measured, tested, "
                    "manufactured, or observed states."
                )

            physical_document = ingest_pdf_document(
                role="requirement",
                filename=uploaded_source.name,
                content=raw_bytes,
            )

            cached_physical_document = (
                st.session_state[
                    "vision_prepared_physical_sources"
                ].get(
                    physical_document.content_sha256
                )
            )

            if cached_physical_document is not None:
                physical_document = (
                    cached_physical_document
                )
            else:
                physical_document = (
                    restore_pdf_document_from_vision_cache(
                        physical_document
                    )
                )

            for role in (
                "requirement",
                "verification",
                "feasible",
            ):
                pdf_documents.append(
                    rebind_pdf_document_role(
                        physical_document,
                        role,
                    )
                )

            representative = pdf_documents[0]

            st.caption(
                "Pages · "
                + str(representative.total_pages)
            )

            if all(
                document.ready_for_semantic_analysis
                for document in pdf_documents
            ):
                st.success(
                    "Integrity checked · Source identity recorded · "
                    "Ready for Automatic Evidence Discovery"
                )

            elif any(
                pdf_document_requires_vision(
                    document
                )
                and pdf_document_can_attempt_vision(
                    document
                )
                for document in pdf_documents
            ):
                st.info(
                    "Scanned/image-only page(s) detected. "
                    "Vision recovery will run automatically "
                    "when analysis starts."
                )

            else:
                st.error(
                    "This PDF cannot currently be prepared "
                    "for engineering evidence analysis."
                )

            shown_issues = set()

            for document in pdf_documents:
                for issue in document.issues:
                    issue_key = (
                        issue.code,
                        issue.message,
                        issue.severity,
                    )

                    if issue_key in shown_issues:
                        continue

                    shown_issues.add(issue_key)

                    if issue.severity == "ERROR":
                        st.error(
                            f"{issue.code} · "
                            f"{issue.message}"
                        )
                    else:
                        st.warning(
                            f"{issue.code} · "
                            f"{issue.message}"
                        )

        pdf_input_signature = source_hash

        document_set_validation = (
            validate_pdf_document_set(
                pdf_documents
            )
        )

        for issue in document_set_validation.issues:
            if issue.code in {
                "PDF_DOCUMENT_NOT_READY",
                "PDF_REUSED_ACROSS_ROLES",
            }:
                continue

            if issue.severity == "ERROR":
                st.error(
                    f"{issue.code} · {issue.message}"
                )
            else:
                st.warning(
                    f"{issue.code} · {issue.message}"
                )

        blocking_document_set_issue = any(
            issue.severity == "ERROR"
            and issue.code
            != "PDF_DOCUMENT_NOT_READY"
            for issue
            in document_set_validation.issues
        )

        documents_supported_for_analysis = all(
            (
                document.ready_for_semantic_analysis
                or pdf_document_should_attempt_automatic_vision(
                    document
                )
            )
            for document in pdf_documents
        )

        document_input_ready = (
            bool(pdf_documents)
            and not blocking_document_set_issue
            and documents_supported_for_analysis
        )

        pdf_documents_fully_prepared = (
            document_input_ready
            and all(
                document.ready_for_semantic_analysis
                and not
                pdf_document_should_attempt_automatic_vision(
                    document
                )
                for document in pdf_documents
            )
        )

        if pdf_documents_fully_prepared:
            documents = [
                build_semantic_document(
                    document
                )
                for document in pdf_documents
                if document.role in {
                    "requirement",
                    "verification",
                }
            ]

            feasible_pdf_documents = [
                document
                for document in pdf_documents
                if document.role == "feasible"
            ]

            feasible_pdf_document = (
                feasible_pdf_documents[0]
                if len(feasible_pdf_documents) == 1
                else None
            )

            source_pdfs = {
                (
                    document.role,
                    document.content_sha256,
                ): document
                for document in pdf_documents
            }

        elif document_input_ready:
            st.info(
                "Source registered. Select Analyze Document "
                "to complete Vision recovery and Automatic "
                "Evidence Discovery."
            )

    else:
        st.info(
            "공학 PDF 한 개를 업로드하면 "
            "문서 근거 탐색을 시작합니다."
        )



semantic_documents_signature = (
    build_semantic_documents_signature(
        documents
    )
    if documents
    else None
)

feasible_document_sha256 = (
    build_pdf_source_set_signature(
        feasible_pdf_documents
    )
)

current_signature = (
    hashlib.sha256(
        (
            (pdf_input_signature or "")
            + "|"
            + (semantic_documents_signature or "")
            + "|"
            + (feasible_document_sha256 or "")
        ).encode("utf-8")
    ).hexdigest()
    if (
        semantic_documents_signature
        or feasible_document_sha256
    )
    else None
)


if st.button(
    "자동 Evidence Discovery 시작 (Analyze Document)",
    type="primary",
):
    if not document_input_ready:
        st.warning(
            "분석할 Engineering Source를 등록해 주세요."
        )

    else:
        try:
            if input_mode == "PDF Upload":
                def vision_page_extractor(
                    pdf_bytes,
                    page_number,
                ):
                    from src.ai.constraint_parser import (
                        client as vision_client,
                    )

                    return extract_pdf_page_with_vision(
                        pdf_bytes,
                        page_number=page_number,
                        client=vision_client,
                    )

                if any(
                    pdf_document_should_attempt_automatic_vision(
                        document
                    )
                    for document in pdf_documents
                ):
                    with st.spinner(
                        "스캔 페이지를 Vision AI로 "
                        "분석하고 있습니다..."
                    ):
                        prepared_pdf_documents = list(
                            prepare_pdf_document_views_with_vision(
                                pdf_documents,
                                vision_page_extractor=(
                                    vision_page_extractor
                                ),
                            )
                        )
                    if not all(
                        document.ready_for_semantic_analysis
                        for document
                        in prepared_pdf_documents
                    ):
                        raise RuntimeError(
                            "Vision recovery did not produce "
                            "usable text for every required PDF."
                        )

                    pdf_documents = (
                        prepared_pdf_documents
                    )

                    cached_documents = dict(
                        st.session_state[
                            "vision_prepared_pdf_documents"
                        ]
                    )

                    for document in pdf_documents:
                        cache_key = (
                            document.role
                            + ":"
                            + document.content_sha256
                        )
                        cached_documents[
                            cache_key
                        ] = document

                    st.session_state[
                        "vision_prepared_pdf_documents"
                    ] = cached_documents

                    physical_cache = dict(
                        st.session_state[
                            "vision_prepared_physical_sources"
                        ]
                    )

                    for document in pdf_documents:
                        current_cached = physical_cache.get(
                            document.content_sha256
                        )

                        if (
                            current_cached is None
                            or len(
                                document.vision_processed_page_numbers
                            )
                            > len(
                                current_cached.vision_processed_page_numbers
                            )
                        ):
                            physical_cache[
                                document.content_sha256
                            ] = document

                    st.session_state[
                        "vision_prepared_physical_sources"
                    ] = physical_cache

                    st.session_state[
                        "vision_prepared_pdf_signature"
                    ] = pdf_input_signature

                prepared_validation = (
                    validate_pdf_document_set(
                        pdf_documents
                    )
                )

                if not prepared_validation.valid:
                    raise RuntimeError(
                        "Prepared PDF document set "
                        "failed validation."
                    )

                documents = [
                    build_semantic_document(
                        document
                    )
                    for document in pdf_documents
                    if document.role in {
                        "requirement",
                        "verification",
                    }
                ]

                feasible_pdf_documents = [
                    document
                    for document in pdf_documents
                    if document.role == "feasible"
                ]

                feasible_pdf_document = (
                    feasible_pdf_documents[0]
                    if len(feasible_pdf_documents) == 1
                    else None
                )

                source_pdfs = {
                    (
                        document.role,
                        document.content_sha256,
                    ): document
                    for document
                    in pdf_documents
                }

                semantic_documents_signature = (
                    build_semantic_documents_signature(
                        documents
                    )
                )

                feasible_document_sha256 = (
    build_pdf_source_set_signature(
        feasible_pdf_documents
    )
)

                current_signature = (
                    hashlib.sha256(
                        (
                            (pdf_input_signature or "")
                            + "|"
                            + semantic_documents_signature
                            + "|"
                            + (
                                feasible_document_sha256
                                or ""
                            )
                        ).encode("utf-8")
                    ).hexdigest()
                )

            with st.spinner(
                "문서에서 공학 의미 (Engineering Semantics)를 추출하고 있습니다..."
            ):
                discovery_started = perf_counter()

                from concurrent.futures import (
                    ThreadPoolExecutor,
                )

                def run_semantic_extraction():
                    started = perf_counter()

                    result = analyze_semantic_documents(
                        documents,
                        max_workers=2,
                    )

                    return (
                        result,
                        perf_counter() - started,
                    )

                def run_feasible_extraction():
                    started = perf_counter()

                    result = (
                        analyze_feasible_evidence_documents(
                            feasible_pdf_documents,
                            max_workers=2,
                        )
                        if feasible_pdf_documents
                        else None
                    )

                    return (
                        result,
                        perf_counter() - started,
                    )

                with ThreadPoolExecutor(
                    max_workers=2
                ) as executor:
                    semantic_future = executor.submit(
                        run_semantic_extraction
                    )

                    feasible_future = executor.submit(
                        run_feasible_extraction
                    )

                    (
                        analysis,
                        semantic_elapsed,
                    ) = semantic_future.result()

                    (
                        feasible_analysis,
                        feasible_elapsed,
                    ) = feasible_future.result()

                print(
                    "[DISCOVERY] R/V extraction: "
                    f"{semantic_elapsed:.2f}s | "
                    f"candidates={len(analysis.candidates)}",
                    flush=True,
                )

                print(
                    "[DISCOVERY] F extraction: "
                    f"{feasible_elapsed:.2f}s | "
                    "candidates="
                    + str(
                        len(feasible_analysis.candidates)
                        if feasible_analysis is not None
                        else 0
                    ),
                    flush=True,
                )

                strict_adapter_accepted_count = sum(
                    1
                    for candidate
                    in analysis.candidates
                    if candidate.adapter_accepted
                )

                source_location_ready_count = sum(
                    1
                    for candidate
                    in analysis.candidates
                    if candidate.source_location_ready
                )

                grounding_eligibility_by_candidate = {
                    candidate.candidate_id:
                    semantic_candidate_grounding_eligibility(
                        candidate
                    )
                    for candidate
                    in analysis.candidates
                }

                grounding_eligible_count = sum(
                    1
                    for eligible, _
                    in grounding_eligibility_by_candidate.values()
                    if eligible
                )

                grounding_source_ready_count = sum(
                    1
                    for candidate
                    in analysis.candidates
                    if (
                        grounding_eligibility_by_candidate[
                            candidate.candidate_id
                        ][0]
                        and candidate.source_location_ready
                    )
                )

                precheck_blocked_count = (
                    len(analysis.candidates)
                    - grounding_eligible_count
                )

                def run_semantic_grounding():
                    started = perf_counter()

                    result = ground_semantic_candidates(
                        analysis,
                        max_workers=2,
                    )

                    return (
                        result,
                        perf_counter() - started,
                    )

                def run_feasible_grounding():
                    started = perf_counter()

                    result = (
                        ground_feasible_candidates(
                            feasible_analysis,
                            max_workers=2,
                        )
                        if feasible_analysis is not None
                        else {}
                    )

                    return (
                        result,
                        perf_counter() - started,
                    )

                with ThreadPoolExecutor(
                    max_workers=2
                ) as executor:
                    semantic_grounding_future = (
                        executor.submit(
                            run_semantic_grounding
                        )
                    )

                    feasible_grounding_future = (
                        executor.submit(
                            run_feasible_grounding
                        )
                    )

                    (
                        semantic_role_grounding,
                        semantic_grounding_elapsed,
                    ) = (
                        semantic_grounding_future.result()
                    )

                    (
                        feasible_role_grounding,
                        feasible_grounding_elapsed,
                    ) = (
                        feasible_grounding_future.result()
                    )

                discovery_total = (
                    perf_counter()
                    - discovery_started
                )

                print(
                    "[DISCOVERY] R/V grounding: "
                    f"{semantic_grounding_elapsed:.2f}s | "
                    f"candidates="
                    f"{len(semantic_role_grounding)} | "
                    "strict-adapter-accepted="
                    f"{strict_adapter_accepted_count} | "
                    "source-ready="
                    f"{source_location_ready_count} | "
                    "grounding-eligible="
                    f"{grounding_eligible_count} | "
                    "grounding+source-ready="
                    f"{grounding_source_ready_count} | "
                    "precheck-blocked="
                    f"{precheck_blocked_count}",
                    flush=True,
                )

                print(
                    "[DISCOVERY] F grounding: "
                    f"{feasible_grounding_elapsed:.2f}s | "
                    f"candidates="
                    f"{len(feasible_role_grounding)}",
                    flush=True,
                )

                print(
                    "[DISCOVERY] TOTAL: "
                    f"{discovery_total:.2f}s",
                    flush=True,
                )

                st.caption(
                    "분석 시간 · "
                    f"R/V 추출 {semantic_elapsed:.1f}s · "
                    f"F 추출 {feasible_elapsed:.1f}s · "
                    "R/V Grounding "
                    f"{semantic_grounding_elapsed:.1f}s · "
                    "F Grounding "
                    f"{feasible_grounding_elapsed:.1f}s · "
                    f"총 {discovery_total:.1f}s"
                )

            st.session_state[
                "verification_result"
            ] = None

            st.session_state[
                "verification_review_state"
            ] = None

            st.session_state[
                "prepared_semantic_review_signature"
            ] = None

            st.session_state[
                "prepared_feasible_review_signature"
            ] = None

            st.session_state[
                "semantic_analysis"
            ] = analysis

            st.session_state[
                "feasible_analysis"
            ] = feasible_analysis

            st.session_state[
                "semantic_role_grounding"
            ] = semantic_role_grounding

            st.session_state[
                "feasible_role_grounding"
            ] = feasible_role_grounding

            st.session_state[
                "semantic_approved_candidate_ids"
            ] = []

            st.session_state[
                "feasible_approved_candidate_ids"
            ] = []

            st.session_state[
                "analysis_signature"
            ] = current_signature

            st.session_state[
                "mapped_analysis"
            ] = None

            st.session_state[
                "base_case"
            ] = None

            st.session_state[
                "prepared_feasible_evidence_traces"
            ] = []

        except Exception as exc:
            st.error(
                f"Analysis error: {exc}"
            )


analysis = st.session_state[
    "semantic_analysis"
]

feasible_analysis = st.session_state[
    "feasible_analysis"
]

semantic_role_grounding = st.session_state[
    "semantic_role_grounding"
]

feasible_role_grounding = st.session_state[
    "feasible_role_grounding"
]


# =========================================================
# STEP 2 — SEMANTIC REVIEW
# =========================================================

if analysis is not None:
    st.divider()

    render_section_header(
        "STAGE 02",
        "Evidence Discovery",
        (
            "Stage 01의 동일한 원본 source를 여러 "
            "engineering lens로 분석한 Candidate와 "
            "source 원문 추적를 제시합니다."
        ),
    )

    render_soft_note(
        (
            "AI는 원본 source에서 engineering evidence "
            "candidate를 제안하는 Semantic Bridge 역할만 "
            "수행합니다. Proposed Role은 Role Grounding과 "
            "Engineer Review를 통과하기 전에는 "
            "Formal Model에 반영되지 않습니다."
        )
    )

    analysis_is_current = (
        st.session_state[
            "analysis_signature"
        ]
        == current_signature
    )

    if not analysis_is_current:
        st.warning(
            "입력 문서가 분석 이후 변경되었습니다. "
            "Candidate를 사용하기 전에 "
            "Analyze Documents를 다시 실행해 주세요."
        )

    with st.expander(
        "표시 옵션",
        expanded=False,
    ):
        review_view_mode = st.radio(
            "후보 표시 방식",
            (
                "Compact",
                "Detailed",
            ),
            horizontal=True,
            format_func=(
                lambda mode: {
                    "Compact": "요약 보기",
                    "Detailed": "전체 펼치기",
                }[mode]
            ),
            key="candidate_review_view_mode",
        )

        st.caption(
            "요약 보기에서는 후보 제목을 먼저 확인하고 "
            "필요한 항목만 펼칩니다."
        )

    candidate_details_expanded = (
        review_view_mode == "Detailed"
    )

    feasible_candidate_count = (
        len(feasible_analysis.candidates)
        if feasible_analysis is not None
        else 0
    )

    requirement_candidate_count = sum(
        candidate.role == "requirement"
        for candidate in analysis.candidates
    )

    verification_candidate_count = sum(
        candidate.role == "verification"
        for candidate in analysis.candidates
    )

    guided_semantic_selected = set(
        st.session_state.get(
            "semantic_approved_candidate_ids",
            [],
        )
    )

    guided_feasible_selected = set(
        st.session_state.get(
            "feasible_approved_candidate_ids",
            [],
        )
    )

    guided_requirement_count = sum(
        candidate.candidate_id
        in guided_semantic_selected
        and candidate.role == "requirement"
        for candidate in analysis.candidates
    )

    guided_verification_count = sum(
        candidate.candidate_id
        in guided_semantic_selected
        and candidate.role == "verification"
        for candidate in analysis.candidates
    )

    guided_feasible_count = (
        sum(
            candidate.candidate_id
            in guided_feasible_selected
            for candidate
            in feasible_analysis.candidates
        )
        if feasible_analysis is not None
        else 0
    )

    guided_requirement_candidate = next(
        (
            candidate
            for candidate in analysis.candidates
            if (
                candidate.role == "requirement"
                and candidate.candidate_id
                in guided_semantic_selected
            )
        ),
        None,
    )

    guided_verification_candidate = next(
        (
            candidate
            for candidate in analysis.candidates
            if (
                candidate.role == "verification"
                and candidate.candidate_id
                in guided_semantic_selected
            )
        ),
        None,
    )

    guided_feasible_candidate = None
    if feasible_analysis is not None:
        guided_feasible_candidate = next(
            (
                candidate
                for candidate
                in feasible_analysis.candidates
                if candidate.candidate_id
                in guided_feasible_selected
            ),
            None,
        )

    st.markdown(
        "### Evidence Set Builder"
    )

    st.caption(
        "Requirement → Verification → 실제 관측 근거 순서로 "
        "하나의 검증 근거 세트를 구성합니다. "
        "현재 단계에 필요한 후보만 기본 화면에 표시합니다."
    )

    builder_r, builder_v, builder_f = st.columns(3)

    with builder_r:
        st.markdown(
            "**① 설계 요구조건 · Requirement**"
        )

        if guided_requirement_candidate is not None:
            st.success("선택 완료 ✓")

            st.caption(
                format_candidate_review_summary(
                    guided_requirement_candidate.extraction
                )
            )

            requirement_change = st.button(
                "설계 요구조건 변경",
                key="builder_change_requirement",
                use_container_width=True,
            )

            if requirement_change:
                st.session_state[
                    "semantic_approved_candidate_ids"
                ] = []

                st.session_state[
                    "feasible_approved_candidate_ids"
                ] = []

                st.session_state[
                    "engineer_variable_mapping_confirmed"
                ] = False

                st.session_state[
                    "engineer_feasible_group_override"
                ] = {}

                st.session_state[
                    "mapped_analysis"
                ] = None

                st.session_state[
                    "base_case"
                ] = None

                st.session_state[
                    "verification_result"
                ] = None

                st.session_state[
                    "verification_review_state"
                ] = None

                st.rerun()

        else:
            st.info("현재 선택 단계")

            st.caption(
                "제품이나 시스템이 반드시 만족해야 하는 "
                "설계·기술 기준을 선택합니다."
            )

    with builder_v:
        st.markdown(
            "**② 검사 / 합격 기준 · Verification**"
        )

        if guided_verification_candidate is not None:
            st.success("선택 완료 ✓")

            st.caption(
                format_candidate_review_summary(
                    guided_verification_candidate.extraction
                )
            )

            verification_change = st.button(
                "Verification 변경",
                key="builder_change_verification",
                use_container_width=True,
            )

            if verification_change:
                requirement_ids = [
                    candidate.candidate_id
                    for candidate in analysis.candidates
                    if (
                        candidate.role == "requirement"
                        and candidate.candidate_id
                        in guided_semantic_selected
                    )
                ]

                st.session_state[
                    "semantic_approved_candidate_ids"
                ] = requirement_ids

                st.session_state[
                    "feasible_approved_candidate_ids"
                ] = []

                st.session_state[
                    "engineer_variable_mapping_confirmed"
                ] = False

                st.session_state[
                    "engineer_feasible_group_override"
                ] = {}

                st.session_state[
                    "mapped_analysis"
                ] = None

                st.session_state[
                    "base_case"
                ] = None

                st.session_state[
                    "verification_result"
                ] = None

                st.session_state[
                    "verification_review_state"
                ] = None

                st.rerun()

        elif guided_requirement_candidate is None:
            st.caption(
                "Requirement 선택 후 진행"
            )

        else:
            st.info("현재 선택 단계")

            st.caption(
                "선택한 Requirement와 연결되는 "
                "실제 검사·합격 기준을 검토합니다."
            )

    with builder_f:
        st.markdown(
            "**③ 실제 관측 근거 · 실제 관측 근거**"
        )

        if guided_feasible_candidate is not None:
            st.success("선택 완료 ✓")

            st.caption(
                format_candidate_review_summary(
                    guided_feasible_candidate.extraction
                )
            )

            feasible_change = st.button(
                "실제 관측 근거 변경",
                key="builder_change_feasible",
                use_container_width=True,
            )

            if feasible_change:
                st.session_state[
                    "feasible_approved_candidate_ids"
                ] = []

                st.session_state[
                    "engineer_variable_mapping_confirmed"
                ] = False

                st.session_state[
                    "engineer_feasible_group_override"
                ] = {}

                st.session_state[
                    "mapped_analysis"
                ] = None

                st.session_state[
                    "base_case"
                ] = None

                st.session_state[
                    "verification_result"
                ] = None

                st.session_state[
                    "verification_review_state"
                ] = None

                st.rerun()

        elif (
            guided_requirement_candidate is None
            or guided_verification_candidate is None
        ):
            st.caption(
                "Requirement / Verification 선택 후 진행"
            )

        else:
            st.info("현재 선택 단계")

            st.caption(
                "현재 R / V와 연결되는 실제 측정·시험 "
                "근거를 검토합니다."
            )


    # -----------------------------------------------------
    # Sequential wizard focus
    # -----------------------------------------------------

    if guided_requirement_candidate is None:
        candidate_category = "Requirement"

        render_review_focus(
            "① Requirement 선택",
            (
                "제품이나 시스템이 반드시 만족해야 하는 "
                "설계·기술 요구조건 하나를 선택합니다."
            ),
        )

    elif guided_verification_candidate is None:
        candidate_category = "Verification"

        render_review_focus(
            "② Verification 선택",
            (
                "선택한 Requirement와 연결되는 검사·시험의 "
                "합격 기준을 검토합니다."
            ),
        )

    elif guided_feasible_candidate is None:
        candidate_category = "실제 관측 근거"

        render_review_focus(
            "③ 실제 관측 근거 선택",
            (
                "현재 Requirement / Verification과 연결되는 "
                "실제 측정·시험 근거를 검토합니다."
            ),
        )

    else:
        candidate_category = None

        render_review_focus(
            "Evidence Set Compatibility",
            (
                "R / V / F 선택이 완료되었습니다. "
                "아래에서 하나의 Formal Model로 연결 가능한지 "
                "최종 정합성을 확인합니다."
            ),
        )

        st.success(
            "Evidence Set 선택 완료 ✓ · "
            "이제 Compatibility 검토로 이동합니다."
        )


    if candidate_category is not None:
        stage_label = {
            "Requirement": "Requirement 후보",
            "Verification": "Verification 후보",
            "실제 관측 근거": "실제 관측 근거 후보",
        }[
            candidate_category
        ]

        st.markdown(
            "#### " + stage_label
        )

        if candidate_category == "Requirement":
            st.caption(
                "역할 근거가 확인된 설계·기술 요구조건 후보를 "
                "검토합니다."
            )

        elif candidate_category == "Verification":
            st.caption(
                "현재 Requirement와의 연결 상태에 따라 "
                "후보가 정리됩니다."
            )

        else:
            st.caption(
                "현재 Requirement / Verification과의 연결 상태에 "
                "따라 후보가 정리됩니다."
            )

        st.caption(
            "특정 Min / Max 숫자값을 기준으로 후보를 "
            "자동 선택하거나 정답 순위를 만들지 않습니다."
        )

    # -----------------------------------------------------
    # Feasible Evidence Candidate Review
    # -----------------------------------------------------

    feasible_approved_candidate_ids = list(
        st.session_state.get(
            "feasible_approved_candidate_ids",
            [],
        )
    )

    if candidate_category == "실제 관측 근거":
        if feasible_analysis is not None:
            st.subheader(
                "관측 근거 추출 결과 "
                "(실제 관측 근거 Candidates)"
            )

            st.caption(
                "AI는 후보만 제안합니다. PDF 원문 위치와 의미를 "
                "확인한 뒤 Engineer Approval이 있어야 다음 단계에서 "
                "실제 가능한 범위(F) 입력 후보로 사용할 수 있습니다."
            )

            feasible_analysis = deepcopy(
                feasible_analysis
            )

            feasible_status_counts = {
                "SUPPORTED": 0,
                "REVIEW REQUIRED": 0,
                "REJECTED": 0,
                "NOT ESTABLISHED": 0,
            }

            for feasible_candidate in feasible_analysis.candidates:
                status = grounding_display_status(
                    feasible_role_grounding.get(
                        feasible_candidate.candidate_id
                    )
                )
                feasible_status_counts[status] += 1

            st.caption(
                "후보 현황 · 전체 "
                f"Total {len(feasible_analysis.candidates)} · "
                f"SUPPORTED {feasible_status_counts['SUPPORTED']} · "
                f"REVIEW REQUIRED "
                f"{feasible_status_counts['REVIEW REQUIRED']} · "
                f"REJECTED {feasible_status_counts['REJECTED']}"
            )

            feasible_status_filter = st.selectbox(
                "후보 보기",
                (
                    "SUPPORTED",
                    "REVIEW REQUIRED",
                    "REJECTED",
                    "전체",
                ),
                format_func=lambda value: {
                    "SUPPORTED": "역할 근거 확인됨",
                    "REVIEW REQUIRED": "추가 확인 필요",
                    "REJECTED": "현재 역할과 맞지 않음",
                    "전체": "전체 후보 보기",
                }[value],
                key="feasible_grounding_status_filter",
            )

            st.caption(
                "표시 필터는 보기만 바꾸며 후보, 근거, "
                "Role Grounding 판정은 변경하지 않습니다."
            )

            feasible_search_query = st.text_input(
                "후보 검색",
                placeholder=(
                    "예: hardness, HRC, pressure, source file name"
                ),
                key="feasible_candidate_search",
            )

            visible_feasible_candidates = [
                candidate
                for candidate in feasible_analysis.candidates
                if (
                    feasible_status_filter == "전체"
                    or grounding_display_status(
                        feasible_role_grounding.get(
                            candidate.candidate_id
                        )
                    )
                    == feasible_status_filter
                )
            ]

            normalized_feasible_search = (
                feasible_search_query
                .strip()
                .lower()
            )

            if normalized_feasible_search:
                visible_feasible_candidates = [
                    candidate
                    for candidate
                    in visible_feasible_candidates
                    if normalized_feasible_search
                    in (
                        format_candidate_review_summary(
                            candidate.extraction
                        )
                        + " "
                        + str(
                            candidate.source_name
                            or ""
                        )
                    ).lower()
                ]

            feasible_connection_counts = {
                "DIRECT": 0,
                "REVIEW": 0,
                "MISMATCH": 0,
                "NO_CONTEXT": 0,
            }

            feasible_connection_anchors = (
                [
                    guided_requirement_candidate,
                    guided_verification_candidate,
                ]
                if (
                    guided_requirement_candidate
                    is not None
                    and guided_verification_candidate
                    is not None
                )
                else []
            )

            for candidate in visible_feasible_candidates:
                state = candidate_connection_state(
                    candidate,
                    feasible_connection_anchors,
                )
                feasible_connection_counts[state] += 1

            if feasible_connection_anchors:
                visible_feasible_candidates.sort(
                    key=lambda candidate: (
                        connection_state_priority(
                            candidate_connection_state(
                                candidate,
                                feasible_connection_anchors,
                            )
                        ),
                        format_candidate_review_summary(
                            candidate.extraction
                        ).lower(),
                    )
                )

                st.caption(
                    "현재 R / V와의 연결 안내 · "
                    f"직접 연결 {feasible_connection_counts['DIRECT']} · "
                    f"Mapping 검토 {feasible_connection_counts['REVIEW']} · "
                    "바로 연결되지 않음 "
                    f"{feasible_connection_counts['MISMATCH']}"
                )

            selected_feasible_count = sum(
                candidate.candidate_id
                in feasible_approved_candidate_ids
                for candidate
                in feasible_analysis.candidates
            )

            st.caption(
                "표시 중 · "
                f"{len(visible_feasible_candidates)} / "
                f"{len(feasible_analysis.candidates)}"
                "  ·  Formal Model 선택 · "
                f"{selected_feasible_count}"
            )

            if not feasible_analysis.candidates:
                st.info(
                    "업로드한 source에서 지원 가능한 "
                    "실제 관측 근거 후보를 찾지 못했습니다."
                )

            for feasible_index, feasible_candidate in enumerate(
                visible_feasible_candidates,
                start=1,
            ):
                extraction = (
                    feasible_candidate.extraction
                )

                feasible_grounding = (
                    feasible_role_grounding.get(
                        feasible_candidate.candidate_id
                    )
                )

                feasible_grounding_supported = bool(
                    feasible_grounding is not None
                    and feasible_grounding.supported
                )

                feasible_candidate_title = (
                    build_candidate_review_title(
                        proposed_role="실제 관측 근거",
                        extraction=extraction,
                        grounding=feasible_grounding,
                        source_name=(
                            feasible_candidate.source_name
                        ),
                        approved=(
                            feasible_candidate.candidate_id
                            in feasible_approved_candidate_ids
                        ),
                    )
                )

                if (
                    guided_requirement_candidate is not None
                    and guided_verification_candidate is not None
                ):
                    feasible_connection_state = (
                        candidate_connection_state(
                            feasible_candidate,
                            [
                                guided_requirement_candidate,
                                guided_verification_candidate,
                            ],
                        )
                    )

                    feasible_candidate_title = (
                        "["
                        + connection_state_label(
                            feasible_connection_state
                        )
                        + "] "
                        + feasible_candidate_title
                    )

                with st.expander(
                    feasible_candidate_title,
                    expanded=candidate_details_expanded,
                ):
                    st.caption(
                        "PROPOSED ROLE · 실제 관측 근거"
                    )
                    source_column, data_column = (
                        st.columns(2)
                    )

                    feasible_preview_page = (
                        feasible_candidate.source_page
                    )

                    with source_column:
                        st.markdown(
                            "#### 원문 근거 (Source Evidence)"
                        )

                        st.caption(
                            feasible_candidate.source_name
                            + " · Block "
                            + str(
                                feasible_candidate.source_block_id
                                or "—"
                            )
                        )

                        if (
                            feasible_candidate.source_location_status
                            == "SOURCE_LOCATION_AMBIGUOUS"
                        ):
                            st.warning(
                                "Source Location Review Required"
                            )

                            selected_page = st.selectbox(
                                "Operating Evidence 원문 페이지 선택",
                                feasible_candidate
                                .source_location_candidates,
                                format_func=(
                                    lambda page:
                                    f"Page {page}"
                                ),
                                key=(
                                    "feasible_source_location_page_"
                                    + safe_key(
                                        feasible_candidate
                                        .candidate_id
                                    )
                                ),
                            )

                            location_confirmed = (
                                st.checkbox(
                                    "이 원문 페이지를 확인합니다.",
                                    key=(
                                        "feasible_source_location_confirm_"
                                        + safe_key(
                                            feasible_candidate
                                            .candidate_id
                                        )
                                    ),
                                )
                            )

                            feasible_preview_page = (
                                selected_page
                            )

                            if location_confirmed:
                                try:
                                    feasible_candidate = (
                                        confirm_ambiguous_feasible_source_location(
                                            feasible_candidate,
                                            selected_page=(
                                                selected_page
                                            ),
                                            confirmed=True,
                                        )
                                    )

                                    feasible_analysis.candidates[
                                        feasible_index - 1
                                    ] = feasible_candidate

                                    st.success(
                                        "Operating Evidence source "
                                        "page confirmed."
                                    )

                                except ValueError as exc:
                                    st.error(
                                        str(exc)
                                    )

                        elif (
                            feasible_candidate
                            .source_location_status
                            in {
                                "SOURCE_LOCATION_UNRESOLVED",
                                "SOURCE_LOCATION_MISMATCH",
                            }
                        ):
                            st.error(
                                "Source location blocked · "
                                + format_code_label(
                                    feasible_candidate
                                    .source_location_status
                                )
                            )

                        elif feasible_candidate.source_pages:
                            st.success(
                                "Source location · "
                                + ", ".join(
                                    f"Page {page}"
                                    for page
                                    in feasible_candidate
                                    .source_pages
                                )
                            )

                        feasible_pdf = (
                            source_pdfs.get(
                                (
                                    "feasible",
                                    feasible_candidate
                                    .source_sha256,
                                )
                            )
                        )

                        if (
                            feasible_pdf is not None
                            and feasible_preview_page
                            is not None
                        ):
                            with st.expander(
                                "원본 Operating Evidence "
                                "PDF 페이지 보기"
                            ):
                                try:
                                    st.pdf(
                                        build_pdf_page_preview(
                                            feasible_pdf,
                                            feasible_preview_page,
                                        ),
                                        height=360,
                                        key=(
                                            "feasible_pdf_preview_"
                                            + safe_key(
                                                feasible_candidate
                                                .candidate_id
                                                + ":"
                                                + str(
                                                    feasible_preview_page
                                                )
                                            )
                                        ),
                                    )
                                except Exception as exc:
                                    st.error(
                                        "PDF page preview failed: "
                                        + str(exc)
                                    )

                        with st.expander(
                            "원문 추적 정보 (Advanced)"
                        ):
                            st.caption(
                                "SHA-256 · "
                                + feasible_candidate
                                .source_sha256
                            )
                            st.caption(
                                "Candidate ID · "
                                + feasible_candidate
                                .candidate_id
                            )
                            st.write(
                                feasible_candidate
                                .source_text
                            )

                    with data_column:
                        st.markdown(
                            "#### AI 추출 후보 (AI Extracted Candidate)"
                        )

                        st.metric(
                            "Engineering Variable",
                            str(
                                extraction.get(
                                    "variable"
                                )
                                or "—"
                            ),
                        )

                        range_left, range_right = (
                            st.columns(2)
                        )

                        range_left.metric(
                            "Feasible Min",
                            str(
                                extraction.get(
                                    "min"
                                )
                                or "—"
                            ),
                        )

                        range_right.metric(
                            "Feasible Max",
                            str(
                                extraction.get(
                                    "max"
                                )
                                or "—"
                            ),
                        )

                        st.caption(
                            "Unit · "
                            + str(
                                extraction.get(
                                    "unit"
                                )
                                or "—"
                            )
                        )

                        st.caption(
                            "Evidence Type · "
                            + str(
                                extraction.get(
                                    "evidence_type"
                                )
                                or "—"
                            )
                        )

                        needs_review = bool(
                            extraction.get(
                                "needs_review",
                                True,
                            )
                        )

                        if needs_review:
                            st.warning(
                                "AI extraction marked this "
                                "candidate as review-required."
                            )

                            review_reason = (
                                extraction.get(
                                    "review_reason"
                                )
                            )

                            if review_reason:
                                st.caption(
                                    str(
                                        review_reason
                                    )
                                )

                        st.markdown(
                            "#### 역할 근거 (Role Evidence)"
                        )

                        if feasible_grounding is None:
                            st.warning(
                                "역할 근거 · 아직 판정되지 않음"
                            )
                        elif feasible_grounding.supported:
                            st.success(
                                "역할 근거 · 확인됨 ✓"
                            )
                        elif (
                            feasible_grounding.status
                            == "REJECTED"
                        ):
                            st.error(
                                "역할 근거 · 현재 역할과 맞지 않음"
                            )
                        else:
                            st.warning(
                                "역할 근거 · 추가 확인 필요"
                            )

                        if feasible_grounding is not None:
                            st.caption(
                                "Basis · "
                                + feasible_grounding.basis_type
                            )
                            st.caption(
                                feasible_grounding.explanation
                            )

                            if (
                                feasible_grounding
                                .supporting_text
                            ):
                                st.code(
                                    feasible_grounding
                                    .supporting_text,
                                    language=None,
                                )

                        eligible_for_approval = (
                            analysis_is_current
                            and feasible_candidate
                            .source_location_ready
                            and not needs_review
                            and feasible_grounding_supported
                        )

                        feasible_is_selected = (
                            feasible_candidate.candidate_id
                            in feasible_approved_candidate_ids
                        )

                        st.markdown(
                            "#### Selection Readiness"
                        )

                        if feasible_is_selected:
                            st.success(
                                "Selection Readiness · "
                                "이번 검증에 선택됨 ✓"
                            )

                            st.caption(
                                "이 원문 근거는 이번 Formal Model의 "
                                "실제 관측 근거로 선택되어 있습니다."
                            )

                            revoke_feasible = st.button(
                                "선택 취소",
                                key=(
                                    "feasible_unselect_button_"
                                    + safe_key(
                                        feasible_candidate.candidate_id
                                    )
                                ),
                            )

                            if revoke_feasible:
                                feasible_approved_candidate_ids.remove(
                                    feasible_candidate.candidate_id
                                )

                                st.session_state[
                                    "feasible_approved_candidate_ids"
                                ] = list(
                                    feasible_approved_candidate_ids
                                )

                                st.rerun()

                        elif eligible_for_approval:
                            st.success(
                                "Selection Readiness · 선택 가능 ✓"
                            )

                            st.caption(
                                "원문 위치, 역할 근거, 수치·단위와 "
                                "review gate가 준비되었습니다. "
                                "원문을 확인한 뒤 이번 검증에 사용할지 "
                                "Engineer가 결정합니다."
                            )

                            select_feasible = st.button(
                                "이 근거를 실제 관측 근거로 사용",
                                type="primary",
                                key=(
                                    "feasible_select_button_"
                                    + safe_key(
                                        feasible_candidate.candidate_id
                                    )
                                ),
                            )

                            if select_feasible:
                                # Guided Review uses exactly one
                                # 실제 관측 근거 candidate.
                                feasible_approved_candidate_ids = [
                                    feasible_candidate.candidate_id
                                ]

                                st.session_state[
                                    "feasible_approved_candidate_ids"
                                ] = list(
                                    feasible_approved_candidate_ids
                                )

                                st.rerun()

                        else:
                            st.warning(
                                "Selection Readiness · 추가 검토 필요"
                            )

                            if not analysis_is_current:
                                st.caption(
                                    "분석 이후 source가 변경되었습니다. "
                                    "문서를 다시 분석해야 합니다."
                                )
                            elif not (
                                feasible_candidate
                                .source_location_ready
                            ):
                                st.caption(
                                    "원문 위치 확인이 아직 완료되지 않았습니다."
                                )
                            elif needs_review:
                                st.caption(
                                    "추출된 값 또는 조건에 unresolved "
                                    "review가 남아 있습니다."
                                )
                            elif not feasible_grounding_supported:
                                st.caption(
                                    "현재 역할의 근거가 아직 확정되지 않았습니다."
                                )
                            else:
                                st.caption(
                                    "선택에 필요한 review gate가 "
                                    "아직 완료되지 않았습니다."
                                )


            st.session_state[
                "feasible_analysis"
            ] = feasible_analysis

            st.session_state[
                "feasible_approved_candidate_ids"
            ] = feasible_approved_candidate_ids

            if feasible_approved_candidate_ids:
                st.success(
                    "선택된 실제 관측 근거 후보 · "
                    + str(
                        len(
                            feasible_approved_candidate_ids
                        )
                    )
                )

            st.caption(
                "이번 단계에서는 승인된 F 후보를 "
                "EngineeringCase나 Solver에 아직 적용하지 않습니다."
            )

            st.divider()

    current_feasible_review_signature = (
        build_feasible_review_signature(
            feasible_analysis,
            feasible_approved_candidate_ids,
        )
    )

    approved_candidate_ids = list(
        st.session_state.get(
            "semantic_approved_candidate_ids",
            [],
        )
    )
    analysis = deepcopy(analysis)

    if candidate_category in (
        "Requirement",
        "Verification",
    ):
        semantic_role_filter = candidate_category

        semantic_role_key = (
            "requirement"
            if candidate_category == "Requirement"
            else "verification"
        )

        selected_semantic_candidates = [
            candidate
            for candidate in analysis.candidates
            if candidate.role == semantic_role_key
        ]

        semantic_status_counts = {
            "SUPPORTED": 0,
            "REVIEW REQUIRED": 0,
            "REJECTED": 0,
            "NOT ESTABLISHED": 0,
        }

        for candidate in selected_semantic_candidates:
            status = grounding_display_status(
                semantic_role_grounding.get(
                    candidate.candidate_id
                )
            )
            semantic_status_counts[status] += 1

        semantic_category_title = {
            "Requirement": (
                "① 설계 요구조건 후보 "
                "(Requirement Candidates)"
            ),
            "Verification": (
                "② 검사 / 합격 기준 후보 "
                "(Verification Criterion Candidates)"
            ),
        }[
            candidate_category
        ]

        st.markdown(
            "### " + semantic_category_title
        )

        if candidate_category == "Requirement":
            st.caption(
                "제품이나 시스템이 실제로 만족해야 하는 "
                "설계·기술 기준 후보입니다. 원문의 적용 대상, "
                "수치, 단위를 확인하세요."
            )
        else:
            st.caption(
                "실제 검사·시험에서 통과 여부를 판단하는 "
                "기준 후보입니다. 단순 설계값이나 operating "
                "limit가 아닌 실제 acceptance criterion인지 "
                "확인하세요."
            )

        st.caption(
            "후보 현황 · 전체 "
            f"Total {len(selected_semantic_candidates)}"
        )

        st.caption(
            "Grounding · "
            f"SUPPORTED "
            f"{semantic_status_counts['SUPPORTED']} · "
            f"REVIEW REQUIRED "
            f"{semantic_status_counts['REVIEW REQUIRED']} · "
            f"REJECTED "
            f"{semantic_status_counts['REJECTED']}"
        )

        semantic_status_filter = st.selectbox(
            "후보 보기",
            (
                "SUPPORTED",
                "REVIEW REQUIRED",
                "REJECTED",
                "전체",
            ),
            format_func=lambda value: {
                "SUPPORTED": "역할 근거 확인됨",
                "REVIEW REQUIRED": "추가 확인 필요",
                "REJECTED": "현재 역할과 맞지 않음",
                "전체": "전체 후보 보기",
            }[value],
            key="semantic_grounding_status_filter",
        )

        st.caption(
            "표시 필터는 보기만 바꾸며 Proposed Role, "
            "Role Grounding, source evidence를 변경하지 않습니다."
        )

        semantic_search_query = st.text_input(
            "후보 검색",
            placeholder=(
                "예: hardness, HRC, pressure, source file name"
            ),
            key=(
                "semantic_candidate_search_"
                + candidate_category
            ),
        )

        visible_semantic_candidates = []

        for candidate in analysis.candidates:
            role_matches = (
                semantic_role_filter == "전체"
                or (
                    semantic_role_filter == "Requirement"
                    and candidate.role == "requirement"
                )
                or (
                    semantic_role_filter == "Verification"
                    and candidate.role == "verification"
                )
            )

            status_matches = (
                semantic_status_filter == "전체"
                or grounding_display_status(
                    semantic_role_grounding.get(
                        candidate.candidate_id
                    )
                )
                == semantic_status_filter
            )

            if role_matches and status_matches:
                visible_semantic_candidates.append(
                    candidate
                )

        normalized_semantic_search = (
            semantic_search_query
            .strip()
            .lower()
        )

        if normalized_semantic_search:
            visible_semantic_candidates = [
                candidate
                for candidate
                in visible_semantic_candidates
                if normalized_semantic_search
                in (
                    format_candidate_review_summary(
                        candidate.extraction
                    )
                    + " "
                    + str(
                        candidate.source_name
                        or ""
                    )
                ).lower()
            ]

        semantic_connection_counts = {
            "DIRECT": 0,
            "REVIEW": 0,
            "MISMATCH": 0,
            "NO_CONTEXT": 0,
        }

        semantic_connection_anchors = []

        if (
            candidate_category == "Verification"
            and guided_requirement_candidate is not None
        ):
            semantic_connection_anchors = [
                guided_requirement_candidate
            ]

        for candidate in visible_semantic_candidates:
            state = candidate_connection_state(
                candidate,
                semantic_connection_anchors,
            )
            semantic_connection_counts[state] += 1

        if semantic_connection_anchors:
            visible_semantic_candidates.sort(
                key=lambda candidate: (
                    connection_state_priority(
                        candidate_connection_state(
                            candidate,
                            semantic_connection_anchors,
                        )
                    ),
                    format_candidate_review_summary(
                        candidate.extraction
                    ).lower(),
                )
            )

            st.caption(
                "현재 Requirement와의 연결 안내 · "
                f"직접 연결 {semantic_connection_counts['DIRECT']} · "
                f"Mapping 검토 {semantic_connection_counts['REVIEW']} · "
                "바로 연결되지 않음 "
                f"{semantic_connection_counts['MISMATCH']}"
            )

        selected_semantic_count = sum(
            candidate.candidate_id
            in approved_candidate_ids
            for candidate
            in selected_semantic_candidates
        )

        st.caption(
            "표시 중 · "
            f"{len(visible_semantic_candidates)} / "
            f"{len(selected_semantic_candidates)}"
            "  ·  Formal Model 선택 · "
            f"{selected_semantic_count}"
        )

        for index, candidate in enumerate(
            visible_semantic_candidates,
            start=1,
        ):
            semantic_grounding = (
                semantic_role_grounding.get(
                    candidate.candidate_id
                )
            )

            semantic_grounding_supported = bool(
                semantic_grounding is not None
                and semantic_grounding.supported
            )

            role_label = (
                "설계 요구조건 (Requirement)"
                if candidate.role
                == "requirement"
                else "검사 기준 (Verification Criterion)"
            )

            semantic_candidate_title = (
                build_candidate_review_title(
                    proposed_role=(
                        "Requirement"
                        if candidate.role == "requirement"
                        else "Verification"
                    ),
                    extraction=candidate.extraction,
                    grounding=semantic_grounding,
                    source_name=candidate.source_name,
                    approved=(
                        candidate.candidate_id
                        in approved_candidate_ids
                    ),
                )
            )

            if (
                candidate_category == "Verification"
                and guided_requirement_candidate is not None
            ):
                semantic_connection_state = (
                    candidate_connection_state(
                        candidate,
                        [
                            guided_requirement_candidate
                        ],
                    )
                )

                semantic_candidate_title = (
                    "["
                    + connection_state_label(
                        semantic_connection_state
                    )
                    + "] "
                    + semantic_candidate_title
                )

            with st.expander(
                semantic_candidate_title,
                expanded=candidate_details_expanded,
            ):
                st.caption(
                    "PROPOSED ROLE · "
                    + (
                        "Requirement"
                        if candidate.role == "requirement"
                        else "Verification"
                    )
                )

                source_column, semantics_column = (
                    st.columns(2)
                )

                preview_page = candidate.source_page

                with source_column:
                    st.subheader(
                        "원문 근거 (Source Evidence)"
                    )

                    source = candidate.source_name
                    block = (
                        candidate.source_block_id
                        or "—"
                    )

                    st.caption(
                        f"{source} · Block {block}"
                    )

                    if candidate.source_sha256:
                        with st.expander(
                            "원문 추적 정보 (Advanced)"
                        ):
                            st.caption(
                                "SHA-256 · "
                                + candidate.source_sha256
                            )
                            st.caption(
                                "Block · "
                                + str(block)
                            )
                            st.caption(
                                "Candidate ID · "
                                + candidate.candidate_id
                            )

                    if (
                        candidate.source_location_status
                        == "SOURCE_LOCATION_AMBIGUOUS"
                    ):
                        st.warning(
                            "Source Location Review Required"
                        )
                        st.write(
                            "Candidate source block found on: "
                            + ", ".join(
                                "Page " + str(page)
                                for page in candidate
                                .source_location_candidates
                            )
                        )

                        selected_page = st.selectbox(
                            "Select the source page",
                            candidate.source_location_candidates,
                            format_func=(
                                lambda page: f"Page {page}"
                            ),
                            key=(
                                "source_location_page_"
                                + safe_key(
                                    candidate.candidate_id
                                )
                            ),
                        )
                        source_confirmed = st.checkbox(
                            "Confirm this source location",
                            key=(
                                "source_location_confirm_"
                                + safe_key(
                                    candidate.candidate_id
                                )
                            ),
                        )
                        preview_page = selected_page

                        if source_confirmed:
                            try:
                                candidate = (
                                    confirm_ambiguous_source_location(
                                        candidate,
                                        selected_page,
                                        True,
                                    )
                                )
                                analysis.candidates[
                                    index - 1
                                ] = candidate
                                st.success(
                                    "Source page confirmed separately "
                                    "from semantic approval."
                                )
                            except ValueError as exc:
                                st.error(str(exc))

                    elif candidate.source_location_status in {
                        "SOURCE_LOCATION_UNRESOLVED",
                        "SOURCE_LOCATION_MISMATCH",
                    }:
                        st.error(
                            "Source location blocked · "
                            + format_code_label(
                                candidate.source_location_status
                            )
                        )

                    elif candidate.source_pages:
                        st.success(
                            "Source location · "
                            + ", ".join(
                                f"Page {page}"
                                for page in candidate.source_pages
                            )
                        )

                        if len(candidate.source_pages) > 1:
                            preview_page = st.selectbox(
                                "Preview source page",
                                candidate.source_pages,
                                format_func=(
                                    lambda page: f"Page {page}"
                                ),
                                key=(
                                    "source_preview_page_"
                                    + safe_key(
                                        candidate.candidate_id
                                    )
                                ),
                            )

                    pdf_document = source_pdfs.get(
                        (
                            candidate.role,
                            candidate.source_sha256,
                        )
                    )

                    if (
                        pdf_document is not None
                        and preview_page is not None
                    ):
                        with st.expander(
                            "원본 PDF 페이지 보기"
                        ):
                            try:
                                st.pdf(
                                    build_pdf_page_preview(
                                        pdf_document,
                                        preview_page,
                                    ),
                                    height=360,
                                    key=(
                                        "pdf_preview_"
                                        + safe_key(
                                            candidate.candidate_id
                                            + ":"
                                            + str(preview_page)
                                        )
                                    ),
                                )
                            except Exception as exc:
                                st.error(
                                    "PDF page preview failed: "
                                    + str(exc)
                                )

                        page_record = (
                            pdf_document.page(
                                preview_page
                            )
                        )

                        if page_record is not None:
                            with st.expander(
                                "추출된 페이지 텍스트"
                            ):
                                st.write(
                                    page_record.text
                                )

                    elif pdf_document is not None:
                        with st.expander(
                            "View original PDF"
                        ):
                            try:
                                st.pdf(
                                    pdf_document.raw_bytes,
                                    height=480,
                                    key=(
                                        "pdf_document_"
                                        + safe_key(
                                            candidate.candidate_id
                                        )
                                    ),
                                )
                            except Exception as exc:
                                st.error(
                                    "PDF preview failed: "
                                    + str(exc)
                                )

                    with st.expander(
                        "Candidate source block"
                    ):
                        st.code(
                            candidate.source_text,
                            language=None,
                        )

                with semantics_column:
                    st.markdown(
                        "#### AI 추출 후보 (AI Extracted Candidate)"
                    )
                    st.subheader(
                        f"{role_label} "
                        f"{candidate.constraint_id}"
                    )

                    st.markdown(
                        "### "
                        + format_constraint(
                            candidate.extraction
                        )
                    )

                    st.caption(
                        "Constraint Type · "
                        + format_code_label(
                            str(
                                candidate.extraction.get(
                                    "type",
                                    "unknown",
                                )
                            )
                        )
                        + " · Unit · "
                        + str(
                            candidate.extraction.get(
                                "unit"
                            )
                            or "—"
                        )
                    )

                    st.markdown(
                        "#### 역할 근거 (Role Evidence)"
                    )

                    if semantic_grounding is None:
                        st.warning(
                            "역할 근거 · 아직 판정되지 않음"
                        )
                    elif semantic_grounding.supported:
                        st.success(
                            "역할 근거 · 확인됨 ✓"
                        )
                    elif (
                        semantic_grounding.status
                        == "REJECTED"
                    ):
                        st.error(
                            "역할 근거 · 현재 역할과 맞지 않음"
                        )
                    else:
                        st.warning(
                            "역할 근거 · 추가 확인 필요"
                        )

                    if semantic_grounding is not None:
                        st.caption(
                            "Basis · "
                            + semantic_grounding.basis_type
                        )
                        st.caption(
                            semantic_grounding.explanation
                        )

                        if semantic_grounding.supporting_text:
                            st.code(
                                semantic_grounding.supporting_text,
                                language=None,
                            )

                    reviewed_adapter = None
                    strict_review_ready = False

                    if (
                        candidate.source_location_ready
                        and semantic_grounding_supported
                    ):
                        reviewed_adapter = (
                            build_engineer_reviewed_semantic_adapter(
                                candidate,
                                semantic_grounding,
                            )
                        )

                        strict_review_ready = (
                            reviewed_adapter is not None
                            and reviewed_adapter.accepted
                        )

                    if strict_review_ready:
                        st.success(
                            "검토 준비 완료"
                        )
                    elif (
                        candidate.source_location_status
                        == "SOURCE_LOCATION_AMBIGUOUS"
                    ):
                        st.warning(
                            "Confirm the source page before "
                            "semantic approval."
                        )
                    else:
                        st.error(
                            "Blocked"
                        )

                    with st.expander(
                        "고급 정보 · Raw extraction"
                    ):
                        st.json(
                            candidate.extraction
                        )

                    semantic_is_selected = (
                        candidate.candidate_id
                        in approved_candidate_ids
                    )

                    formal_role_label = (
                        "Requirement"
                        if candidate.role == "requirement"
                        else "Verification Criterion"
                    )

                    st.markdown(
                        "#### Selection Readiness"
                    )

                    if semantic_is_selected:
                        st.success(
                            "Selection Readiness · "
                            "이번 검증에 선택됨 ✓"
                        )

                        st.caption(
                            "이 원문 근거는 이번 Formal Model의 "
                            + formal_role_label
                            + "으로 선택되어 있습니다."
                        )

                        revoke_semantic = st.button(
                            "선택 취소",
                            key=(
                                "semantic_unselect_button_"
                                + safe_key(
                                    candidate.candidate_id
                                )
                            ),
                        )

                        if revoke_semantic:
                            approved_candidate_ids.remove(
                                candidate.candidate_id
                            )

                            st.session_state[
                                "semantic_approved_candidate_ids"
                            ] = list(
                                approved_candidate_ids
                            )

                            st.rerun()

                    elif strict_review_ready:
                        st.success(
                            "Selection Readiness · 선택 가능 ✓"
                        )

                        st.caption(
                            "원문 위치, 역할 근거와 strict review gate가 "
                            "준비되었습니다. 원문과 공학적 의미를 확인한 뒤 "
                            "이번 검증에 사용할지 Engineer가 결정합니다."
                        )

                        select_semantic = st.button(
                            (
                                "이 근거를 Requirement로 사용"
                                if candidate.role == "requirement"
                                else
                                "이 근거를 Verification Criterion으로 사용"
                            ),
                            type="primary",
                            key=(
                                "semantic_select_button_"
                                + safe_key(
                                    candidate.candidate_id
                                )
                            ),
                        )

                        if select_semantic:
                            # Keep one selected candidate per
                            # semantic role. Choosing another
                            # Requirement replaces Requirement only;
                            # Verification behaves independently.
                            same_role_candidate_ids = {
                                item.candidate_id
                                for item in analysis.candidates
                                if item.role == candidate.role
                            }

                            approved_candidate_ids = [
                                candidate_id
                                for candidate_id
                                in approved_candidate_ids
                                if candidate_id
                                not in same_role_candidate_ids
                            ]

                            approved_candidate_ids.append(
                                candidate.candidate_id
                            )

                            st.session_state[
                                "semantic_approved_candidate_ids"
                            ] = list(
                                approved_candidate_ids
                            )

                            st.rerun()

                    else:
                        st.warning(
                            "Selection Readiness · 추가 검토 필요"
                        )

                        if not analysis_is_current:
                            st.caption(
                                "분석 이후 source가 변경되었습니다. "
                                "문서를 다시 분석해야 합니다."
                            )
                        elif not candidate.source_location_ready:
                            st.caption(
                                "원문 위치 확인이 아직 완료되지 않았습니다."
                            )
                        elif not semantic_grounding_supported:
                            st.caption(
                                "현재 역할의 근거가 아직 확정되지 않았습니다."
                            )
                        elif not strict_review_ready:
                            st.caption(
                                "구조화된 constraint가 strict review gate를 "
                                "아직 통과하지 못했습니다."
                            )
                        else:
                            st.caption(
                                "선택에 필요한 review gate가 "
                                "아직 완료되지 않았습니다."
                            )


    st.session_state[
        "semantic_approved_candidate_ids"
    ] = list(
        approved_candidate_ids
    )

    role_completeness = (
        evaluate_role_completeness(
            semantic_analysis=analysis,
            approved_semantic_candidate_ids=(
                approved_candidate_ids
            ),
            semantic_grounding_by_candidate_id=(
                semantic_role_grounding
            ),
            feasible_analysis=feasible_analysis,
            approved_feasible_candidate_ids=(
                feasible_approved_candidate_ids
            ),
            feasible_grounding_by_candidate_id=(
                feasible_role_grounding
            ),
        )
    )

    role_set_ready = (
        analysis_is_current
        and role_completeness.ready
    )

    selected_requirement = next(
        (
            candidate
            for candidate in analysis.candidates
            if (
                candidate.role == "requirement"
                and candidate.candidate_id
                in approved_candidate_ids
            )
        ),
        None,
    )

    selected_verification = next(
        (
            candidate
            for candidate in analysis.candidates
            if (
                candidate.role == "verification"
                and candidate.candidate_id
                in approved_candidate_ids
            )
        ),
        None,
    )

    selected_feasible = None
    if feasible_analysis is not None:
        selected_feasible = next(
            (
                candidate
                for candidate in feasible_analysis.candidates
                if candidate.candidate_id
                in feasible_approved_candidate_ids
            ),
            None,
        )

    compatibility_candidates = [
        selected_requirement,
        selected_verification,
        selected_feasible,
    ]

    role_alignment_ready = (
        role_set_ready
        and all(
            candidate is not None
            for candidate in compatibility_candidates
        )
    )

    source_provenance_ready = (
        role_alignment_ready
        and all(
            bool(candidate.source_location_ready)
            for candidate in compatibility_candidates
        )
    )

    def compatibility_value(candidate, field):
        if candidate is None:
            return ""
        return str(
            (candidate.extraction or {}).get(field)
            or ""
        ).strip()

    requirement_variable = compatibility_value(
        selected_requirement,
        "variable",
    )
    verification_variable = compatibility_value(
        selected_verification,
        "variable",
    )
    feasible_variable = compatibility_value(
        selected_feasible,
        "variable",
    )

    requirement_unit = compatibility_value(
        selected_requirement,
        "unit",
    )
    verification_unit = compatibility_value(
        selected_verification,
        "unit",
    )
    feasible_unit = compatibility_value(
        selected_feasible,
        "unit",
    )

    compatibility_units = [
        requirement_unit,
        verification_unit,
        feasible_unit,
    ]

    unit_alignment_ready = (
        role_alignment_ready
        and all(compatibility_units)
        and len(set(compatibility_units)) == 1
    )

    requirement_group_key = (
        normalize_source_variable_group_key(
            requirement_variable
        )
        if requirement_variable
        else ""
    )

    verification_group_key = (
        normalize_source_variable_group_key(
            verification_variable
        )
        if verification_variable
        else ""
    )

    feasible_group_key_original = (
        normalize_source_variable_group_key(
            feasible_variable
        )
        if feasible_variable
        else ""
    )

    compatibility_group_keys = [
        requirement_group_key,
        verification_group_key,
        feasible_group_key_original,
    ]

    exact_variable_alignment = (
        role_alignment_ready
        and all(compatibility_group_keys)
        and len(set(compatibility_group_keys)) == 1
    )

    compatibility_signature_parts = [
        candidate.candidate_id
        if candidate is not None
        else ""
        for candidate in compatibility_candidates
    ]

    compatibility_signature = hashlib.sha256(
        "|".join(
            compatibility_signature_parts
        ).encode("utf-8")
    ).hexdigest()

    if (
        st.session_state.get(
            "evidence_compatibility_signature"
        )
        != compatibility_signature
    ):
        st.session_state[
            "evidence_compatibility_signature"
        ] = compatibility_signature
        st.session_state[
            "engineer_variable_mapping_confirmed"
        ] = False
        st.session_state[
            "engineer_feasible_group_override"
        ] = {}

    engineer_variable_mapping_confirmed = bool(
        st.session_state.get(
            "engineer_variable_mapping_confirmed",
            False,
        )
    )

    variable_alignment_ready = (
        exact_variable_alignment
        or (
            unit_alignment_ready
            and engineer_variable_mapping_confirmed
        )
    )

    compatibility_ready = (
        role_alignment_ready
        and source_provenance_ready
        and unit_alignment_ready
        and variable_alignment_ready
    )

    formalization_ready = (
        analysis_is_current
        and role_set_ready
        and compatibility_ready
    )

    established_semantic_ids = set(
        role_completeness
        .established_semantic_candidate_ids
    )

    approved_analysis = deepcopy(
        analysis
    )

    approved_analysis.candidates = [
        candidate
        for candidate in analysis.candidates
        if candidate.candidate_id
        in established_semantic_ids
    ]

    current_semantic_review_signature = (
        build_semantic_review_signature(
            analysis,
            approved_candidate_ids,
        )
    )

    st.markdown(
        "### Role Completeness"
    )

    completeness_columns = st.columns(3)

    completeness_rows = [
        (
            completeness_columns[0],
            "Requirement",
            role_completeness
            .requirement_candidate_count,
            role_completeness
            .requirement_established,
        ),
        (
            completeness_columns[1],
            "Verification",
            role_completeness
            .verification_candidate_count,
            role_completeness
            .verification_established,
        ),
        (
            completeness_columns[2],
            "실제 관측 근거",
            role_completeness
            .feasible_candidate_count,
            role_completeness
            .feasible_established,
        ),
    ]

    for (
        column,
        role_name,
        candidate_count,
        established,
    ) in completeness_rows:
        with column:
            st.markdown(
                f"**{role_name}**"
            )

            if candidate_count > 0:
                st.caption(
                    "Candidate · FOUND · "
                    + str(candidate_count)
                )
            else:
                st.caption(
                    "Candidate · NOT FOUND"
                )

            if established:
                st.success(
                    "ESTABLISHED ✓"
                )
            else:
                st.warning(
                    "NOT ESTABLISHED"
                )

    if role_set_ready:
        st.success(
            "Role Set Complete ✓ · "
            "Requirement / Verification / 실제 관측 근거가 "
            "각각 선택되었습니다."
        )

        st.caption(
            "Role Set Complete는 Formalization Ready와 "
            "다릅니다. 아래 Evidence Set Compatibility를 "
            "통과해야 합니다."
        )
    else:
        st.warning(
            "Formal Verification · BLOCKED"
        )

        if not analysis_is_current:
            st.caption(
                "• Source changed after analysis."
            )

        for completeness_issue in (
            role_completeness.issues
        ):
            st.caption(
                "• " + completeness_issue
            )


    if role_set_ready:
        render_review_focus(
            "Evidence Set Compatibility",
            (
                "선택한 R / V / F가 같은 engineering variable을 "
                "의미하는지 확인합니다."
            ),
        )

        st.markdown("### Evidence Set Compatibility")

        st.caption(
            "선택된 R / V / F가 하나의 Formal Model에서 "
            "서로 연결될 수 있는지 확인합니다."
        )

        compatibility_columns = st.columns(4)

        with compatibility_columns[0]:
            if role_alignment_ready:
                st.success("Role Alignment · READY ✓")
            else:
                st.error("Role Alignment · BLOCKED")

        with compatibility_columns[1]:
            if source_provenance_ready:
                st.success("Source Provenance · READY ✓")
            else:
                st.error("Source Provenance · BLOCKED")

        with compatibility_columns[2]:
            if unit_alignment_ready:
                st.success("Unit Alignment · READY ✓")
            else:
                st.error("Unit Alignment · BLOCKED")

        with compatibility_columns[3]:
            if variable_alignment_ready:
                st.success("Variable Alignment · READY ✓")
            elif unit_alignment_ready:
                st.warning(
                    "Variable Alignment · REVIEW REQUIRED"
                )
            else:
                st.error("Variable Alignment · BLOCKED")

        st.markdown("#### 선택된 Evidence Set")

        evidence_columns = st.columns(3)

        with evidence_columns[0]:
            st.markdown("**Requirement**")
            st.write(
                format_candidate_review_summary(
                    (
                        selected_requirement.extraction
                        if selected_requirement
                        else {}
                    )
                )
            )

        with evidence_columns[1]:
            st.markdown("**Verification**")
            st.write(
                format_candidate_review_summary(
                    (
                        selected_verification.extraction
                        if selected_verification
                        else {}
                    )
                )
            )

        with evidence_columns[2]:
            st.markdown("**실제 관측 근거**")
            st.write(
                format_candidate_review_summary(
                    (
                        selected_feasible.extraction
                        if selected_feasible
                        else {}
                    )
                )
            )

        st.markdown("#### 실제 관측 근거 연결 진단")

        st.caption(
            "현재 선택된 Requirement / Verification을 기준으로 "
            "실제 관측 근거 후보가 같은 engineering state로 "
            "연결될 수 있는지 확인합니다."
        )

        rv_connection_state = None

        if (
            selected_requirement is not None
            and selected_verification is not None
        ):
            rv_connection_state = candidate_connection_state(
                selected_verification,
                [
                    selected_requirement,
                ],
            )

        feasible_connection_states = []

        if (
            feasible_analysis is not None
            and selected_requirement is not None
            and selected_verification is not None
        ):
            for candidate in feasible_analysis.candidates:
                connection_state = candidate_connection_state(
                    candidate,
                    [
                        selected_requirement,
                        selected_verification,
                    ],
                )

                feasible_connection_states.append(
                    (
                        candidate,
                        connection_state,
                    )
                )

        direct_feasible_candidates = [
            candidate
            for candidate, state
            in feasible_connection_states
            if state == "DIRECT"
        ]

        review_feasible_candidates = [
            candidate
            for candidate, state
            in feasible_connection_states
            if state == "REVIEW"
        ]

        mismatch_feasible_candidates = [
            candidate
            for candidate, state
            in feasible_connection_states
            if state == "MISMATCH"
        ]

        if rv_connection_state == "MISMATCH":
            st.error(
                "Requirement / Verification이 같은 "
                "engineering state로 정렬되지 않았습니다."
            )

            st.caption(
                "현재 선택한 R과 V가 서로 다른 변수 또는 단위를 "
                "가리키므로, 실제 관측 근거와의 연결 여부를 "
                "확정하지 않습니다."
            )

            st.info(
                "실제 관측 근거 후보는 그대로 유지됩니다. "
                "먼저 Requirement / Verification 조합을 다시 검토하거나, "
                "Engineer Review에서 engineering state의 동일성을 "
                "확인해야 합니다."
            )

        else:
            if direct_feasible_candidates:
                st.success(
                    "현재 R / V와 바로 연결 가능한 "
                    "실제 관측 근거 후보 · "
                    + str(
                        len(
                            direct_feasible_candidates
                        )
                    )
                    + "개"
                )

                st.caption(
                    "표현된 engineering variable과 unit이 "
                    "현재 deterministic 연결 규칙에서 일치합니다."
                )

            elif review_feasible_candidates:
                st.warning(
                    "바로 연결 가능한 실제 관측 근거는 없지만, "
                    "Engineer Review가 필요한 후보가 "
                    + str(
                        len(
                            review_feasible_candidates
                        )
                    )
                    + "개 있습니다."
                )

                st.caption(
                    "단위는 연결 가능하지만 변수 표현 또는 "
                    "engineering context의 동일성을 사람이 확인해야 합니다. "
                    "후보는 자동으로 승인되지 않습니다."
                )

            elif feasible_connection_states:
                st.error(
                    "현재 R / V와 연결 가능한 "
                    "실제 관측 근거를 확인하지 못했습니다."
                )

                st.markdown(
                    "**현재 상태 · "
                    "NO COMPATIBLE OBSERVED EVIDENCE**"
                )

                st.caption(
                    "실제 관측 근거 후보 자체는 발견되었지만, "
                    "현재 선택된 Requirement / Verification과 "
                    "같은 engineering state로 바로 연결할 수 있는 "
                    "후보는 확인되지 않았습니다."
                )

                candidate_count_left, candidate_count_right = (
                    st.columns(2)
                )

                with candidate_count_left:
                    st.metric(
                        "실제 관측 근거 후보",
                        len(
                            feasible_connection_states
                        ),
                    )

                with candidate_count_right:
                    st.metric(
                        "현재 연결 가능",
                        0,
                    )

                st.info(
                    "후보는 삭제되거나 숨겨지지 않습니다. "
                    "다른 실제 관측 근거 후보를 검토하거나 "
                    "Engineer Review에서 engineering state의 "
                    "동일성을 확인할 수 있습니다. "
                    "확인 전에는 Formalization을 진행하지 않습니다."
                )

            else:
                st.error(
                    "실제 관측 근거 후보를 확인하지 못했습니다."
                )

                st.caption(
                    "Formal Verification에 필요한 실제 관측 근거가 "
                    "없으므로 Formalization을 진행하지 않습니다."
                )

        if (
            selected_feasible is not None
            and selected_requirement is not None
            and selected_verification is not None
            and rv_connection_state != "MISMATCH"
        ):
            selected_feasible_connection_state = (
                candidate_connection_state(
                    selected_feasible,
                    [
                        selected_requirement,
                        selected_verification,
                    ],
                )
            )

            if selected_feasible_connection_state == "MISMATCH":
                st.error(
                    "현재 선택한 실제 관측 근거는 "
                    "R / V와 변수 또는 단위가 일치하지 않습니다."
                )

                st.caption(
                    "이 후보는 Formal Model에 자동 연결되지 않습니다. "
                    "후보 자체는 계속 검토할 수 있습니다."
                )

            elif selected_feasible_connection_state == "REVIEW":
                st.warning(
                    "현재 선택한 실제 관측 근거의 "
                    "공학적 동일성 확인이 필요합니다."
                )

                st.caption(
                    "자동 연결하지 않고 Engineer Review에서 "
                    "같은 engineering state인지 확인해야 합니다."
                )

        with st.expander(
            "연결 진단 기준",
            expanded=False,
        ):
            st.write(
                "이 진단은 후보를 정답/오답으로 판정하는 기능이 아닙니다."
            )

            st.write(
                "자동 연결 안내는 현재 variable normalization과 "
                "engineering unit 정렬을 기준으로 합니다."
            )

            st.write(
                "문맥상 같은 물리량인지에 대한 최종 판단은 "
                "Engineer Review에 남겨둡니다."
            )

            if feasible_connection_states:
                st.caption(
                    "후보 상태 요약 · "
                    + "바로 연결 "
                    + str(
                        len(
                            direct_feasible_candidates
                        )
                    )
                    + " · 검토 필요 "
                    + str(
                        len(
                            review_feasible_candidates
                        )
                    )
                    + " · 불일치 "
                    + str(
                        len(
                            mismatch_feasible_candidates
                        )
                    )
                )

        st.divider()

        if not unit_alignment_ready:
            st.error(
                "선택된 R / V / F의 Engineering Unit이 "
                "일치하지 않습니다."
            )

            st.caption(
                "Requirement · "
                + (requirement_unit or "UNIT MISSING")
                + " | Verification · "
                + (verification_unit or "UNIT MISSING")
                + " | 실제 관측 근거 · "
                + (feasible_unit or "UNIT MISSING")
            )

            st.caption(
                "단위 변환을 자동으로 가정하지 않습니다. "
                "현재 조합을 다시 검토해 주세요."
            )

        elif exact_variable_alignment:
            st.success(
                "Variable Alignment · 문서의 변수 표현이 "
                "동일한 source-variable group으로 연결됩니다."
            )

        else:
            st.warning(
                "Variable Alignment · Engineer confirmation required"
            )

            st.write(
                "문서의 변수 이름이 완전히 동일하지 않습니다. "
                "시스템은 이를 자동으로 같은 변수라고 확정하지 않습니다."
            )

            mapping_left, mapping_middle, mapping_right = (
                st.columns(3)
            )

            mapping_left.metric(
                "Requirement",
                requirement_variable or "—",
            )

            mapping_middle.metric(
                "Verification",
                verification_variable or "—",
            )

            mapping_right.metric(
                "실제 관측 근거",
                feasible_variable or "—",
            )

            st.caption(
                "같은 Engineering Unit이라는 사실만으로 "
                "같은 engineering variable이라고 판단하지 않습니다."
            )

            confirm_col, reject_col = st.columns(2)

            with confirm_col:
                confirm_mapping = st.button(
                    "같은 engineering variable로 확인",
                    type="primary",
                    key="confirm_evidence_variable_mapping",
                )

            with reject_col:
                reject_mapping = st.button(
                    "다른 변수로 유지",
                    key="reject_evidence_variable_mapping",
                )

            if confirm_mapping:
                st.session_state[
                    "engineer_variable_mapping_confirmed"
                ] = True

                st.session_state[
                    "engineer_feasible_group_override"
                ] = {
                    (
                        selected_feasible.candidate_id
                        if selected_feasible
                        else ""
                    ): requirement_group_key
                }

                st.rerun()

            if reject_mapping:
                st.session_state[
                    "engineer_variable_mapping_confirmed"
                ] = False

                st.session_state[
                    "engineer_feasible_group_override"
                ] = {}

                st.rerun()

            if engineer_variable_mapping_confirmed:
                st.success(
                    "Engineer Variable Mapping · CONFIRMED ✓"
                )

                st.caption(
                    "이 확인은 선택된 Evidence Set에만 적용됩니다. "
                    "R / V / F 선택이 바뀌면 자동으로 무효화됩니다."
                )

        st.markdown("#### Formalization Readiness")

        if formalization_ready:
            st.success(
                "FORMALIZATION READY ✓ · "
                "Role / Variable / Unit / Source checks passed."
            )
        else:
            st.warning(
                "FORMALIZATION NOT READY · "
                "위 Compatibility 항목을 먼저 해결하세요."
            )

    # =====================================================
    # STEP 3 — VARIABLE MAPPING + FEASIBLE DOMAIN
    # =====================================================

    if formalization_ready:
        st.divider()

        render_section_header(
            "STAGE 03",
            "Formal Review",
            "승인된 engineering semantics와 source-bound feasible evidence를 검토해 Formal Verification Model을 구성합니다.",
        )
        render_soft_note(
            "Variable mapping과 source 원문 추적를 검토한 뒤 승인된 값만 deterministic verification으로 전달합니다."
        )

        st.caption(
            "추출된 공학 변수를 검토하고 현실 가능 범위 "
            "(실제 가능한 범위(F))를 공학적 근거와 함께 확인합니다."
        )

        targets = (
            build_variable_mapping_targets(
                approved_analysis
            )
        )

        source_info: dict[
            str,
            dict,
        ] = {}

        for target in targets:
            group_key = (
                normalize_source_variable_group_key(
                    target.source_variable
                )
            )

            item = source_info.setdefault(
                group_key,
                {
                    "display_name": (
                        target.source_variable
                    ),
                    "aliases": set(),
                    "units": set(),
                    "targets": [],
                },
            )

            item["aliases"].add(
                target.source_variable
            )

            if target.unit:
                item["units"].add(
                    target.unit
                )

            item["targets"].append(
                target
            )

        approved_feasible_ids = set(
            role_completeness
            .established_feasible_candidate_ids
        )

        feasible_binding_by_group = {}
        feasible_binding_errors = []

        if (
            feasible_analysis is not None
            and approved_feasible_ids
        ):
            for feasible_candidate in (
                feasible_analysis.candidates
            ):
                if (
                    feasible_candidate.candidate_id
                    not in approved_feasible_ids
                ):
                    continue

                extraction = (
                    feasible_candidate.extraction
                )

                source_variable_f = str(
                    extraction.get(
                        "variable"
                    )
                    or ""
                ).strip()

                if not source_variable_f:
                    feasible_binding_errors.append(
                        feasible_candidate.candidate_id
                        + ": variable is missing."
                    )
                    continue

                if not (
                    feasible_candidate
                    .source_location_ready
                ):
                    feasible_binding_errors.append(
                        feasible_candidate.candidate_id
                        + ": source location is not ready."
                    )
                    continue

                if bool(
                    extraction.get(
                        "needs_review",
                        True,
                    )
                ):
                    feasible_binding_errors.append(
                        feasible_candidate.candidate_id
                        + ": candidate still requires review."
                    )
                    continue

                feasible_group_key = (
                    normalize_source_variable_group_key(
                        source_variable_f
                    )
                )

                engineer_group_override = (
                    st.session_state.get(
                        "engineer_feasible_group_override",
                        {},
                    )
                )

                overridden_group_key = (
                    engineer_group_override.get(
                        feasible_candidate.candidate_id
                    )
                )

                if overridden_group_key:
                    feasible_group_key = (
                        overridden_group_key
                    )

                if (
                    feasible_group_key
                    not in source_info
                ):
                    feasible_binding_errors.append(
                        source_variable_f
                        + ": approved Operating Evidence "
                        "does not match an R/V variable."
                    )
                    continue

                source_reference_f = (
                    build_source_reference(
                        source_name=(
                            feasible_candidate.source_name
                        ),
                        source_block_id=(
                            feasible_candidate.source_block_id
                        ),
                        source_pages=(
                            feasible_candidate.source_pages
                        ),
                    )
                )

                binding = {
                    "candidate_id":
                        feasible_candidate.candidate_id,
                    "unit": str(
                        extraction.get("unit")
                        or ""
                    ).strip(),
                    "min": str(
                        extraction.get("min")
                        or ""
                    ).strip(),
                    "max": str(
                        extraction.get("max")
                        or ""
                    ).strip(),
                    "evidence_type": str(
                        extraction.get(
                            "evidence_type"
                        )
                        or ""
                    ).strip(),
                    "reference": str(
                        source_reference_f
                        or ""
                    ).strip(),
                }

                rv_units = (
                    source_info[
                        feasible_group_key
                    ]["units"]
                )

                if (
                    rv_units
                    and binding["unit"]
                    not in rv_units
                ):
                    feasible_binding_errors.append(
                        source_variable_f
                        + ": Operating Evidence unit "
                        + binding["unit"]
                        + " conflicts with R/V unit(s): "
                        + ", ".join(
                            sorted(
                                rv_units
                            )
                        )
                    )
                    continue

                if not all(
                    binding[
                        field
                    ]
                    for field in (
                        "unit",
                        "min",
                        "max",
                        "evidence_type",
                        "reference",
                    )
                ):
                    feasible_binding_errors.append(
                        feasible_candidate.candidate_id
                        + ": required source-bound data is missing."
                    )
                    continue

                if (
                    feasible_group_key
                    in feasible_binding_by_group
                ):
                    feasible_binding_errors.append(
                        source_variable_f
                        + ": multiple approved F candidates "
                        "map to the same variable."
                    )
                    feasible_binding_by_group[
                        feasible_group_key
                    ] = None
                    continue

                feasible_binding_by_group[
                    feasible_group_key
                ] = binding

        for issue in feasible_binding_errors:
            st.error(
                "Feasible Evidence binding blocked · "
                + issue
            )

        variable_forms = {}

        for group_key, info in (
            source_info.items()
        ):
            source_variable = info[
                "display_name"
            ]

            key = safe_key(
                group_key
            )

            units = sorted(
                info["units"]
            )

            default_unit = (
                units[0]
                if len(units) == 1
                else ""
            )

            group_type, _, group_value = (
                group_key.partition(":")
            )
            existing_mapping_suggestion = (
                group_value
                if (
                    group_type == "symbol"
                    and valid_variable_id(
                        group_value
                    )
                )
                else ""
            )

            source_bound = (
                feasible_binding_by_group.get(
                    group_key
                )
            )

            binding_marker_key = (
                "feasible_bound_candidate_"
                + key
            )

            source_bound_id = (
                source_bound[
                    "candidate_id"
                ]
                if source_bound is not None
                else None
            )

            previous_bound_id = (
                st.session_state.get(
                    binding_marker_key
                )
            )

            if (
                source_bound_id
                != previous_bound_id
            ):
                for widget_key in (
                    "unit_" + key,
                    "fmin_" + key,
                    "fmax_" + key,
                    "evidence_type_" + key,
                    "evidence_ref_" + key,
                    "evidence_confirmed_" + key,
                ):
                    st.session_state.pop(
                        widget_key,
                        None,
                    )

                if source_bound_id is None:
                    st.session_state.pop(
                        binding_marker_key,
                        None,
                    )
                else:
                    st.session_state[
                        binding_marker_key
                    ] = source_bound_id

            with st.container(
                border=True
            ):
                st.subheader(
                    source_variable
                )

                st.caption(
                    "문서에서 추출된 공학 변수"
                )

                aliases = sorted(
                    info["aliases"]
                )

                if len(aliases) > 1:
                    st.caption(
                        "Document aliases · "
                        + " · ".join(
                            aliases
                        )
                    )

                if len(units) > 1:
                    st.error(
                        "동일 Source Variable에 "
                        "서로 다른 Engineering Unit이 확인되었습니다: "
                        + ", ".join(
                            units
                        )
                    )

                canonical_id = (
                    st.text_input(
                        "Canonical Variable ID",
                        value=(
                            existing_mapping_suggestion
                        ),
                        placeholder="예: H",
                        key=(
                            "canonical_"
                            + key
                        ),
                    )
                )

                if source_bound is not None:
                    st.markdown(
                        "#### 현실 가능 범위 검토 "
                        "(실제 가능한 범위(F) Review)"
                    )

                    min_col, max_col, unit_col = (
                        st.columns(3)
                    )

                    min_col.metric(
                        "Feasible Min",
                        source_bound["min"],
                    )

                    max_col.metric(
                        "Feasible Max",
                        source_bound["max"],
                    )

                    unit_col.metric(
                        "Engineering Unit",
                        source_bound["unit"],
                    )

                    canonical_display = (
                        canonical_id.strip()
                        or source_variable
                    )

                    st.markdown(
                        "**Formal 실제 가능한 범위(F)** · "
                        f"`{source_bound['min']} ≤ "
                        f"{canonical_display} ≤ "
                        f"{source_bound['max']} "
                        f"{source_bound['unit']}`"
                    )

                    status_left, status_right = (
                        st.columns(2)
                    )

                    status_left.success(
                        "✓ PDF Source Bound"
                    )

                    status_right.success(
                        "✓ Engineer Approved"
                    )

                    st.markdown(
                        "**원문 근거 (Source Evidence)**"
                    )

                    st.write(
                        source_bound[
                            "reference"
                        ]
                    )

                    st.caption(
                        "Evidence Type · "
                        + source_bound[
                            "evidence_type"
                        ]
                    )

                    st.caption(
                        "Min / Max / Unit / Evidence Reference는 "
                        "승인된 Operating Evidence 원문에 "
                        "직접 연결되어 있습니다."
                    )

                    unit = (
                        source_bound["unit"]
                    )

                    feasible_min = (
                        source_bound["min"]
                    )

                    feasible_max = (
                        source_bound["max"]
                    )

                    evidence_type = (
                        source_bound[
                            "evidence_type"
                        ]
                    )

                    evidence_reference = (
                        source_bound[
                            "reference"
                        ]
                    )

                    evidence_confirmed = True

                else:
                    st.info(
                        "승인된 PDF Source-Bound "
                        "Operating Evidence가 없습니다."
                    )

                    with st.expander(
                        "Advanced · Engineer-Supplied "
                        "실제 가능한 범위(F)"
                    ):
                        unit = st.text_input(
                            "공학 단위 (Engineering Unit)",
                            value=default_unit,
                            key=(
                                "unit_"
                                + key
                            ),
                        )

                        feasible_min = (
                            st.text_input(
                                "현실 가능 최솟값 "
                                "(Feasible Min)",
                                placeholder="예: 58",
                                key=(
                                    "fmin_"
                                    + key
                                ),
                            )
                        )

                        feasible_max = (
                            st.text_input(
                                "현실 가능 최댓값 "
                                "(Feasible Max)",
                                placeholder="예: 60",
                                key=(
                                    "fmax_"
                                    + key
                                ),
                            )
                        )

                        evidence_type = (
                            st.selectbox(
                                "현실 가능 근거 유형 "
                                "(Evidence Type)",
                                [
                                    "observed_test_data",
                                    "manufacturing_record",
                                    "engineering_analysis",
                                    "other",
                                ],
                                key=(
                                    "evidence_type_"
                                    + key
                                ),
                            )
                        )

                        evidence_reference = (
                            st.text_input(
                                "근거 참조 "
                                "(Evidence Reference)",
                                placeholder=(
                                    "예: hardness_test_report:"
                                    "sample_set_A"
                                ),
                                key=(
                                    "evidence_ref_"
                                    + key
                                ),
                            )
                        )

                        evidence_confirmed = (
                            st.checkbox(
                                "이 현실 가능 범위가 "
                                "공학적 근거에 기반함을 "
                                "확인합니다.",
                                key=(
                                    "evidence_confirmed_"
                                    + key
                                ),
                            )
                        )

                variable_forms[
                    group_key
                ] = {
                    "display_name": (
                        source_variable
                    ),
                    "canonical_id": (
                        canonical_id.strip()
                    ),
                    "unit": (
                        unit.strip()
                    ),
                    "feasible_min": (
                        feasible_min.strip()
                    ),
                    "feasible_max": (
                        feasible_max.strip()
                    ),
                    "evidence_type": (
                        evidence_type
                    ),
                    "evidence_reference": (
                        evidence_reference.strip()
                    ),
                    "evidence_confirmed": (
                        evidence_confirmed
                    ),
                    "source_bound": (
                        source_bound
                        is not None
                    ),
                    "source_bound_candidate_id": (
                        source_bound[
                            "candidate_id"
                        ]
                        if source_bound
                        is not None
                        else None
                    ),
                }

        if st.button(
            "검증 모델 준비 (Prepare Formal Model)",
            type="primary",
        ):
            try:
                prepared_feasible_evidence_traces = []

                errors = list(
                    feasible_binding_errors
                )

                approved_feasible_ids = set(
                    role_completeness
                    .established_feasible_candidate_ids
                )

                if (
                    feasible_analysis is not None
                    and approved_feasible_ids
                ):
                    selected_feasible_analysis = (
                        deepcopy(
                            feasible_analysis
                        )
                    )

                    selected_feasible_analysis.candidates = [
                        candidate
                        for candidate
                        in selected_feasible_analysis.candidates
                        if candidate.candidate_id
                        in approved_feasible_ids
                    ]

                    canonical_variable_by_candidate = {}

                    for candidate in (
                        selected_feasible_analysis
                        .candidates
                    ):
                        source_variable_f = str(
                            candidate.extraction.get(
                                "variable"
                            )
                            or ""
                        ).strip()

                        group_key_f = (
                            normalize_source_variable_group_key(
                                source_variable_f
                            )
                        )

                        form_f = variable_forms.get(
                            group_key_f
                        )

                        if form_f is not None:
                            canonical_variable_by_candidate[
                                candidate.candidate_id
                            ] = form_f[
                                "canonical_id"
                            ]

                    grounded_feasible_result = (
                        build_grounded_feasible_evidence_prefills(
                            selected_feasible_analysis,
                            approved_candidate_ids=sorted(
                                approved_feasible_ids
                            ),
                            grounding_by_candidate_id=(
                                feasible_role_grounding
                            ),
                            canonical_variable_by_candidate=(
                                canonical_variable_by_candidate
                            ),
                        )
                    )

                    if (
                        grounded_feasible_result
                        .grounding_blocked
                    ):
                        raise ValueError(
                            "Feasible Evidence Role Grounding "
                            "blocked formalization: "
                            + "; ".join(
                                grounded_feasible_result
                                .grounding_gate
                                .issues
                            )
                        )

                    feasible_prefill_result = (
                        grounded_feasible_result
                        .downstream_result
                    )

                    if feasible_prefill_result is None:
                        raise ValueError(
                            "Grounded Feasible Evidence "
                            "prefill produced no downstream result."
                        )

                    prepared_feasible_evidence_traces = [
                        build_feasible_evidence_trace(prefill)
                        for prefill in feasible_prefill_result.prefills
                    ]

                    if not feasible_prefill_result.ready:
                        errors.extend(
                            feasible_prefill_result.issues
                        )

                    else:
                        for prefill in (
                            feasible_prefill_result.prefills
                        ):
                            group_key_f = (
                                normalize_source_variable_group_key(
                                    prefill.source_variable
                                )
                            )

                            form_f = variable_forms.get(
                                group_key_f
                            )

                            if form_f is None:
                                errors.append(
                                    prefill.source_variable
                                    + ": source-bound F has "
                                    "no matching variable form."
                                )
                                continue

                            # Application-level source-bound
                            # contract is authoritative.
                            form_f["unit"] = (
                                prefill.unit
                            )
                            form_f[
                                "feasible_min"
                            ] = (
                                prefill.feasible_min
                            )
                            form_f[
                                "feasible_max"
                            ] = (
                                prefill.feasible_max
                            )
                            form_f[
                                "evidence_type"
                            ] = (
                                prefill.evidence_type
                            )
                            form_f[
                                "evidence_reference"
                            ] = (
                                prefill.evidence_reference
                            )
                            form_f[
                                "evidence_confirmed"
                            ] = True
                            form_f[
                                "source_bound"
                            ] = True
                            form_f[
                                "source_bound_candidate_id"
                            ] = (
                                prefill.candidate_id
                            )

                for (
                    group_key,
                    form,
                ) in variable_forms.items():
                    source_variable = form[
                        "display_name"
                    ]

                    canonical_id = form[
                        "canonical_id"
                    ]

                    if not canonical_id:
                        errors.append(
                            f"{source_variable}: "
                            "Canonical ID required."
                        )

                    elif not valid_variable_id(
                        canonical_id
                    ):
                        errors.append(
                            f"{source_variable}: "
                            "Canonical ID는 "
                            "영문, 숫자 및 underscore(_) 형식을 사용해야 합니다."
                        )

                    if not form["unit"]:
                        errors.append(
                            f"{source_variable}: "
                            "Unit required."
                        )

                    if not form[
                        "feasible_min"
                    ]:
                        errors.append(
                            f"{source_variable}: "
                            "Feasible minimum required."
                        )

                    if not form[
                        "feasible_max"
                    ]:
                        errors.append(
                            f"{source_variable}: "
                            "Feasible maximum required."
                        )

                    if not form[
                        "evidence_reference"
                    ]:
                        errors.append(
                            f"{source_variable}: "
                            "Evidence reference required."
                        )

                    if not form[
                        "evidence_confirmed"
                    ]:
                        errors.append(
                            f"{source_variable}: "
                            "Evidence confirmation required."
                        )

                if errors:
                    raise ValueError(
                        "\n".join(
                            errors
                        )
                    )

                mappings_by_candidate = {}

                for target in targets:
                    group_key = (
                        normalize_source_variable_group_key(
                            target.source_variable
                        )
                    )

                    canonical_id = (
                        variable_forms[
                            group_key
                        ][
                            "canonical_id"
                        ]
                    )

                    mappings_by_candidate.setdefault(
                        target.candidate_id,
                        {},
                    )[
                        target.source_variable
                    ] = canonical_id

                mapped_analysis = (
                    apply_analysis_variable_mappings(
                    approved_analysis,

                        mappings_by_candidate,
                    )
                )

                variables = {}

                for (
                    group_key,
                    form,
                ) in variable_forms.items():
                    source_variable = form[
                        "display_name"
                    ]

                    canonical_id = form[
                        "canonical_id"
                    ]

                    spec = {
                        "unit": form[
                            "unit"
                        ],
                        "feasible_min": form[
                            "feasible_min"
                        ],
                        "feasible_max": form[
                            "feasible_max"
                        ],
                        "feasible_evidence": {
                            "source_type": (
                                form[
                                    "evidence_type"
                                ]
                            ),
                            "source_reference": (
                                form[
                                    "evidence_reference"
                                ]
                            ),
                            "approval_status": (
                                "approved"
                            ),
                            "note": (
                                (
                                    "Engineer-approved, PDF "
                                    "source-bound Operating "
                                    "Evidence through "
                                    "Application UI."
                                )
                                if form.get(
                                    "source_bound",
                                    False,
                                )
                                else (
                                    "Engineer-confirmed "
                                    "through Application UI."
                                )
                            ),
                        },
                    }

                    if (
                        canonical_id
                        in variables
                        and
                        variables[
                            canonical_id
                        ]
                        != spec
                    ):
                        raise ValueError(
                            "동일 Canonical Variable ID에 "
                            "서로 다른 실제 가능한 범위(F) "
                            "정보가 입력되었습니다: "
                            f"{canonical_id}"
                        )

                    variables[
                        canonical_id
                    ] = spec

                base_case = (
                    EngineeringCase.from_dict(
                        {
                            "name": (
                                "UI Verification Case"
                            ),
                            "variables": variables,
                            "requirements": [],
                            "verification_constraints": [],
                        }
                    )
                )

                st.session_state[
                    "mapped_analysis"
                ] = mapped_analysis

                st.session_state[
                    "base_case"
                ] = base_case

                st.session_state[
                    "prepared_feasible_evidence_traces"
                ] = prepared_feasible_evidence_traces

                st.session_state[
                    "prepared_semantic_review_signature"
                ] = current_semantic_review_signature

                st.session_state[
                    "prepared_feasible_review_signature"
                ] = current_feasible_review_signature

                st.session_state[
                    "formal_model_revision"
                ] += 1

                st.session_state[
                    "verification_result"
                ] = None

                st.session_state[
                    "verification_review_state"
                ] = None

                st.success(
                    "검증 모델 준비가 완료되었습니다."
                )

            except Exception as exc:
                st.error(
                    str(exc)
                )


# A prepared model must never survive changed R/V semantics,
# source-page review, F approval/source review, or stale input.
if (
    analysis is not None
    and role_completeness is not None
    and (
        not formalization_ready
        or (
            st.session_state[
                "prepared_semantic_review_signature"
            ]
            is not None
            and st.session_state[
                "prepared_semantic_review_signature"
            ]
            != current_semantic_review_signature
        )
        or (
            st.session_state[
                "prepared_feasible_review_signature"
            ]
            is not None
            and st.session_state[
                "prepared_feasible_review_signature"
            ]
            != current_feasible_review_signature
        )
    )
):
    if (
        st.session_state["mapped_analysis"]
        is not None
        or st.session_state["base_case"]
        is not None
    ):
        st.session_state[
            "mapped_analysis"
        ] = None

        st.session_state[
            "base_case"
        ] = None

        st.session_state[
            "verification_result"
        ] = None

        st.session_state[
            "verification_review_state"
        ] = None

        st.session_state[
            "prepared_semantic_review_signature"
        ] = None

        st.session_state[
            "prepared_feasible_review_signature"
        ] = None

        st.session_state[
            "formal_model_revision"
        ] += 1

        st.info(
            "Semantic Review 또는 Feasible Evidence Review가 "
            "변경되어 기존 Formal Model과 Verification Result를 "
            "무효화했습니다."
        )


# =========================================================
# PREPARED MODEL VIEW
# =========================================================

mapped_analysis = st.session_state[
    "mapped_analysis"
]

base_case = st.session_state[
    "base_case"
]


review_revision = st.session_state[
    "formal_model_revision"
]

current_reviewer_reference = str(
    st.session_state.get(
        "formal_reviewer_"
        + str(review_revision),
        "",
    )
)

current_review_confirmation = bool(
    st.session_state.get(
        "formal_review_confirmation_"
        + str(review_revision),
        False,
    )
)

if (
    st.session_state[
        "verification_result"
    ]
    is not None
    and has_review_state_changed(
        st.session_state[
            "verification_review_state"
        ],
        current_reviewer_reference,
        current_review_confirmation,
    )
):
    st.session_state[
        "verification_result"
    ] = None

    st.session_state[
        "verification_review_state"
    ] = None

    st.info(
        "Formal review state changed. "
        "The previous Verification result, "
        "Assurance Report, and Evidence Trace "
        "have been invalidated."
    )


if (
    mapped_analysis is not None
    and base_case is not None
):
    st.divider()

    st.header(
        "검증 모델 미리보기 (Verification Model)"
    )

    st.success(
        "Variable Mapping과 실제 가능한 범위(F)이 "
        "Formal Verification Workflow 입력으로 준비되었습니다."
    )

    st.subheader(
        "검증 모델 요약 (Engineering Model Summary)"
    )

    model_rows = []

    role_labels = {
        "requirement":
            "설계 요구조건 (Requirement)",
        "verification":
            "검사 기준 (Verification Criterion)",
    }

    for candidate in mapped_analysis.candidates:
        model_rows.append(
            {
                "구분": role_labels.get(
                    candidate.role,
                    candidate.role,
                ),
                "공학 모델": format_constraint(
                    candidate.extraction
                ),
                "참조": candidate.constraint_id,
            }
        )

    for variable_id, spec in (
        base_case.variables.items()
    ):
        model_rows.append(
            {
                "구분":
                    "현실 가능 범위 (실제 가능한 범위(F))",
                "공학 모델": (
                    f"{spec.feasible_min} ≤ "
                    f"{variable_id} ≤ "
                    f"{spec.feasible_max} "
                    f"{spec.unit}"
                ),
                "참조": (
                    spec.feasible_evidence
                    .source_reference
                    if spec.feasible_evidence
                    else "—"
                ),
            }
        )

    st.dataframe(
        model_rows,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Requirement와 Verification 값은 승인된 문서 추출 "
        "결과에서 자동으로 연결됩니다. 실제 가능한 범위(F)은 "
        "승인된 PDF Source-Bound Operating Evidence 또는 "
        "Engineer-Supplied Evidence에서 구성됩니다."
    )

    if (
        st.session_state[
            "verification_result"
        ]
        is None
    ):
        st.info(
            "Formal Human Review가 완료된 이후 "
            "Verification을 실행할 수 있습니다. "
            "현재 단계에서는 Solver가 실행되지 않습니다."
        )
    else:
        st.success(
            "이 Formal Model의 Verification이 "
            "완료되었습니다. 아래 결과와 Evidence "
            "Trace를 확인하세요."
        )



# =========================================================
# FORMAL HUMAN REVIEW + VERIFICATION
# =========================================================

if (
    mapped_analysis is not None
    and base_case is not None
    and role_completeness is not None
    and formalization_ready
):
    established_semantic_id_set = set(
        role_completeness
        .established_semantic_candidate_ids
    )

    approved_ids = [
        candidate.candidate_id
        for candidate
        in mapped_analysis.candidates
        if candidate.candidate_id
        in established_semantic_id_set
    ]

    try:
        grounded_semantic_result = (
            apply_grounded_semantic_approvals(
                base_case,
                mapped_analysis,
                approved_ids,
                semantic_role_grounding,
            )
        )

        if grounded_semantic_result.grounding_blocked:
            formal_ingress = None

            for grounding_issue in (
                grounded_semantic_result
                .grounding_gate
                .issues
            ):
                st.error(
                    "Role Grounding blocked · "
                    + grounding_issue
                )
        else:
            formal_ingress = (
                grounded_semantic_result
                .downstream_result
            )

    except Exception as exc:
        formal_ingress = None

        st.error(
            "Formal model assembly failed: "
            f"{exc}"
        )


    if formal_ingress is not None:
        if (
            formal_ingress.status
            != "READY_FOR_FORMAL_WORKFLOW"
        ):
            st.divider()

            st.header(
                "형식 검토 (Formal Human Review)"
            )

            st.error(
                "The semantic model is not ready "
                "for the formal verification workflow."
            )

            for issue in formal_ingress.issues:
                st.write(
                    "•",
                    issue,
                )

        else:
            required_targets = (
                build_required_review_targets(
                    formal_ingress.case
                )
            )

            st.divider()

            st.header(
                "형식 검토 (Formal Human Review)"
            )

            st.caption(
                "Solver 실행 전 독립적인 Formal Human Review가 "
                "필요합니다. AI 추출 결과의 승인만으로 형식 검증이 "
                "자동 실행되지는 않습니다."
            )

            st.subheader(
                "검토 요약 (Review Summary)"
            )

            review_rows = (
                build_review_summary_rows(
                    required_targets
                )
            )

            review_counts = {
                "Variable": 0,
                "Requirement": 0,
                "Verification": 0,
            }

            for row in review_rows:
                target_label = str(
                    row.get("Target", "")
                )

                for category in review_counts:
                    if target_label.startswith(
                        category
                    ):
                        review_counts[
                            category
                        ] += 1
                        break

            summary_total, summary_var, summary_req, summary_ver = (
                st.columns(4)
            )

            with summary_total:
                st.metric(
                    "전체 검토 항목",
                    len(review_rows),
                )

            with summary_var:
                st.metric(
                    "변수 정의",
                    review_counts["Variable"],
                )

            with summary_req:
                st.metric(
                    "설계 요구조건",
                    review_counts["Requirement"],
                )

            with summary_ver:
                st.metric(
                    "검사 기준",
                    review_counts["Verification"],
                )

            with st.expander(
                "세부 검토 항목 (Exact Review Targets)"
            ):
                st.dataframe(
                    review_rows,
                    width="stretch",
                    hide_index=True,
                )

            revision = st.session_state[
                "formal_model_revision"
            ]

            reviewer_reference = (
                st.text_input(
                    "검토자 참조 (Reviewer Reference)",
                    placeholder=(
                        "검토자 이름, ID 또는 추적 가능한 검토 참조"
                    ),
                    key=(
                        "formal_reviewer_"
                        + str(revision)
                    ),
                )
            )

            final_confirmation = (
                st.checkbox(
                    "검토 요약의 모든 항목을 확인하고 승인했습니다.",
                    key=(
                        "formal_review_confirmation_"
                        + str(revision)
                    ),
                )
            )

            reviewer_present = bool(
                reviewer_reference.strip()
            )

            if (
                final_confirmation
                and reviewer_present
            ):
                st.success(
                    "검토 완료 · Formal Verification을 실행할 수 있습니다."
                )

            else:
                st.info(
                    "검토자 참조와 최종 승인이 완료될 때까지 "
                    "Formal Verification은 실행되지 않습니다."
                )

            run_enabled = (
                bool(required_targets)
                and final_confirmation
                and reviewer_present
            )

            st.subheader(
                "검증 파이프라인 상태 "
                "(Verification Pipeline)"
            )

            pipeline_left, pipeline_right = (
                st.columns(2)
            )

            with pipeline_left:
                st.success(
                    "✓ 문서 근거 및 Source Provenance"
                )
                st.success(
                    "✓ 공학 의미 검토 (Semantic Review)"
                )
                st.success(
                    "✓ 변수 매핑 (Variable Mapping)"
                )

            with pipeline_right:
                st.success(
                    "✓ 현실 가능 범위 근거 "
                    "(실제 가능한 범위(F) Evidence)"
                )

                if run_enabled:
                    st.success(
                        "✓ 형식 검토 "
                        "(Formal Human Review)"
                    )
                    st.info(
                        "Deterministic Solver · Ready"
                    )
                else:
                    st.warning(
                        "○ 형식 검토 "
                        "(Formal Human Review) · 대기"
                    )
                    st.info(
                        "Deterministic Solver · Blocked"
                    )

            st.caption(
                "AI 추출 결과만으로 Solver가 실행되지 않습니다. "
                "문서 근거, 의미 검토, 변수 매핑, 현실 가능 범위와 "
                "Formal Human Review가 준비되어야 검증을 실행할 수 있습니다."
            )

            if st.button(
                "검증 실행 (Run Verification)",
                type="primary",
                disabled=not run_enabled,
            ):
                try:
                    review_records = (
                        build_exact_approved_review_records(
                            required_targets,
                            reviewer_reference,
                            final_confirmation,
                        )
                    )

                    with st.spinner(
                        "Executing assured formal "
                        "verification..."
                    ):
                        verification_result = (
                            run_verification_escape_workflow(
                                formal_ingress.case,
                                review_records,
                                evidence=(
                                    list(formal_ingress.evidence)
                                    + list(
                                        st.session_state["prepared_feasible_evidence_traces"]
                                    )
                                ),
                                generate_patches=False,
                            )
                        )

                    st.session_state[
                        "verification_result"
                    ] = verification_result

                    st.session_state[
                        "verification_review_state"
                    ] = build_review_state_signature(
                        reviewer_reference,
                        final_confirmation,
                    )

                    st.rerun()

                except Exception as exc:
                    st.error(
                        "Verification execution failed: "
                        f"{exc}"
                    )


# =========================================================
# VERIFICATION RESULT
# =========================================================

verification_result = st.session_state[
    "verification_result"
]


if verification_result is not None:
    st.divider()

    render_section_header(
        "STAGE 04",
        "Verification Result",
        "검토가 완료된 Formal Model에 대해 deterministic solver가 Verification Escape 여부와 witness를 판정합니다.",
    )
    render_soft_note(
        "AI가 결과를 결정하지 않습니다. 최종 판정은 승인된 Formal Model을 입력으로 하는 deterministic verification 결과입니다."
    )

    st.caption(
        "가장 최근에 준비되고 Formal Human Review를 통과한 "
        "검증 모델에 대한 결과입니다."
    )

    assured_result = (
        verification_result.assured_result
    )

    if not assured_result.core_executed:
        st.warning(
            "형식 검증이 실행되지 않았습니다."
        )

        st.write(
            "Workflow status:",
            verification_result.status,
        )

        human_review = getattr(
            assured_result,
            "human_review",
            None,
        )

        if human_review is not None:
            for issue in getattr(
                human_review,
                "issues",
                [],
            ):
                st.write(
                    f"• {issue.code}: "
                    f"{issue.message}"
                )

    else:
        pipeline = (
            assured_result.pipeline_result
        )

        if pipeline.has_escape:
            st.error(
                "⚠ 검증 이탈 발견 (Verification Escape Found)"
            )

            st.markdown(
                "**현재 검사 기준은 설계 요구조건을 위반하는 상태를 "
                "합격으로 판정할 수 있습니다.**"
            )

            st.caption(
                "아래 반례는 AI의 최종 판단이 아니라, "
                "검토된 공학 제약조건에 대해 Deterministic Solver가 "
                "계산한 Formal Counterexample입니다."
            )

            escape_count = 0

            for requirement_result in (
                pipeline.requirement_results
            ):
                stress_result = (
                    requirement_result.stress_result
                )

                if not stress_result.escape_found:
                    continue

                escape_count += 1

                with st.container(
                    border=True
                ):
                    st.subheader(
                        "반례 (Counterexample)"
                    )

                    state_rows = []

                    for (
                        variable_id,
                        value,
                    ) in stress_result.state.items():
                        variable_spec = (
                            verification_result.case
                            .variables.get(
                                variable_id
                            )
                        )

                        state_rows.append(
                            {
                                "Variable": (
                                    variable_id
                                ),
                                "Value": str(
                                    value
                                ),
                                "Unit": (
                                    variable_spec.unit
                                    if variable_spec
                                    is not None
                                    else "—"
                                ),
                            }
                        )

                    # A scalar case is shown once as the primary
                    # counterexample metric below. Multi-variable
                    # witnesses retain their complete state here.
                    if len(state_rows) > 1:
                        st.markdown(
                            "**반례 상태 (Counterexample State)**"
                        )

                        state_columns = st.columns(
                            min(len(state_rows), 3)
                        )

                        for row_index, row in enumerate(
                            state_rows
                        ):
                            column = state_columns[
                                row_index % len(
                                    state_columns
                                )
                            ]

                            unit_text = (
                                ""
                                if row["Unit"] == "—"
                                else " " + row["Unit"]
                            )

                            with column:
                                st.metric(
                                    row["Variable"],
                                    row["Value"]
                                    + unit_text,
                                )

                    st.markdown(
                        "**반례가 성립하는 이유**"
                    )

                    check_left, check_mid, check_right = (
                        st.columns(3)
                    )

                    with check_left:
                        st.success(
                            "현실 가능 범위 (실제 가능한 범위(F)) · PASS"
                        )

                    with check_mid:
                        st.success(
                            "검사 기준 (Verification Criterion) · PASS"
                        )

                    with check_right:
                        st.error(
                            "설계 요구조건 (Requirement) · FAIL"
                        )

                    requirement_spec = next(
                        (
                            requirement
                            for requirement
                            in verification_result
                            .case.requirements
                            if requirement.id
                            == stress_result.requirement_id
                        ),
                        None,
                    )

                    derived_value = None

                    if requirement_spec is not None:
                        derived_value = (
                            build_derived_value_view(
                                requirement_spec,
                                stress_result.actual_value,
                            )
                        )

                    result_left, result_mid, result_right = (
                        st.columns(3)
                    )

                    with result_left:
                        if derived_value is not None:
                            st.metric(
                                "반례 값 (Counterexample)",
                                derived_value.value,
                                help=(
                                    "Derived expression: "
                                    + derived_value.expression
                                ),
                            )

                    with result_mid:
                        if (
                            stress_result.worst_violation
                            is not None
                        ):
                            st.metric(
                                "요구조건 위반량 (Violation)",
                                format_value_with_unit(
                                    stress_result.worst_violation,
                                    (
                                        requirement_spec.unit
                                        if requirement_spec
                                        is not None
                                        else None
                                    ),
                                ),
                            )

                    with result_right:
                        if (
                            stress_result.direction
                            is not None
                        ):
                            direction_display = (
                                format_code_label(
                                    stress_result.direction
                                )
                            )

                            direction_display = {
                                "Above Maximum":
                                    "허용 상한 초과 "
                                    "(Above Maximum)",
                                "Below Minimum":
                                    "허용 하한 미달 "
                                    "(Below Minimum)",
                                "Exceeds Limit":
                                    "허용 한계 초과 "
                                    "(Exceeds Limit)",
                            }.get(
                                direction_display,
                                direction_display,
                            )

                            st.metric(
                                "위반 방향 (Direction)",
                                direction_display,
                            )

                    with st.expander(
                        "고급 정보 (Advanced) · Formal Verification"
                    ):
                        st.code(
                            "F(x) ∧ V(x) ∧ ¬R(x)",
                            language=None,
                        )
                        st.caption(
                            "Requirement ID · "
                            + stress_result.requirement_id
                        )
                        st.caption(
                            "Pipeline status · "
                            + str(pipeline.status)
                        )

            if (
                getattr(
                    pipeline,
                    "has_solver_indeterminate",
                    False,
                )
            ):
                st.warning(
                    "One or more additional "
                    "requirements were indeterminate."
                )

        elif getattr(
            pipeline,
            "has_solver_indeterminate",
            False,
        ):
            st.warning(
                "판정 불확정 (INDETERMINATE)"
            )

            st.markdown(
                "하나 이상의 요구조건에서 검증 이탈 여부를 "
                "확정할 수 없었습니다. 이 상태를 "
                "No Escape로 간주하지 않습니다."
            )

        elif (
            pipeline.status
            == "NO_ESCAPE_FOUND"
        ):
            st.success(
                "검증 이탈이 발견되지 않았습니다 "
                "(No Verification Escape Found)"
            )

            st.markdown(
                "모델링된 현실 가능 범위 안에서 "
                "검사 기준을 통과하면서 설계 요구조건을 "
                "위반하는 반례가 발견되지 않았습니다."
            )

            st.caption(
                "이 결과는 현재 모델링된 Requirement, "
                "Verification Criterion, 실제 가능한 범위(F) 및 "
                "지원되는 분석 범위에 한정됩니다. "
                "제품 안전성에 대한 최종 판정이 아닙니다."
            )

        else:
            st.warning(
                "Verification completed with status: "
                + str(
                    pipeline.status
                )
            )


    gap_classification = getattr(
        verification_result,
        "gap_classification",
        None,
    )

    if gap_classification is not None:
        st.subheader(
            "검증 격차 분류 (Gap Classification)"
        )

        gap_label_ko = {
            "Acceptance Boundary Gap":
                "허용 경계 누락",
            "Relational Acceptance Boundary Gap":
                "관계형 허용 경계 격차",
            "Coverage Gap":
                "검증 범위 누락",
        }

        gap_explanation_ko = {
            "Acceptance Boundary Gap": (
                "검사 기준이 설계 요구조건보다 넓은 허용 범위를 "
                "인정하여 요구조건의 경계 일부가 검사에서 "
                "검증되지 않습니다."
            ),
            "Relational Acceptance Boundary Gap": (
                "변수 간 관계에 대한 검사 허용 경계가 "
                "설계 요구조건보다 넓어 관계형 요구조건 위반이 "
                "검사를 통과할 수 있습니다."
            ),
            "Coverage Gap": (
                "설계 요구조건을 직접 확인하는 검사 기준이 없어 "
                "해당 요구조건 위반이 검증 범위에서 누락됩니다."
            ),
        }

        for item in gap_classification.items:
            korean_label = gap_label_ko.get(
                item.display_label,
                "검증 격차",
            )

            with st.container(border=True):
                st.markdown(
                    "### "
                    + korean_label
                )

                if item.display_label:
                    st.caption(
                        item.display_label
                    )

                korean_explanation = (
                    gap_explanation_ko.get(
                        item.display_label
                    )
                )

                if korean_explanation:
                    st.write(
                        korean_explanation
                    )
                elif item.rationale:
                    st.write(
                        item.rationale
                    )

                if item.rationale:
                    with st.expander(
                        "분류 근거 원문 (Advanced)"
                    ):
                        st.write(
                            item.rationale
                        )

        with st.expander(
            "고급 정보 (Advanced) · "
            "Gap Classification"
        ):
            st.caption(
                "Report Status · "
                + format_code_label(
                    gap_classification.status
                )
            )
            st.json(
                gap_classification.to_dict()
            )


    with st.expander(
        "고급 정보 (Advanced) · Assurance Report"
    ):
        rendered_report = getattr(
            verification_result,
            "rendered_report",
            None,
        )

        if rendered_report:
            st.code(
                rendered_report,
                language=None,
            )

        else:
            st.write(
                "No rendered assurance report "
                "is available."
            )


    st.subheader(
        "근거 문서 (Evidence Trace)"
    )

    st.caption(
        "검증 모델과 결과가 어떤 원문 근거에서 "
        "형성되었는지 추적합니다."
    )

    evidence_items = getattr(
        verification_result,
        "evidence",
        [],
    )

    if not evidence_items:
        st.info(
            "표시할 Evidence Trace가 없습니다."
        )

    evidence_role_labels = {
        "requirement":
            "설계 요구조건 (Requirement)",
        "verification":
            "검사 기준 (Verification Criterion)",
        "feasible_domain":
            "현실 가능 근거 (Feasible Evidence)",
    }

    for evidence in evidence_items:
        pages = evidence.source_pages

        if (
            not pages
            and evidence.source_page is not None
        ):
            pages = (
                evidence.source_page,
            )

        if evidence.role == "feasible_domain":
            with st.container(border=True):
                st.markdown(
                    "#### 엔지니어 입력 운영 근거 "
                    "(Engineer-Supplied Operating Evidence)"
                )

                variable_spec = (
                    verification_result.case
                    .variables.get(
                        evidence.target_id
                    )
                )

                if variable_spec is not None:
                    st.markdown(
                        "**현실 가능 범위 (실제 가능한 범위(F))**"
                    )
                    st.markdown(
                        "### "
                        + str(
                            variable_spec.feasible_min
                        )
                        + " ≤ "
                        + evidence.target_id
                        + " ≤ "
                        + str(
                            variable_spec.feasible_max
                        )
                        + " "
                        + str(
                            variable_spec.unit
                        )
                    )

                st.caption(
                    "근거 참조 · "
                    + str(
                        evidence.source_reference
                        or evidence.source_name
                    )
                )

                if evidence.analysis_scope is not None:
                    st.caption(
                        "Analysis Scope · "
                        + format_code_label(
                            evidence.analysis_scope
                        )
                    )

                if evidence.vision_processed_page_numbers:
                    st.caption(
                        "Vision Analyzed Pages · "
                        + ", ".join(
                            str(page)
                            for page
                            in evidence
                            .vision_processed_page_numbers
                        )
                    )

                if (
                    evidence
                    .vision_unprocessed_candidate_page_numbers
                ):
                    st.caption(
                        "Unprocessed Candidate Pages · "
                        + ", ".join(
                            str(page)
                            for page
                            in evidence
                            .vision_unprocessed_candidate_page_numbers
                        )
                    )

                if (
                    evidence.analysis_scope
                    == "SELECTED_PAGES"
                ):
                    st.warning(
                        "This Feasible Evidence was derived "
                        "from selected PDF pages. Candidate "
                        "pages listed as unprocessed were not "
                        "included in the high-detail analysis."
                    )

                st.info(
                    "이 실제 가능한 범위(F)은 Operating Evidence에서 "
                    "추출된 후보를 엔지니어가 검토·승인한 후 "
                    "Formal Model에 적용한 값입니다. "
                    "AI extraction alone does not authorize F."
                )

                with st.expander(
                    "추적 세부정보 (Advanced)"
                ):
                    st.caption(
                        "Target ID · "
                        + evidence.target_id
                    )
                    st.write(
                        evidence.source_text
                    )

            continue

        role_label = {
            "requirement":
                "설계 요구조건 (Requirement)",
            "verification":
                "검사 기준 (Verification Criterion)",
        }.get(
            evidence.role,
            format_code_label(
                evidence.role
            ),
        )

        with st.container(border=True):
            st.markdown(
                "#### " + role_label
            )

            source_line = evidence.source_name

            if pages:
                source_line += (
                    " · Page "
                    + ", ".join(
                        str(page)
                        for page in pages
                    )
                )

            st.caption(
                source_line
            )

            st.markdown(
                "**원문 근거**"
            )
            st.write(
                evidence.source_text
            )

            with st.expander(
                "추적 세부정보 (Advanced)"
            ):
                st.caption(
                    "Target ID · "
                    + evidence.target_id
                )

                if evidence.source_reference:
                    st.caption(
                        "Source Reference · "
                        + evidence.source_reference
                    )

                if evidence.source_block_id:
                    st.caption(
                        "Source Block · "
                        + evidence.source_block_id
                    )

                if evidence.source_sha256:
                    st.caption(
                        "SHA-256 · "
                        + evidence.source_sha256
                    )

                if evidence.source_location_status:
                    st.caption(
                        "Source Location · "
                        + format_code_label(
                            evidence.source_location_status
                        )
                    )

    with st.expander(
        "고급 정보 (Advanced) · Raw Verification Data"
    ):
        st.json(
            verification_result.to_dict()
        )
