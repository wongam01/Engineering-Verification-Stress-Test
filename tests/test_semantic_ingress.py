import unittest

from src.application.document_workflow import (
    run_document_verification_workflow,
)
from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
    apply_semantic_approvals,
)
from src.core.models import (
    EngineeringCase,
)


def fake_extractor(
    text,
    role,
    source_name,
):
    common = {
        "source_line_id": "L1",
        "unit": "HRC",
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

    if role == "requirement":
        return [
            {
                **common,
                "constraint_id": "R_H",
                "type": "range",
                "variable": "H",
                "min": "50",
                "max": "57",
            }
        ]

    return [
        {
            **common,
            "constraint_id": "V_H",
            "type": "lower_bound",
            "variable": "H",
            "min": "50",
        }
    ]


def unsupported_extractor(
    text,
    role,
    source_name,
):
    return [
        {
            "source_line_id": "L1",
            "constraint_id": "R_UNSUPPORTED",
            "type": "unsupported",
            "unit": None,
            "variable": None,
            "min": None,
            "max": None,
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": False,
            "review_reason": None,
            "constraint_role": role,
            "source_name": source_name,
            "source_text": text,
        }
    ]


class SemanticIngressTest(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.base_case = (
            EngineeringCase.from_dict(
                {
                    "name": (
                        "Semantic Ingress HRC Case"
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
        )

        self.documents = [
            SemanticDocument(
                role="requirement",
                source_name="requirement.txt",
                text=(
                    "R_H. Hardness shall be "
                    "50 to 57 HRC."
                ),
            ),
            SemanticDocument(
                role="verification",
                source_name="inspection.txt",
                text=(
                    "V_H. Tip hardness shall "
                    "be at least 50 HRC."
                ),
            ),
        ]

    def analyze(
        self,
    ):
        return (
            analyze_semantic_documents(
                self.documents,
                extractor=fake_extractor,
            )
        )

    def test_01_analysis_preserves_candidates(
        self,
    ):
        analysis = self.analyze()

        self.assertEqual(
            analysis.status,
            "SEMANTIC_REVIEW_REQUIRED",
        )

        self.assertEqual(
            len(analysis.candidates),
            2,
        )

        self.assertTrue(
            all(
                candidate.adapter_accepted
                for candidate
                in analysis.candidates
            )
        )

        self.assertEqual(
            analysis.candidates[0]
            .source_block_id,
            "L1",
        )

    def test_02_no_semantic_approval_blocks_formalization(
        self,
    ):
        analysis = self.analyze()

        ingress = (
            apply_semantic_approvals(
                self.base_case,
                analysis,
                approved_candidate_ids=[],
            )
        )

        self.assertEqual(
            ingress.status,
            "SEMANTIC_REVIEW_REQUIRED",
        )

        self.assertFalse(
            ingress
            .ready_for_formal_workflow
        )

    def test_03_explicit_approval_applies_constraints_and_evidence(
        self,
    ):
        analysis = self.analyze()

        approved_ids = [
            candidate.candidate_id
            for candidate
            in analysis.candidates
        ]

        ingress = (
            apply_semantic_approvals(
                self.base_case,
                analysis,
                approved_ids,
            )
        )

        self.assertEqual(
            ingress.status,
            "READY_FOR_FORMAL_WORKFLOW",
        )

        self.assertEqual(
            [
                item.id
                for item
                in ingress.case.requirements
            ],
            ["R_H"],
        )

        self.assertEqual(
            [
                item.id
                for item
                in (
                    ingress.case
                    .verification_constraints
                )
            ],
            ["V_H"],
        )

        self.assertEqual(
            len(ingress.evidence),
            2,
        )

        self.assertEqual(
            ingress.evidence[0]
            .source_block_id,
            "L1",
        )

    def test_04_unknown_approval_is_invalid(
        self,
    ):
        analysis = self.analyze()

        ingress = (
            apply_semantic_approvals(
                self.base_case,
                analysis,
                [
                    "not-a-real-candidate"
                ],
            )
        )

        self.assertEqual(
            ingress.status,
            "INVALID_SEMANTIC_APPROVAL",
        )

        self.assertFalse(
            ingress
            .ready_for_formal_workflow
        )

    def test_05_semantic_approval_cannot_bypass_formal_review(
        self,
    ):
        analysis = self.analyze()

        approved_ids = [
            candidate.candidate_id
            for candidate
            in analysis.candidates
        ]

        result = (
            run_document_verification_workflow(
                self.base_case,
                analysis,
                approved_ids,
                review_records=[],
                generate_patches=False,
            )
        )

        self.assertTrue(
            result.formal_workflow_executed
        )

        self.assertEqual(
            result.status,
            "HUMAN_REVIEW_BLOCKED",
        )

        self.assertFalse(
            result.core_executed
        )

        self.assertEqual(
            len(
                result
                .formal_result
                .evidence
            ),
            3,
        )

        self.assertEqual(
            [
                trace.role
                for trace
                in result
                .formal_result
                .evidence
            ],
            [
                "requirement",
                "verification",
                "feasible_domain",
            ],
        )

    def test_06_unsupported_candidate_blocks_formal_workflow(
        self,
    ):
        analysis = (
            analyze_semantic_documents(
                [
                    SemanticDocument(
                        role="requirement",
                        source_name=(
                            "unsupported.txt"
                        ),
                        text=(
                            "Evaluate fatigue life."
                        ),
                    )
                ],
                extractor=(
                    unsupported_extractor
                ),
            )
        )

        approved_ids = [
            candidate.candidate_id
            for candidate
            in analysis.candidates
        ]

        result = (
            run_document_verification_workflow(
                self.base_case,
                analysis,
                approved_ids,
                review_records=[],
                generate_patches=False,
            )
        )

        self.assertEqual(
            result.status,
            "SEMANTIC_REVIEW_REQUIRED",
        )

        self.assertFalse(
            result.formal_workflow_executed
        )

        self.assertFalse(
            result.core_executed
        )


if __name__ == "__main__":
    unittest.main()
