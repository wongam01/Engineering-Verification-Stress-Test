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
    validate_pdf_document_set,
)
from src.application.result_presentation import (
    build_derived_value_view,
    build_gap_classification_rows,
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
        "Engineering Verification Stress Test"
    ),
    layout="wide",
)

st.title(
    "Engineering Verification Stress Test"
)

st.caption(
    "Document Evidence → Engineering Semantics "
    "→ Formal Counterexample"
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


# =========================================================
# SESSION STATE
# =========================================================

for key, default in {
    "semantic_analysis": None,
    "analysis_signature": None,
    "mapped_analysis": None,
    "base_case": None,
    "verification_result": None,
    "verification_review_state": None,
    "prepared_semantic_review_signature": None,
    "formal_model_revision": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# =========================================================
# STEP 1 — DOCUMENTS
# =========================================================

st.header(
    "1 · Engineering Documents"
)

input_mode = st.radio(
    "Document input method",
    [
        "PDF Upload",
        "Text Input",
    ],
    horizontal=True,
)

documents = []
pdf_documents = []
source_pdfs = {}
document_input_ready = False

left, right = st.columns(2)

if input_mode == "PDF Upload":
    with left:
        st.subheader(
            "Engineering Requirement PDF"
        )
        requirement_upload = st.file_uploader(
            "Upload Requirement PDF",
            type=["pdf"],
            key="requirement_pdf_upload",
        )

    with right:
        st.subheader(
            "Verification / Inspection PDF"
        )
        verification_upload = st.file_uploader(
            "Upload Verification PDF",
            type=["pdf"],
            key="verification_pdf_upload",
        )

    uploads = [
        (
            "requirement",
            requirement_upload,
        ),
        (
            "verification",
            verification_upload,
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
        pdf_documents.append(pdf_document)

        container = left if role == "requirement" else right

        with container:
            if pdf_document.ready_for_semantic_analysis:
                st.success(
                    f"{pdf_document.filename} · "
                    f"{pdf_document.total_pages} page(s)"
                )
                st.caption(
                    "SHA-256 · "
                    + pdf_document.content_sha256
                )
            else:
                st.error(
                    f"PDF ingestion blocked · {pdf_document.status}"
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

    document_input_ready = (
        len(pdf_documents) == 2
        and document_set_validation.valid
        and all(
            document.ready_for_semantic_analysis
            for document in pdf_documents
        )
    )

    if document_input_ready:
        documents = [
            build_semantic_document(document)
            for document in pdf_documents
        ]
        source_pdfs = {
            (
                document.role,
                document.content_sha256,
            ): document
            for document in pdf_documents
        }
    elif len(pdf_documents) < 2:
        st.info(
            "Requirement PDF와 Verification PDF를 모두 업로드해 주세요."
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


current_signature = (
    build_semantic_documents_signature(
        documents
    )
    if documents
    else None
)


if st.button(
    "Analyze Documents",
    type="primary",
):
    if not document_input_ready:
        st.warning(
            "분석할 Requirement와 Verification 문서를 확인해 주세요."
        )

    else:
        try:
            with st.spinner(
                "Engineering semantics 분석 중..."
            ):
                analysis = (
                    analyze_semantic_documents(
                        documents
                    )
                )

            for state_key in list(
                st.session_state.keys()
            ):
                if state_key.startswith((
                    "semantic_approval_",
                    "source_location_page_",
                    "source_location_confirm_",
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
                "semantic_analysis"
            ] = analysis

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


# =========================================================
# STEP 2 — SEMANTIC REVIEW
# =========================================================

if analysis is not None:
    st.divider()

    st.header(
        "2 · Extracted Engineering Semantics"
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

    approved_candidate_ids = []
    analysis = deepcopy(analysis)

    for index, candidate in enumerate(
        analysis.candidates,
        start=1,
    ):
        role_label = (
            "Requirement"
            if candidate.role
            == "requirement"
            else "Verification"
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
                    "Source Evidence"
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
                    st.caption(
                        "SHA-256 · "
                        + candidate.source_sha256
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
                    try:
                        st.pdf(
                            build_pdf_page_preview(
                                pdf_document,
                                preview_page,
                            ),
                            height=480,
                            key=(
                                "pdf_preview_"
                                + safe_key(
                                    candidate.candidate_id
                                    + ":"
                                    + str(preview_page)
                                )
                            ),
                        )

                        page_record = (
                            pdf_document.page(
                                preview_page
                            )
                        )

                        if page_record is not None:
                            with st.expander(
                                "Extracted page text"
                            ):
                                st.code(
                                    page_record.text,
                                    language=None,
                                )
                    except Exception as exc:
                        st.error(
                            "PDF page preview failed: "
                            + str(exc)
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
                        "Ready for review"
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
                    "Advanced · Raw extraction"
                ):
                    st.json(
                        candidate.extraction
                    )

                approved = st.checkbox(
                    "Approve this semantic interpretation",
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
            "Semantic review complete."
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
            "3 · Variables & Feasible Domain / "
            "Engineer-Supplied Operating Evidence"
        )

        st.caption(
            "AI가 추출한 문서 변수명을 "
            "Canonical Variable ID에 연결하고, "
            "현실적으로 가능한 상태 범위를 "
            "근거 자료와 함께 입력해 주세요."
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

            with st.container(
                border=True
            ):
                st.subheader(
                    source_variable
                )

                st.caption(
                    "Source variable extracted "
                    "from the document"
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

                col1, col2 = (
                    st.columns(2)
                )

                with col1:
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

                    unit = st.text_input(
                        "Engineering Unit",
                        value=default_unit,
                        key=(
                            "unit_"
                            + key
                        ),
                    )

                with col2:
                    feasible_min = (
                        st.text_input(
                            "Feasible Minimum",
                            placeholder="예: 58",
                            key=(
                                "fmin_"
                                + key
                            ),
                        )
                    )

                    feasible_max = (
                        st.text_input(
                            "Feasible Maximum",
                            placeholder="예: 60",
                            key=(
                                "fmax_"
                                + key
                            ),
                        )
                    )

                evidence_type = (
                    st.selectbox(
                        "Feasible Domain Evidence Type",
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
                        "Evidence Reference",
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
                        "I confirm this Feasible "
                        "Domain is evidence-backed.",
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
                }

        if st.button(
            "Prepare Formal Model",
            type="primary",
        ):
            try:
                errors = []

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
                                "Engineer-confirmed "
                                "through Application UI."
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
                    "formal_model_revision"
                ] += 1

                st.session_state[
                    "verification_result"
                ] = None

                st.session_state[
                    "verification_review_state"
                ] = None

                st.success(
                    "Formal model preparation complete."
                )

            except Exception as exc:
                st.error(
                    str(exc)
                )


# A prepared model must never survive a changed semantic approval,
# source-page review, or stale document analysis.
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
            "formal_model_revision"
        ] += 1

        st.info(
            "Semantic approval or source-location review changed. "
            "The prepared formal model has been invalidated."
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
        "4 · Prepared Formal Model"
    )

    st.success(
        "Variable Mapping과 Feasible Domain이 "
        "Formal Verification Workflow 입력으로 준비되었습니다."
    )

    mapping_rows = []

    for candidate in (
        mapped_analysis.candidates
    ):
        mapping_rows.append(
            {
                "Role": candidate.role,
                "Constraint": (
                    candidate.constraint_id
                ),
                "Formal Semantics": (
                    format_constraint(
                        candidate.extraction
                    )
                ),
            }
        )

    st.dataframe(
        mapping_rows,
        width="stretch",
        hide_index=True,
    )

    feasible_rows = []

    for variable_id, spec in (
        base_case.variables.items()
    ):
        feasible_rows.append(
            {
                "Variable": variable_id,
                "Unit": spec.unit,
                "Feasible Min": (
                    str(
                        spec.feasible_min
                    )
                ),
                "Feasible Max": (
                    str(
                        spec.feasible_max
                    )
                ),
                "Evidence": (
                    spec.feasible_evidence
                    .source_reference
                    if spec.feasible_evidence
                    else "—"
                ),
            }
        )

    st.subheader(
        "Feasible Domain / Engineer-Supplied Operating Evidence"
    )

    st.dataframe(
        feasible_rows,
        width="stretch",
        hide_index=True,
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
                "5 · Formal Human Review"
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
                "5 · Formal Human Review"
            )

            st.caption(
                "Engineering review must be completed "
                "before solver execution. "
                "Semantic approval alone does not "
                "authorize formal verification."
            )

            st.subheader(
                "Review Summary"
            )

            st.dataframe(
                build_review_summary_rows(
                    required_targets
                ),
                width="stretch",
                hide_index=True,
            )

            revision = st.session_state[
                "formal_model_revision"
            ]

            reviewer_reference = (
                st.text_input(
                    "Reviewer Reference",
                    placeholder=(
                        "Reviewer name, employee ID, "
                        "or traceable review reference"
                    ),
                    key=(
                        "formal_reviewer_"
                        + str(revision)
                    ),
                )
            )

            final_confirmation = (
                st.checkbox(
                    "I confirm that every item in the "
                    "Review Summary has been reviewed "
                    "and approved.",
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
                    "Ready for Verification. "
                    "The complete Review Summary has "
                    "been approved."
                )

            else:
                st.info(
                    "Formal verification remains blocked "
                    "until the final confirmation is "
                    "checked and a Reviewer Reference "
                    "is provided."
                )

            run_enabled = (
                bool(required_targets)
                and final_confirmation
                and reviewer_present
            )

            if st.button(
                "Run Verification",
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
        "6 · Verification Result"
    )

    st.caption(
        "This result corresponds to the most "
        "recently prepared and formally reviewed "
        "model."
    )

    assured_result = (
        verification_result.assured_result
    )

    if not assured_result.core_executed:
        st.warning(
            "Formal verification was not executed."
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
                "VERIFICATION ESCAPE DETECTED"
            )

            st.markdown(
                "A feasible state has been identified "
                "that satisfies the verification "
                "criterion while violating the "
                "engineering requirement."
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
                        "Counterexample · "
                        + stress_result.requirement_id
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

                    if state_rows:
                        st.dataframe(
                            state_rows,
                            width="stretch",
                            hide_index=True,
                        )

                    checks = [
                        {
                            "Condition": (
                                "Feasible Domain"
                            ),
                            "Status": "PASS",
                        },
                        {
                            "Condition": (
                                "Verification Criterion"
                            ),
                            "Status": "PASS",
                        },
                        {
                            "Condition": (
                                "Engineering Requirement"
                            ),
                            "Status": "FAIL",
                        },
                    ]

                    st.dataframe(
                        checks,
                        width="stretch",
                        hide_index=True,
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

                    details_left, details_right = (
                        st.columns(2)
                    )

                    with details_left:
                        if (
                            stress_result.worst_violation
                            is not None
                        ):
                            st.metric(
                                "Worst Violation",
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

                    with details_right:
                        if (
                            stress_result.direction
                            is not None
                        ):
                            st.metric(
                                "Violation Direction",
                                format_code_label(
                                    stress_result
                                    .direction
                                ),
                            )

                    if requirement_spec is not None:
                        derived_value = (
                            build_derived_value_view(
                                requirement_spec,
                                stress_result.actual_value,
                            )
                        )

                        if derived_value is not None:
                            st.metric(
                                derived_value.label
                                + " · "
                                + derived_value.expression,
                                derived_value.value,
                            )

                    st.caption(
                        "Formal condition: "
                        "F(x) ∧ V(x) ∧ ¬R(x)"
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
                "INDETERMINATE"
            )

            st.markdown(
                "The analysis could not establish "
                "either a Verification Escape or "
                "No Escape for at least one "
                "requirement."
            )

        elif (
            pipeline.status
            == "NO_ESCAPE_FOUND"
        ):
            st.success(
                "NO VERIFICATION ESCAPE FOUND"
            )

            st.markdown(
                "No counterexample was found within "
                "the modeled feasible domain."
            )

            st.caption(
                "This result is limited to the "
                "modeled requirements, verification "
                "criteria, feasible domain, and "
                "supported analysis scope. "
                "It is not a product safety verdict."
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
            "Gap Classification"
        )
        st.caption(
            "Report status · "
            + format_code_label(
                gap_classification.status
            )
        )
        st.dataframe(
            build_gap_classification_rows(
                gap_classification
            ),
            width="stretch",
            hide_index=True,
        )

        with st.expander(
            "Advanced · Classification codes"
        ):
            st.json(
                gap_classification.to_dict()
            )


    with st.expander(
        "Assurance Report"
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


    with st.expander(
        "Evidence Trace"
    ):
        evidence_items = getattr(
            verification_result,
            "evidence",
            [],
        )

        if not evidence_items:
            st.write(
                "No evidence trace entries "
                "are available."
            )

        for evidence in evidence_items:
            reference = (
                evidence.source_reference
                or evidence.source_name
            )

            st.markdown(
                "**"
                + format_code_label(
                    evidence.role
                )
                + " · "
                + evidence.target_id
                + "**"
            )

            st.caption(
                "Source · "
                + str(
                    reference
                )
            )

            provenance_details = []

            if evidence.source_sha256:
                provenance_details.append(
                    "SHA-256 "
                    + evidence.source_sha256
                )

            if evidence.source_pages:
                provenance_details.append(
                    "Page "
                    + ", ".join(
                        str(page)
                        for page
                        in evidence.source_pages
                    )
                )

            if evidence.source_location_status:
                provenance_details.append(
                    format_code_label(
                        evidence.source_location_status
                    )
                )

            if provenance_details:
                st.caption(
                    " · ".join(
                        provenance_details
                    )
                )

            st.code(
                evidence.source_text,
                language=None,
            )
