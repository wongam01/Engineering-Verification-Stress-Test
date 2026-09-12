import hashlib
import re
from copy import deepcopy

import streamlit as st

from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
    apply_semantic_approvals,
    build_semantic_documents_signature,
    build_semantic_review_signature,
    confirm_ambiguous_source_location,
)
from src.application.pdf_ingress import (
    build_pdf_page_preview,
    build_semantic_document,
    ingest_pdf_document,
    pdf_document_can_attempt_vision,
    pdf_document_requires_vision,
    prepare_pdf_document_for_semantic_analysis,
    validate_pdf_document_set,
)
from src.ai.pdf_page_vision import (
    extract_pdf_page_with_vision,
)
from src.application.feasible_evidence_ingress import (
    analyze_feasible_evidence_pdf,
    build_feasible_evidence_prefills,
    confirm_ambiguous_feasible_source_location,
)
from src.application.evidence_trace import (
    build_source_reference,
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


st.set_page_config(
    page_title=(
        "공학 검증 스트레스 테스트"
    ),
    layout="wide",
)

st.title(
    "공학 검증 스트레스 테스트"
)

st.caption(
    "Engineering Verification Stress Test · "
    "Document Evidence → Engineering Semantics "
    "→ Formal Counterexample"
)

st.markdown(
    "**① 문서 입력**  →  "
    "**② 공학 데이터 추출**  →  "
    "**③ 검증 모델 및 검토**  →  "
    "**④ 검증 결과**"
)

st.caption(
    "PDF 무결성 · Source Provenance · Semantic Review · "
    "Variable Mapping · Feasible Domain · "
    "Scope / Assurance · Formal Human Review · "
    "Deterministic Solver"
)


# =========================================================
# HELPERS
# =========================================================

def safe_key(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:10]


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
# SESSION STATE
# =========================================================

for key, default in {
    "semantic_analysis": None,
    "analysis_signature": None,
    "feasible_analysis": None,
    "feasible_approved_candidate_ids": [],
    "mapped_analysis": None,
    "base_case": None,
    "verification_result": None,
    "verification_review_state": None,
    "prepared_semantic_review_signature": None,
    "prepared_feasible_review_signature": None,
    "vision_prepared_pdf_documents": {},
    "vision_prepared_pdf_signature": None,
    "formal_model_revision": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# =========================================================
# STEP 1 — DOCUMENTS
# =========================================================

st.header(
    "1 · 문서 입력 (Documents)"
)

input_mode = st.radio(
    "문서 입력 방식",
    [
        "PDF Upload",
        "Text Input",
    ],
    horizontal=True,
    format_func=lambda mode: {
        "PDF Upload": "PDF 업로드",
        "Text Input": "텍스트 입력",
    }[mode],
)

documents = []
pdf_documents = []
source_pdfs = {}
feasible_pdf_document = None
document_input_ready = False
pdf_input_signature = None

left, right = st.columns(2)

if input_mode == "PDF Upload":
    with left:
        st.subheader(
            "설계 요구조건 문서 (Requirement PDF)"
        )
        requirement_upload = st.file_uploader(
            "Requirement PDF 업로드",
            type=["pdf"],
            key="requirement_pdf_upload",
        )

    with right:
        st.subheader(
            "검사 기준 문서 (Verification PDF)"
        )
        verification_upload = st.file_uploader(
            "Verification PDF 업로드",
            type=["pdf"],
            key="verification_pdf_upload",
        )

    st.divider()

    st.subheader(
        "운영 근거 문서 (Operating Evidence PDF)"
    )

    st.caption(
        "관측·시험·생산·운영 데이터에서 현실 가능 범위 "
        "(Feasible Domain) 후보를 추출합니다. "
        "Engineer Approval 전에는 Formal Model에 적용되지 않습니다."
    )

    feasible_upload = st.file_uploader(
        "Operating Evidence PDF 업로드",
        type=["pdf"],
        key="feasible_pdf_upload",
    )

    feasible_status = st.container()

    uploads = [
        (
            "requirement",
            requirement_upload,
        ),
        (
            "verification",
            verification_upload,
        ),
        (
            "feasible",
            feasible_upload,
        ),
    ]

    for role, upload in uploads:
        if upload is None:
            continue

        pdf_document = ingest_pdf_document(
            role=role,
            filename=upload.name,
            content=upload.getvalue(),
        )

        cache_key = (
            role
            + ":"
            + pdf_document.content_sha256
        )

        cached_pdf_document = (
            st.session_state[
                "vision_prepared_pdf_documents"
            ].get(cache_key)
        )

        if cached_pdf_document is not None:
            pdf_document = cached_pdf_document

        pdf_documents.append(pdf_document)

        if role == "requirement":
            container = left
        elif role == "verification":
            container = right
        else:
            container = feasible_status

        with container:
            if pdf_document.ready_for_semantic_analysis:
                st.success(
                    f"{pdf_document.filename} · "
                    f"{pdf_document.total_pages} page(s)"
                )
                with st.expander(
                    "문서 세부정보 (Advanced)"
                ):
                    st.caption(
                        "SHA-256 · "
                        + pdf_document.content_sha256
                    )
                    st.caption(
                        "Role · " + pdf_document.role
                    )
                    st.caption(
                        "Pages · "
                        + str(pdf_document.total_pages)
                    )
            else:
                if (
                    pdf_document_requires_vision(
                        pdf_document
                    )
                    and pdf_document_can_attempt_vision(
                        pdf_document
                    )
                ):
                    st.info(
                        f"{pdf_document.filename} · "
                        "Scanned/image-only page(s) detected. "
                        "Vision analysis will run when "
                        "Analyze Documents is selected."
                    )
                else:
                    st.error(
                        "PDF ingestion blocked · "
                        + pdf_document.status
                    )

            for issue in pdf_document.issues:
                if issue.severity == "ERROR":
                    st.error(
                        f"{issue.code} · {issue.message}"
                    )
                else:
                    st.warning(
                        f"{issue.code} · {issue.message}"
                    )

    if pdf_documents:
        pdf_input_signature = hashlib.sha256(
            "\n".join(
                (
                    document.role
                    + ":"
                    + document.content_sha256
                )
                for document in pdf_documents
            ).encode("utf-8")
        ).hexdigest()

    document_set_validation = (
        validate_pdf_document_set(
            pdf_documents
        )
    )

    for issue in document_set_validation.issues:
        if issue.code == "PDF_DOCUMENT_NOT_READY":
            continue

        if issue.severity == "ERROR":
            st.error(
                f"{issue.code} · {issue.message}"
            )
        else:
            st.warning(
                f"{issue.code} · {issue.message}"
            )

    pdf_roles = {
        document.role
        for document in pdf_documents
    }

    required_pdf_roles = {
        "requirement",
        "verification",
    }

    blocking_document_set_issue = any(
        issue.severity == "ERROR"
        and issue.code != "PDF_DOCUMENT_NOT_READY"
        for issue in document_set_validation.issues
    )

    documents_supported_for_analysis = all(
        (
            document.ready_for_semantic_analysis
            or (
                pdf_document_requires_vision(
                    document
                )
                and pdf_document_can_attempt_vision(
                    document
                )
            )
        )
        for document in pdf_documents
    )

    document_input_ready = (
        required_pdf_roles.issubset(
            pdf_roles
        )
        and not blocking_document_set_issue
        and documents_supported_for_analysis
    )

    pdf_documents_fully_prepared = (
        document_input_ready
        and all(
            document.ready_for_semantic_analysis
            and not pdf_document_requires_vision(
                document
            )
            for document in pdf_documents
        )
    )

    if pdf_documents_fully_prepared:
        documents = [
            build_semantic_document(document)
            for document in pdf_documents
            if document.role in {
                "requirement",
                "verification",
            }
        ]

        feasible_pdf_document = next(
            (
                document
                for document in pdf_documents
                if document.role == "feasible"
            ),
            None,
        )

        source_pdfs = {
            (
                document.role,
                document.content_sha256,
            ): document
            for document in pdf_documents
        }

    elif not required_pdf_roles.issubset(
        pdf_roles
    ):
        st.info(
            "Requirement PDF와 Verification PDF를 "
            "모두 업로드해 주세요. "
            "Operating Evidence PDF는 선택사항입니다."
        )

    elif document_input_ready:
        st.info(
            "Scanned/image-only PDF page(s) are ready "
            "for Vision analysis. "
            "Select Analyze Documents to continue."
        )

else:
    with left:
        st.subheader(
            "Engineering Requirement"
        )
        requirement_text = st.text_area(
            "Requirement document text",
            height=220,
            placeholder=(
                "R1. Hardness H shall be between "
                "50 HRC and 57 HRC inclusive."
            ),
        )

    with right:
        st.subheader(
            "Verification / Inspection"
        )
        verification_text = st.text_area(
            "Verification document text",
            height=220,
            placeholder=(
                "V1. The inspection accepts the part "
                "when hardness H is at least 50 HRC."
            ),
        )

    if requirement_text.strip():
        documents.append(
            SemanticDocument(
                role="requirement",
                source_name="requirement_input",
                text=requirement_text,
            )
        )

    if verification_text.strip():
        documents.append(
            SemanticDocument(
                role="verification",
                source_name="verification_input",
                text=verification_text,
            )
        )

    document_input_ready = bool(documents)


semantic_documents_signature = (
    build_semantic_documents_signature(
        documents
    )
    if documents
    else None
)

feasible_document_sha256 = (
    feasible_pdf_document.content_sha256
    if feasible_pdf_document is not None
    else None
)

current_signature = (
    hashlib.sha256(
        (
            (semantic_documents_signature or "")
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
    "문서 분석 시작 (Analyze Documents)",
    type="primary",
):
    if not document_input_ready:
        st.warning(
            "분석할 Requirement와 Verification 문서를 확인해 주세요."
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
                    pdf_document_requires_vision(
                        document
                    )
                    for document in pdf_documents
                ):
                    with st.spinner(
                        "스캔 페이지를 Vision AI로 "
                        "분석하고 있습니다..."
                    ):
                        prepared_pdf_documents = [
                            (
                                prepare_pdf_document_for_semantic_analysis(
                                    document,
                                    vision_page_extractor=(
                                        vision_page_extractor
                                    ),
                                )
                                if pdf_document_requires_vision(
                                    document
                                )
                                else document
                            )
                            for document in pdf_documents
                        ]

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

                feasible_pdf_document = next(
                    (
                        document
                        for document
                        in pdf_documents
                        if document.role
                        == "feasible"
                    ),
                    None,
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
                    feasible_pdf_document
                    .content_sha256
                    if feasible_pdf_document
                    is not None
                    else None
                )

                current_signature = (
                    hashlib.sha256(
                        (
                            semantic_documents_signature
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
                analysis = (
                    analyze_semantic_documents(
                        documents
                    )
                )

                feasible_analysis = (
                    analyze_feasible_evidence_pdf(
                        feasible_pdf_document
                    )
                    if feasible_pdf_document
                    is not None
                    else None
                )

            for state_key in list(
                st.session_state.keys()
            ):
                if state_key.startswith((
                    "semantic_approval_",
                    "source_location_page_",
                    "source_location_confirm_",
                    "feasible_approval_",
                    "feasible_source_location_page_",
                    "feasible_source_location_confirm_",
                )):
                    del st.session_state[
                        state_key
                    ]

            st.session_state[
                "formal_model_revision"
            ] += 1

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


# =========================================================
# STEP 2 — SEMANTIC REVIEW
# =========================================================

if analysis is not None:
    st.divider()

    st.header(
        "2 · 공학 데이터 추출 (Engineering Extraction)"
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
            "Candidate를 사용하기 전에 Analyze Documents를 다시 실행해 주세요."
        )

    # -----------------------------------------------------
    # Feasible Evidence Candidate Review
    # -----------------------------------------------------

    feasible_approved_candidate_ids = []

    if feasible_analysis is not None:
        st.subheader(
            "운영 근거 추출 결과 "
            "(Feasible Evidence Candidates)"
        )

        st.caption(
            "AI는 후보만 제안합니다. PDF 원문 위치와 의미를 "
            "확인한 뒤 Engineer Approval이 있어야 다음 단계에서 "
            "Feasible Domain 입력 후보로 사용할 수 있습니다."
        )

        feasible_analysis = deepcopy(
            feasible_analysis
        )

        if not feasible_analysis.candidates:
            st.info(
                "이 Operating Evidence PDF에서 지원 가능한 "
                "Feasible Domain 후보를 찾지 못했습니다."
            )

        for feasible_index, feasible_candidate in enumerate(
            feasible_analysis.candidates,
            start=1,
        ):
            extraction = (
                feasible_candidate.extraction
            )

            with st.container(
                border=True
            ):
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
                        "#### 추출된 현실 가능 범위"
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

                    eligible_for_approval = (
                        analysis_is_current
                        and feasible_candidate
                        .source_location_ready
                        and not needs_review
                    )

                    approved = st.checkbox(
                        "이 Operating Evidence를 "
                        "Feasible Domain 후보로 승인합니다.",
                        key=(
                            "feasible_approval_"
                            + safe_key(
                                feasible_candidate
                                .candidate_id
                            )
                        ),
                        disabled=(
                            not eligible_for_approval
                        ),
                    )

                    if approved:
                        feasible_approved_candidate_ids.append(
                            feasible_candidate
                            .candidate_id
                        )

        st.session_state[
            "feasible_analysis"
        ] = feasible_analysis

        st.session_state[
            "feasible_approved_candidate_ids"
        ] = feasible_approved_candidate_ids

        if feasible_approved_candidate_ids:
            st.success(
                "승인된 Operating Evidence 후보 · "
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

    approved_candidate_ids = []
    analysis = deepcopy(analysis)

    for index, candidate in enumerate(
        analysis.candidates,
        start=1,
    ):
        role_label = (
            "설계 요구조건 (Requirement)"
            if candidate.role
            == "requirement"
            else "검사 기준 (Verification Criterion)"
        )

        with st.container(
            border=True
        ):
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

                if (
                    candidate.adapter_accepted
                    and candidate.source_location_ready
                ):
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

                approved = st.checkbox(
                    "이 공학 의미 해석을 승인합니다",
                    key=(
                        "semantic_approval_"
                        + candidate.candidate_id
                    ),
                    disabled=(
                        not candidate.adapter_accepted
                        or not candidate.source_location_ready
                        or not analysis_is_current
                    ),
                )

                if (
                    approved
                    and candidate.adapter_accepted
                    and candidate.source_location_ready
                ):
                    approved_candidate_ids.append(
                        candidate.candidate_id
                    )

    all_semantics_approved = (
        analysis_is_current
        and bool(
            analysis.candidates
        )
        and len(
            approved_candidate_ids
        )
        == len(
            analysis.candidates
        )
    )

    current_semantic_review_signature = (
        build_semantic_review_signature(
            analysis,
            approved_candidate_ids,
        )
    )

    if all_semantics_approved:
        st.success(
            "추출 결과 검토가 완료되었습니다."
        )

    else:
        st.info(
            "모든 Semantic Candidate를 "
            "검토하고 승인해야 다음 단계로 "
            "진행할 수 있습니다."
        )


    # =====================================================
    # STEP 3 — VARIABLE MAPPING + FEASIBLE DOMAIN
    # =====================================================

    if all_semantics_approved:
        st.divider()

        st.header(
            "3 · 검증 모델 및 검토 (Verification Model & Review)"
        )

        st.caption(
            "추출된 공학 변수를 검토하고 현실 가능 범위 "
            "(Feasible Domain)를 공학적 근거와 함께 확인합니다."
        )

        targets = (
            build_variable_mapping_targets(
                analysis
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
            st.session_state[
                "feasible_approved_candidate_ids"
            ]
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
                        "(Feasible Domain Review)"
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
                        "**Formal Feasible Domain** · "
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
                        "Feasible Domain"
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
                errors = list(
                    feasible_binding_errors
                )

                approved_feasible_ids = set(
                    st.session_state[
                        "feasible_approved_candidate_ids"
                    ]
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

                    feasible_prefill_result = (
                        build_feasible_evidence_prefills(
                            selected_feasible_analysis,
                            approved_candidate_ids=sorted(
                                approved_feasible_ids
                            ),
                            canonical_variable_by_candidate=(
                                canonical_variable_by_candidate
                            ),
                        )
                    )

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
                        analysis,
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
                            "서로 다른 Feasible Domain "
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
    and "all_semantics_approved" in locals()
    and (
        not all_semantics_approved
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
        "Variable Mapping과 Feasible Domain이 "
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
                    "현실 가능 범위 (Feasible Domain)",
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
        "결과에서 자동으로 연결됩니다. Feasible Domain은 "
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
):
    approved_ids = [
        candidate.candidate_id
        for candidate
        in mapped_analysis.candidates
    ]

    try:
        formal_ingress = (
            apply_semantic_approvals(
                base_case,
                mapped_analysis,
                approved_ids,
            )
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
                    "(Feasible Domain Evidence)"
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
                                    formal_ingress.evidence
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

    st.header(
        "4 · 검증 결과 (Verification Result)"
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
                            "현실 가능 범위 (Feasible Domain) · PASS"
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
                "Verification Criterion, Feasible Domain 및 "
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
        "feasible":
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

        if evidence.role == "feasible":
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
                        "**현실 가능 범위 (Feasible Domain)**"
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

                st.info(
                    "현재 Phase 5B-0에서는 F가 PDF에서 자동 "
                    "추출된 값이 아닙니다. 엔지니어가 입력하고 "
                    "근거 기반임을 확인한 Operating Evidence입니다."
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
