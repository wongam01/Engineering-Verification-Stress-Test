import unittest

from src.application.evidence_trace import (
    build_source_reference,
    extract_explicit_source_pages,
    select_single_source_page,
)
from src.application.models import (
    EvidenceTrace,
)
from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
    apply_semantic_approvals,
)
from src.core.models import (
    EngineeringCase,
)


def page_aware_fake_extractor(
    text,
    role,
    source_name,
):
    if role == "requirement":
        return [
            {
                "source_line_id": "L1",
                "constraint_id": "R_H",
                "type": "range",
                "unit": "HRC",
                "variable": "H",
                "min": "50",
                "max": "57",
                "left": None,
                "right": None,
                "variables": [],
                "limit": None,
                "needs_review": False,
                "review_reason": None,
                "source_name": source_name,
                "source_text": text,
            }
        ]

    return [
        {
            "source_line_id": "L1",
            "constraint_id": "V_H",
            "type": "lower_bound",
            "unit": "HRC",
            "variable": "H",
            "min": "50",
            "max": None,
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": False,
            "review_reason": None,
            "source_name": source_name,
            "source_text": text,
        }
    ]


class EvidencePageTraceTest(
    unittest.TestCase
):
    def test_01_single_explicit_page_is_extracted(
        self,
    ):
        text = """
===== PDF PAGE 3 =====
R1. Hardness shall be 50 to 57 HRC.
"""

        pages = (
            extract_explicit_source_pages(
                text
            )
        )

        self.assertEqual(
            pages,
            (3,),
        )

        self.assertEqual(
            select_single_source_page(
                pages
            ),
            3,
        )

    def test_02_multiple_pages_are_not_collapsed_to_one(
        self,
    ):
        text = """
===== PDF PAGE 3 =====
R1. Requirement begins here
===== PDF PAGE 4 =====
and continues here.
"""

        pages = (
            extract_explicit_source_pages(
                text
            )
        )

        self.assertEqual(
            pages,
            (3, 4),
        )

        self.assertIsNone(
            select_single_source_page(
                pages
            )
        )

        self.assertEqual(
            build_source_reference(
                source_name="design.pdf",
                source_block_id="L1",
                source_pages=pages,
            ),
            "design.pdf:p3,p4:L1",
        )

    def test_03_missing_page_marker_is_not_guessed(
        self,
    ):
        text = (
            "R1. Hardness shall be "
            "50 to 57 HRC."
        )

        pages = (
            extract_explicit_source_pages(
                text
            )
        )

        self.assertEqual(
            pages,
            (),
        )

        self.assertIsNone(
            select_single_source_page(
                pages
            )
        )

    def test_04_evidence_trace_serializes_page_data(
        self,
    ):
        trace = EvidenceTrace(
            role="requirement",
            target_id="R1",
            source_name="design.pdf",
            source_text=(
                "===== PDF PAGE 3 =====\n"
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

        data = trace.to_dict()

        self.assertEqual(
            data["source_page"],
            3,
        )

        self.assertEqual(
            data["source_pages"],
            [3],
        )

    def test_05_semantic_ingress_builds_page_trace(
        self,
    ):
        case = EngineeringCase.from_dict(
            {
                "name": (
                    "Evidence Page Trace Case"
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
                "requirements": [],
                "verification_constraints": [],
            }
        )

        documents = [
            SemanticDocument(
                role="requirement",
                source_name="design.pdf",
                text=(
                    "===== PDF PAGE 3 =====\n"
                    "R_H. Hardness H shall be "
                    "50 to 57 HRC."
                ),
            ),
            SemanticDocument(
                role="verification",
                source_name="inspection.pdf",
                text=(
                    "===== PDF PAGE 7 =====\n"
                    "V_H. Hardness H shall be "
                    "at least 50 HRC."
                ),
            ),
        ]

        analysis = (
            analyze_semantic_documents(
                documents,
                extractor=(
                    page_aware_fake_extractor
                ),
            )
        )

        approved_ids = [
            candidate.candidate_id
            for candidate
            in analysis.candidates
        ]

        ingress = (
            apply_semantic_approvals(
                case,
                analysis,
                approved_ids,
            )
        )

        self.assertEqual(
            ingress.status,
            "READY_FOR_FORMAL_WORKFLOW",
        )

        self.assertEqual(
            len(ingress.evidence),
            2,
        )

        requirement_trace = (
            ingress.evidence[0]
        )

        verification_trace = (
            ingress.evidence[1]
        )

        self.assertEqual(
            requirement_trace.source_page,
            3,
        )

        self.assertEqual(
            requirement_trace.source_pages,
            (3,),
        )

        self.assertEqual(
            requirement_trace.source_reference,
            "design.pdf:p3:L1",
        )

        self.assertEqual(
            verification_trace.source_page,
            7,
        )

        self.assertEqual(
            verification_trace.source_reference,
            "inspection.pdf:p7:L1",
        )


if __name__ == "__main__":
    unittest.main()
