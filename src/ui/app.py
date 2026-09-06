import hashlib
import re

import streamlit as st

from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
)
from src.application.variable_mapping import (
    apply_analysis_variable_mappings,
    build_variable_mapping_targets,
    normalize_source_variable_group_key,
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


def safe_key(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:10]


def format_constraint(
    extraction: dict,
) -> str:
    kind = extraction.get(
        "type"
    )

    unit = extraction.get(
        "unit"
    ) or ""

    variable = extraction.get(
        "variable"
    )

    if kind == "range":
        return (
            f"{extraction.get('min')} ≤ "
            f"{variable} ≤ "
            f"{extraction.get('max')} "
            f"{unit}"
        ).strip()

    if kind == "lower_bound":
        return (
            f"{variable} ≥ "
            f"{extraction.get('min')} "
            f"{unit}"
        ).strip()

    if kind == "upper_bound":
        return (
            f"{variable} ≤ "
            f"{extraction.get('max')} "
            f"{unit}"
        ).strip()

    if kind == "difference_min":
        return (
            f"{extraction.get('left')} - "
            f"{extraction.get('right')} ≥ "
            f"{extraction.get('limit')} "
            f"{unit}"
        ).strip()

    if kind == "abs_difference_max":
        return (
            f"|{extraction.get('left')} - "
            f"{extraction.get('right')}| ≤ "
            f"{extraction.get('limit')} "
            f"{unit}"
        ).strip()

    if kind == "sum_upper":
        variables = " + ".join(
            extraction.get(
                "variables",
                [],
            )
        )

        return (
            f"{variables} ≤ "
            f"{extraction.get('limit')} "
            f"{unit}"
        ).strip()

    return str(
        extraction
    )


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
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# =========================================================
# STEP 1 — DOCUMENTS
# =========================================================

st.header(
    "1 · Engineering Documents"
)

left, right = st.columns(2)

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


current_signature = (
    build_input_signature(
        requirement_text,
        verification_text,
    )
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
                source_name=(
                    "requirement_input"
                ),
                text=requirement_text,
            )
        )

    if verification_text.strip():
        documents.append(
            SemanticDocument(
                role="verification",
                source_name=(
                    "verification_input"
                ),
                text=verification_text,
            )
        )

    if not documents:
        st.warning(
            "분석할 Engineering Requirement 또는 Verification 문서를 입력해 주세요."
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
            top_left, top_right = (
                st.columns(
                    [4, 1]
                )
            )

            with top_left:
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

            with top_right:
                if candidate.adapter_accepted:
                    st.success(
                        "Ready for review"
                    )
                else:
                    st.error(
                        "Blocked"
                    )

            source = (
                candidate.source_name
            )

            block = (
                candidate.source_block_id
                or "—"
            )

            st.caption(
                f"Source · {source} · "
                f"Block {block}"
            )

            with st.expander(
                "View original evidence"
            ):
                st.code(
                    candidate.source_text,
                    language=None,
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
                    or not analysis_is_current
                ),
            )

            if approved:
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
            "3 · Variables & Feasible Domain"
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

                st.success(
                    "Formal model preparation complete."
                )

            except Exception as exc:
                st.error(
                    str(exc)
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
        "Feasible Domain"
    )

    st.dataframe(
        feasible_rows,
        width="stretch",
        hide_index=True,
    )

    st.info(
        "다음 단계에서 Formal Human Review "
        "checklist와 Run Verification을 연결한다. "
        "현재 단계에서는 Solver가 실행되지 않습니다."
    )
