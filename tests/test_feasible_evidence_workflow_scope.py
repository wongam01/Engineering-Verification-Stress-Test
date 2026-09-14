import unittest

from src.application.models import EvidenceTrace
from src.application.evidence_trace import (
    assemble_workflow_evidence,
)
from src.application import feasible_evidence_ingress
from src.application.feasible_evidence_ingress import (
    FeasibleEvidencePrefill,
)
from src.core.models import EngineeringCase


class FeasibleEvidenceWorkflowScopeTest(
    unittest.TestCase
):
    def test_01_evidence_trace_serializes_selected_scope(
        self,
    ):
        trace = EvidenceTrace(
            role="feasible_domain",
            target_id="H",
            source_name="evidence.pdf",
            source_text=(
                "Observed hardness 58 to 60 HRC."
            ),
            source_sha256="abc123",
            source_page=2,
            source_pages=(2,),
            source_block_id="L1",
            source_reference=(
                "evidence.pdf:p2:L1"
            ),
            source_location_status="RESOLVED",
            analysis_scope="SELECTED_PAGES",
            vision_processed_page_numbers=(
                2,
                11,
            ),
            vision_unprocessed_candidate_page_numbers=(
                1,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                12,
                13,
            ),
        )

        data = trace.to_dict()

        self.assertEqual(
            data["analysis_scope"],
            "SELECTED_PAGES",
        )
        self.assertEqual(
            data[
                "vision_processed_page_numbers"
            ],
            [2, 11],
        )
        self.assertEqual(
            data[
                "vision_unprocessed_candidate_page_numbers"
            ],
            [
                1,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                12,
                13,
            ],
        )

    def test_02_prefill_builds_rich_feasible_trace(
        self,
    ):
        builder = getattr(
            feasible_evidence_ingress,
            "build_feasible_evidence_trace",
            None,
        )

        self.assertIsNotNone(
            builder,
            (
                "Application helper "
                "build_feasible_evidence_trace "
                "must exist."
            ),
        )

        if builder is None:
            return

        prefill = FeasibleEvidencePrefill(
            candidate_id="F-1",
            source_variable="H",
            canonical_variable="H",
            unit="HRC",
            feasible_min="58",
            feasible_max="60",
            evidence_type=(
                "observed_test_data"
            ),
            evidence_reference=(
                "evidence.pdf:p2:L1"
            ),
            source_name="evidence.pdf",
            source_text=(
                "Observed hardness 58 to 60 HRC."
            ),
            source_sha256="abc123",
            source_page=2,
            source_pages=(2,),
            source_block_id="L1",
            source_location_status="RESOLVED",
            analysis_scope="SELECTED_PAGES",
            vision_processed_page_numbers=(
                2,
                11,
            ),
            vision_unprocessed_candidate_page_numbers=(
                1,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                12,
                13,
            ),
        )

        trace = builder(prefill)

        self.assertEqual(
            trace.role,
            "feasible_domain",
        )
        self.assertEqual(
            trace.target_id,
            "H",
        )
        self.assertEqual(
            trace.source_name,
            "evidence.pdf",
        )
        self.assertEqual(
            trace.source_page,
            2,
        )
        self.assertEqual(
            trace.source_pages,
            (2,),
        )
        self.assertEqual(
            trace.analysis_scope,
            "SELECTED_PAGES",
        )
        self.assertEqual(
            trace.vision_processed_page_numbers,
            (2, 11),
        )

    def test_03_rich_feasible_trace_suppresses_fallback(
        self,
    ):
        case = EngineeringCase.from_dict(
            {
                "name": "scope-test",
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
                                "evidence.pdf:p2:L1"
                            ),
                            "approval_status": (
                                "approved"
                            ),
                        },
                    },
                },
                "requirements": [],
                "verification_constraints": [],
            }
        )

        rich_trace = EvidenceTrace(
            role="feasible_domain",
            target_id="H",
            source_name="evidence.pdf",
            source_text=(
                "Observed hardness 58 to 60 HRC."
            ),
            source_sha256="abc123",
            source_page=2,
            source_pages=(2,),
            source_block_id="L1",
            source_reference=(
                "evidence.pdf:p2:L1"
            ),
            source_location_status="RESOLVED",
        )

        traces = assemble_workflow_evidence(
            case,
            [rich_trace],
        )

        feasible_traces = [
            trace
            for trace in traces
            if (
                trace.role
                == "feasible_domain"
                and trace.target_id == "H"
            )
        ]

        self.assertEqual(
            feasible_traces,
            [rich_trace],
        )


if __name__ == "__main__":
    unittest.main()
