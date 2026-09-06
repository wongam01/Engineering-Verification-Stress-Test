import unittest

from src.application.models import (
    EvidenceTrace,
)
from src.application.trace_view import (
    build_constraint_trace_view,
)
from src.application.verification_workflow import (
    run_verification_workflow,
)
from src.core.models import (
    EngineeringCase,
)


def build_case(
    requirement_id="R1",
    verification_id="V1",
):
    return EngineeringCase.from_dict(
        {
            "name": (
                "Constraint Trace View Case"
            ),
            "variables": {
                "H": {
                    "unit": "HRC",
                    "feasible_min": "58",
                    "feasible_max": "60",
                    "feasible_evidence": {
                        "source_type": (
                            "observed_test_data"
                        ),
                        "source_reference": (
                            "fixture:F_H"
                        ),
                        "approval_status": (
                            "approved"
                        ),
                    },
                }
            },
            "requirements": [
                {
                    "id": requirement_id,
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "max": "57",
                }
            ],
            "verification_constraints": [
                {
                    "id": verification_id,
                    "type": "lower_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                }
            ],
        }
    )


class ConstraintTraceViewTest(
    unittest.TestCase
):
    def test_01_exact_constraint_evidence_link(
        self,
    ):
        case = build_case()

        trace = EvidenceTrace(
            role="requirement",
            target_id="R1",
            source_name="design.pdf",
            source_text=(
                "R1. Hardness shall be "
                "50 to 57 HRC."
            ),
            source_page=3,
            source_pages=(3,),
            source_block_id="L1",
            source_reference=(
                "design.pdf:p3:L1"
            ),
        )

        report = (
            build_constraint_trace_view(
                case,
                [trace],
            )
        )

        self.assertEqual(
            len(report.entries),
            2,
        )

        requirement = (
            report.entries[0]
        )

        self.assertEqual(
            requirement.target_id,
            "R1",
        )

        self.assertEqual(
            requirement.trace_status,
            "EVIDENCE_LINKED",
        )

        self.assertEqual(
            requirement.evidence,
            (trace,),
        )

    def test_02_role_prevents_cross_linking(
        self,
    ):
        case = build_case(
            requirement_id="X1",
            verification_id="X1",
        )

        trace = EvidenceTrace(
            role="requirement",
            target_id="X1",
            source_name="design.pdf",
            source_text="Requirement text.",
        )

        report = (
            build_constraint_trace_view(
                case,
                [trace],
            )
        )

        requirement = (
            report.entries[0]
        )

        verification = (
            report.entries[1]
        )

        self.assertEqual(
            requirement.trace_status,
            "EVIDENCE_LINKED",
        )

        self.assertEqual(
            verification.trace_status,
            "EVIDENCE_NOT_LINKED",
        )

    def test_03_missing_evidence_is_explicit(
        self,
    ):
        case = build_case()

        report = (
            build_constraint_trace_view(
                case,
                [],
            )
        )

        self.assertTrue(
            all(
                entry.trace_status
                == "EVIDENCE_NOT_LINKED"
                for entry
                in report.entries
            )
        )

    def test_04_unmatched_evidence_is_preserved(
        self,
    ):
        case = build_case()

        orphan = EvidenceTrace(
            role="requirement",
            target_id="R_UNKNOWN",
            source_name="other.pdf",
            source_text=(
                "Unmatched source evidence."
            ),
        )

        report = (
            build_constraint_trace_view(
                case,
                [orphan],
            )
        )

        self.assertTrue(
            report.has_unmatched_evidence
        )

        self.assertEqual(
            report.unmatched_evidence,
            (orphan,),
        )

    def test_05_workflow_summary_contains_trace_view(
        self,
    ):
        case = build_case()

        evidence = [
            EvidenceTrace(
                role="requirement",
                target_id="R1",
                source_name="design.pdf",
                source_text=(
                    "R1. Hardness shall be "
                    "50 to 57 HRC."
                ),
                source_page=3,
                source_pages=(3,),
                source_block_id="L1",
                source_reference=(
                    "design.pdf:p3:L1"
                ),
            ),
            EvidenceTrace(
                role="verification",
                target_id="V1",
                source_name="inspection.pdf",
                source_text=(
                    "V1. Hardness shall be "
                    "at least 50 HRC."
                ),
                source_page=7,
                source_pages=(7,),
                source_block_id="L1",
                source_reference=(
                    "inspection.pdf:p7:L1"
                ),
            ),
        ]

        result = (
            run_verification_workflow(
                case,
                review_records=[],
                evidence=evidence,
                generate_patches=False,
            )
        )

        # Formal Human Review가 없으므로
        # Core는 여전히 실행되면 안 된다.
        self.assertFalse(
            result.core_executed
        )

        summary = result.to_dict()

        trace_report = (
            summary[
                "constraint_trace"
            ]
        )

        self.assertEqual(
            len(
                trace_report[
                    "entries"
                ]
            ),
            2,
        )

        self.assertEqual(
            trace_report[
                "entries"
            ][0][
                "trace_status"
            ],
            "EVIDENCE_LINKED",
        )

        self.assertEqual(
            trace_report[
                "entries"
            ][0][
                "evidence"
            ][0][
                "source_page"
            ],
            3,
        )

        self.assertEqual(
            trace_report[
                "unmatched_evidence"
            ],
            [],
        )


if __name__ == "__main__":
    unittest.main()
