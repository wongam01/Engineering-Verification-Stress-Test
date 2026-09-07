import json
import unittest
from collections import Counter
from pathlib import Path

from src.application.escape_execution import (
    run_verification_escape_workflow,
)
from src.application.formal_review import (
    build_exact_approved_review_records,
)
from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
    apply_semantic_approvals,
)
from src.application.variable_mapping import (
    apply_analysis_variable_mappings,
    build_variable_mapping_targets,
)
from src.core.models import EngineeringCase
from src.core.review_completeness import (
    build_required_review_targets,
)


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = (
    ROOT
    / "demos"
    / "unseen_4d_thermal_balance"
)


def load_expected_data():
    return json.loads(
        (DEMO_DIR / "expected_case.json")
        .read_text(encoding="utf-8")
    )


def deterministic_extractor(
    text,
    role,
    source_name,
):
    common = {
        "source_line_id": "L1",
        "type": "abs_difference_max",
        "unit": "degC",
        "variable": None,
        "min": None,
        "max": None,
        "left": "T_A",
        "right": "T_B",
        "variables": [],
        "needs_review": False,
        "review_reason": None,
        "source_name": source_name,
        "source_text": text,
    }

    if role == "requirement":
        return [
            {
                **common,
                "constraint_id": "R_BALANCE",
                "limit": "2",
            }
        ]

    return [
        {
            **common,
            "constraint_id": "V_BALANCE",
            "limit": "5",
        }
    ]


def build_deterministic_flow():
    expected = load_expected_data()

    documents = [
        SemanticDocument(
            role="requirement",
            source_name="requirement.txt",
            text=(DEMO_DIR / "requirement.txt")
            .read_text(encoding="utf-8"),
        ),
        SemanticDocument(
            role="verification",
            source_name="verification.txt",
            text=(DEMO_DIR / "verification.txt")
            .read_text(encoding="utf-8"),
        ),
    ]

    analysis = analyze_semantic_documents(
        documents,
        extractor=deterministic_extractor,
    )

    mappings = {
        candidate.candidate_id: {
            "T_A": "T_A",
            "T_B": "T_B",
        }
        for candidate in analysis.candidates
    }

    mapped_analysis = (
        apply_analysis_variable_mappings(
            analysis,
            mappings,
        )
    )

    base_case = EngineeringCase.from_dict(
        {
            "name": expected["name"],
            "variables": expected["variables"],
            "requirements": [],
            "verification_constraints": [],
        }
    )

    approved_ids = [
        candidate.candidate_id
        for candidate in mapped_analysis.candidates
    ]

    ingress = apply_semantic_approvals(
        base_case,
        mapped_analysis,
        approved_ids,
    )

    targets = build_required_review_targets(
        ingress.case
    )

    records = build_exact_approved_review_records(
        targets,
        "4D-DETERMINISTIC-REVIEWER",
        True,
        reviewed_at="2026-09-07T00:00:00+00:00",
    )

    result = run_verification_escape_workflow(
        ingress.case,
        records,
        evidence=ingress.evidence,
        generate_patches=False,
    )

    return (
        analysis,
        mapped_analysis,
        ingress,
        targets,
        result,
    )


class Unseen4DThermalBalanceTest(unittest.TestCase):
    def test_01_demo_artifacts_freeze_controlled_contract(
        self,
    ):
        required_disclosures = (
            "Controlled Synthetic Engineering Demo",
            "Development-only evidence set",
            "Not field data and not a real industrial incident",
        )

        for filename in (
            "README.md",
            "requirement.txt",
            "verification.txt",
            "feasible_domain_evidence.md",
        ):
            content = (DEMO_DIR / filename).read_text(
                encoding="utf-8"
            )

            with self.subTest(filename=filename):
                for disclosure in required_disclosures:
                    self.assertIn(disclosure, content)

        evidence_text = (
            DEMO_DIR / "feasible_domain_evidence.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "independently controllable",
            evidence_text,
        )
        self.assertIn(
            "Cartesian product",
            evidence_text,
        )
        self.assertIn(
            "[20, 30] x [20, 30] degC",
            evidence_text,
        )

    def test_02_deterministic_semantics_mapping_and_review_targets(
        self,
    ):
        (
            analysis,
            mapped_analysis,
            ingress,
            targets,
            _,
        ) = build_deterministic_flow()

        self.assertEqual(
            analysis.status,
            "SEMANTIC_REVIEW_REQUIRED",
        )
        self.assertEqual(
            [
                (
                    candidate.constraint_id,
                    candidate.extraction["type"],
                    candidate.extraction["limit"],
                )
                for candidate in analysis.candidates
            ],
            [
                (
                    "R_BALANCE",
                    "abs_difference_max",
                    "2",
                ),
                (
                    "V_BALANCE",
                    "abs_difference_max",
                    "5",
                ),
            ],
        )

        mapping_targets = build_variable_mapping_targets(
            mapped_analysis
        )
        self.assertEqual(
            {
                target.source_variable
                for target in mapping_targets
            },
            {"T_A", "T_B"},
        )

        for candidate in mapped_analysis.candidates:
            self.assertEqual(
                candidate.extraction["left"],
                "T_A",
            )
            self.assertEqual(
                candidate.extraction["right"],
                "T_B",
            )

        self.assertEqual(
            ingress.status,
            "READY_FOR_FORMAL_WORKFLOW",
        )
        self.assertEqual(len(targets), 12)

    def test_03_existing_workflow_produces_expected_escape_and_trace(
        self,
    ):
        (
            _,
            _,
            _,
            _,
            result,
        ) = build_deterministic_flow()

        self.assertEqual(
            result.assured_result
            .scope_assessment.status,
            "AUTOMATED_STRESS_TEST_SUPPORTED",
        )
        self.assertEqual(
            result.assured_result
            .assurance_readiness.status,
            "READY",
        )
        self.assertTrue(
            result.assured_result
            .human_review.ready_for_solver
        )
        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )
        self.assertTrue(result.core_executed)

        stress = (
            result.pipeline_result
            .requirement_results[0]
            .stress_result
        )
        self.assertTrue(stress.escape_found)

        t_a = stress.state["T_A"]
        t_b = stress.state["T_B"]
        derived_difference = abs(t_a - t_b)

        self.assertGreaterEqual(t_a, 20.0)
        self.assertLessEqual(t_a, 30.0)
        self.assertGreaterEqual(t_b, 20.0)
        self.assertLessEqual(t_b, 30.0)
        self.assertAlmostEqual(
            derived_difference,
            5.0,
            places=9,
        )
        self.assertLessEqual(
            derived_difference,
            5.0,
        )
        self.assertGreater(
            derived_difference,
            2.0,
        )
        self.assertAlmostEqual(
            stress.worst_violation,
            3.0,
            places=9,
        )

        role_counts = Counter(
            trace.role
            for trace in result.evidence
        )
        self.assertEqual(
            role_counts,
            Counter(
                {
                    "requirement": 1,
                    "verification": 1,
                    "feasible_domain": 2,
                }
            ),
        )

        feasible_references = {
            trace.target_id: trace.source_reference
            for trace in result.evidence
            if trace.role == "feasible_domain"
        }
        self.assertEqual(
            feasible_references,
            {
                "T_A": (
                    "demos/unseen_4d_thermal_balance/"
                    "feasible_domain_evidence.md#F-T_A"
                ),
                "T_B": (
                    "demos/unseen_4d_thermal_balance/"
                    "feasible_domain_evidence.md#F-T_B"
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
