import hashlib

import streamlit as st

from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
)


st.set_page_config(
    page_title="Engineering Verification Stress Test",
    layout="wide",
)

st.title("Engineering Verification Stress Test")

st.caption(
    "Document Evidence → Engineering Semantics "
    "→ Formal Verification"
)


def build_input_signature(
    requirement_text: str,
    verification_text: str,
) -> str:
    payload = (
        requirement_text
        + "\n---VERIFICATION---\n"
        + verification_text
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


if "semantic_analysis" not in st.session_state:
    st.session_state.semantic_analysis = None

if "analysis_signature" not in st.session_state:
    st.session_state.analysis_signature = None


left, right = st.columns(2)

with left:
    st.subheader("Engineering Requirement")

    requirement_text = st.text_area(
        "Requirement document text",
        height=260,
        placeholder=(
            "Example:\n"
            "R1. Hardness H shall be between "
            "50 HRC and 57 HRC inclusive."
        ),
    )

with right:
    st.subheader("Verification / Inspection")

    verification_text = st.text_area(
        "Verification document text",
        height=260,
        placeholder=(
            "Example:\n"
            "V1. The inspection accepts the part "
            "when hardness H is at least 50 HRC."
        ),
    )


current_signature = build_input_signature(
    requirement_text,
    verification_text,
)


if st.button(
    "Analyze Documents",
    type="primary",
):
    documents = []

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

    if not documents:
        st.warning(
            "분석할 Requirement 또는 "
            "Verification 문서를 입력해줘."
        )
    else:
        try:
            with st.spinner(
                "AI Semantic Analysis..."
            ):
                analysis = (
                    analyze_semantic_documents(
                        documents
                    )
                )

            st.session_state.semantic_analysis = (
                analysis
            )

            st.session_state.analysis_signature = (
                current_signature
            )

        except Exception as exc:
            st.error(
                "Semantic Analysis 실행 중 "
                f"오류가 발생했습니다: {exc}"
            )


analysis = st.session_state.semantic_analysis


if analysis is not None:
    st.divider()

    st.subheader("Semantic Candidates")

    if (
        st.session_state.analysis_signature
        != current_signature
    ):
        st.warning(
            "문서가 분석 이후 변경되었습니다. "
            "Candidate를 사용하기 전에 다시 Analyze 해줘."
        )

        analysis_is_current = False

    else:
        analysis_is_current = True

    st.write(
        "Analysis status:",
        analysis.status,
    )

    st.write(
        "Candidate count:",
        len(analysis.candidates),
    )

    approved_candidate_ids = []

    for index, candidate in enumerate(
        analysis.candidates,
        start=1,
    ):
        label = (
            f"{index}. "
            f"{candidate.role.upper()} — "
            f"{candidate.constraint_id} "
            f"[{candidate.extraction.get('type')}]"
        )

        with st.expander(
            label,
            expanded=True,
        ):
            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Role",
                candidate.role,
            )

            c2.metric(
                "Constraint",
                candidate.constraint_id,
            )

            c3.metric(
                "Adapter",
                (
                    "ACCEPTED"
                    if candidate.adapter_accepted
                    else "BLOCKED"
                ),
            )

            st.write(
                "**Source:**",
                candidate.source_name,
            )

            st.write(
                "**Block:**",
                candidate.source_block_id
                or "Not available",
            )

            st.write(
                "**Original Evidence**"
            )

            st.code(
                candidate.source_text,
                language=None,
            )

            st.write(
                "**Formalization Candidate**"
            )

            st.json(
                candidate.extraction
            )

            if not candidate.adapter_accepted:
                st.error(
                    candidate.adapter_result.message
                )

            approved = st.checkbox(
                "Approve semantic candidate",
                key=(
                    "semantic_approval_"
                    + candidate.candidate_id
                ),
                disabled=(
                    not candidate.adapter_accepted
                    or not analysis_is_current
                ),
            )

            if approved:
                approved_candidate_ids.append(
                    candidate.candidate_id
                )

    st.divider()

    st.subheader("Semantic Review Summary")

    st.write(
        "Approved:",
        len(approved_candidate_ids),
        "/",
        len(analysis.candidates),
    )

    if (
        analysis_is_current
        and analysis.candidates
        and len(approved_candidate_ids)
        == len(analysis.candidates)
    ):
        st.success(
            "모든 Semantic Candidate가 승인되었습니다."
        )

        st.info(
            "다음 단계에서 Feasible Domain Evidence와 "
            "Formal Human Review를 연결한 뒤 "
            "Validated Core 실행 버튼을 추가합니다."
        )
    else:
        st.info(
            "Semantic approval은 Formal Human Review와 "
            "별개이며 Solver 실행 승인이 아닙니다."
        )
