import unittest

from src.application.formal_review import (
    build_exact_approved_review_records,
    build_review_state_signature,
    build_review_summary_rows,
    format_code_label,
    format_review_target_id,
    format_value_with_unit,
    has_review_state_changed,
)
from src.application.evidence_trace import (
    assemble_workflow_evidence,
    build_feasible_domain_evidence,
)
from src.application.models import (
    EvidenceTrace,
)
from src.application.escape_execution import (
    run_verification_escape_workflow,
)
from src.core.models import (
    EngineeringCase,
)
from src.core.review_completeness import (
    build_required_review_targets,
    evaluate_case_human_review_gate,
)


def build_case():
    return EngineeringCase.from_dict(
        {
            "name": "Application 4C-2B Case",
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
                            "test_fixture:F_H"
                        ),
                        "approval_status": (
                            "approved"
                        ),
                        "note": (
                            "Fixture-backed domain."
                        ),
                    },
                },
            },
            "requirements": [
                {
                    "id": "R1",
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "max": "57",
                },
            ],
            "verification_constraints": [
                {
                    "id": "V1",
                    "type": "lower_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                },
            ],
        }
    )


def semantic_evidence():
    return [
        EvidenceTrace(
            role="requirement",
            target_id="R1",
            source_name="requirement.txt",
            source_text=(
                "R1. H shall be between "
                "50 and 57 HRC."
            ),
        ),
        EvidenceTrace(
            role="verification",
            target_id="V1",
            source_name="inspection.txt",
            source_text=(
                "V1. Accept when H is at "
                "least 50 HRC."
            ),
        ),
    ]


class Application4C2BTest(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.case = build_case()
        self.targets = (
            build_required_review_targets(
                self.case
            )
        )

    def test_01_single_confirmation_preserves_exact_records(
        self,
    ):
        records = (
            build_exact_approved_review_records(
                self.targets,
                " REVIEWER-42 ",
                True,
                reviewed_at=(
                    "2026-09-07T00:00:00+00:00"
                ),
            )
        )

        self.assertEqual(
            len(records),
            len(self.targets),
        )

        self.assertEqual(
            [
                (
                    record.target_type,
                    record.target_id,
                )
                for record in records
            ],
            [
                (
                    target.target_type,
                    target.target_id,
                )
                for target in self.targets
            ],
        )

        self.assertTrue(
            all(
                record.reviewer_reference
                == "REVIEWER-42"
                and record.decision
                == "approved"
                for record in records
            )
        )

        gate = (
            evaluate_case_human_review_gate(
                self.case,
                records,
            )
        )

        self.assertTrue(
            gate.ready_for_solver
        )

    def test_02_incomplete_ui_approval_remains_blocked(
        self,
    ):
        incomplete_inputs = [
            ("", True),
            ("REVIEWER-42", False),
        ]

        for reviewer, confirmed in (
            incomplete_inputs
        ):
            with self.subTest(
                reviewer=reviewer,
                confirmed=confirmed,
            ):
                records = (
                    build_exact_approved_review_records(
                        self.targets,
                        reviewer,
                        confirmed,
                    )
                )

                self.assertEqual(
                    records,
                    [],
                )

                result = (
                    run_verification_escape_workflow(
                        self.case,
                        records,
                        generate_patches=False,
                    )
                )

                self.assertEqual(
                    result.status,
                    "HUMAN_REVIEW_BLOCKED",
                )

                self.assertFalse(
                    result.core_executed
                )

    def test_03_feasible_domain_evidence_is_in_final_trace(
        self,
    ):
        records = (
            build_exact_approved_review_records(
                self.targets,
                "REVIEWER-42",
                True,
                reviewed_at=(
                    "2026-09-07T00:00:00+00:00"
                ),
            )
        )

        result = (
            run_verification_escape_workflow(
                self.case,
                records,
                evidence=semantic_evidence(),
                generate_patches=False,
            )
        )

        self.assertEqual(
            [
                trace.role
                for trace
                in result.evidence
            ],
            [
                "requirement",
                "verification",
                "feasible_domain",
            ],
        )

        feasible_trace = (
            result.evidence[2]
        )

        self.assertEqual(
            feasible_trace.target_id,
            "H",
        )

        self.assertEqual(
            feasible_trace.source_reference,
            "test_fixture:F_H",
        )

        self.assertIn(
            "58 <= H <= 60 HRC",
            feasible_trace.source_text,
        )

        trace_entries = (
            result.to_dict()[
                "constraint_trace"
            ][
                "entries"
            ]
        )

        feasible_entries = [
            entry
            for entry in trace_entries
            if entry["role"]
            == "feasible_domain"
        ]

        self.assertEqual(
            len(feasible_entries),
            1,
        )

        self.assertEqual(
            feasible_entries[0][
                "trace_status"
            ],
            "EVIDENCE_LINKED",
        )

    def test_04_review_summary_and_labels_are_deterministic(
        self,
    ):
        rows = build_review_summary_rows(
            self.targets
        )

        self.assertEqual(
            len(rows),
            len(self.targets),
        )

        self.assertEqual(
            format_review_target_id(
                "variable:H"
            ),
            "Variable · H",
        )

        self.assertEqual(
            format_review_target_id(
                "requirement:R1"
            ),
            "Requirement · R1",
        )

        self.assertEqual(
            format_review_target_id(
                "verification_constraint:V1"
            ),
            "Verification · V1",
        )

        self.assertEqual(
            format_code_label(
                "above_maximum"
            ),
            "Above Maximum",
        )

        self.assertEqual(
            format_value_with_unit(
                "3.0",
                "HRC",
            ),
            "3.0 HRC",
        )

        self.assertEqual(
            rows[0],
            {
                "Target": "Variable · H",
                "Review Item": (
                    "Variable Mapping"
                ),
            },
        )

    def test_05_identical_feasible_evidence_is_deduplicated(
        self,
    ):
        actual = (
            build_feasible_domain_evidence(
                self.case
            )[0]
        )

        traces = assemble_workflow_evidence(
            self.case,
            [actual, actual],
        )

        self.assertEqual(
            traces,
            [actual],
        )

    def test_06_distinct_feasible_sources_are_preserved(
        self,
    ):
        alternate = EvidenceTrace(
            role="feasible_domain",
            target_id="H",
            source_name=(
                "alternate_observation"
            ),
            source_text=(
                "Alternate feasible-domain evidence."
            ),
            source_reference=(
                "alternate_fixture:F_H"
            ),
        )

        traces = assemble_workflow_evidence(
            self.case,
            [alternate],
        )

        self.assertEqual(
            len(traces),
            2,
        )

        self.assertEqual(
            {
                trace.source_reference
                for trace in traces
            },
            {
                "alternate_fixture:F_H",
                "test_fixture:F_H",
            },
        )

    def test_07_review_state_changes_invalidate_result_signature(
        self,
    ):
        executed = (
            build_review_state_signature(
                "REVIEWER-42",
                True,
            )
        )

        self.assertFalse(
            has_review_state_changed(
                executed,
                " REVIEWER-42 ",
                True,
            )
        )

        self.assertTrue(
            has_review_state_changed(
                executed,
                "REVIEWER-43",
                True,
            )
        )

        self.assertTrue(
            has_review_state_changed(
                executed,
                "REVIEWER-42",
                False,
            )
        )


if __name__ == "__main__":
    unittest.main()
