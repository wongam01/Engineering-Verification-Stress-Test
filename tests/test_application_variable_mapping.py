import unittest

from src.application.semantic_ingress import (
    SemanticDocument,
    analyze_semantic_documents,
)
from src.application.variable_mapping import (
    apply_analysis_variable_mappings,
    build_variable_mapping_targets,
)


def fake_extractor(
    text,
    role,
    source_name,
):
    if role == "requirement":
        return [
            {
                "source_line_id": "L1",
                "constraint_id": "R1",
                "type": "range",
                "unit": "HRC",
                "variable": "Hardness H",
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
            "constraint_id": "V1",
            "type": "lower_bound",
            "unit": "HRC",
            "variable": "Hardness H",
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


def build_analysis():
    return analyze_semantic_documents(
        [
            SemanticDocument(
                role="requirement",
                source_name="design.txt",
                text=(
                    "R1. Hardness H shall be "
                    "50 to 57 HRC."
                ),
            ),
            SemanticDocument(
                role="verification",
                source_name="inspection.txt",
                text=(
                    "V1. Hardness H shall be "
                    "at least 50 HRC."
                ),
            ),
        ],
        extractor=fake_extractor,
    )


class ApplicationVariableMappingTest(
    unittest.TestCase
):
    def test_01_targets_preserve_source_variable(
        self,
    ):
        analysis = build_analysis()

        targets = (
            build_variable_mapping_targets(
                analysis
            )
        )

        self.assertEqual(
            len(targets),
            2,
        )

        self.assertTrue(
            all(
                target.source_variable
                == "Hardness H"
                for target in targets
            )
        )

    def test_02_explicit_mapping_replaces_variable(
        self,
    ):
        analysis = build_analysis()

        decisions = {
            candidate.candidate_id: {
                "Hardness H": "H"
            }
            for candidate
            in analysis.candidates
        }

        mapped = (
            apply_analysis_variable_mappings(
                analysis,
                decisions,
            )
        )

        self.assertTrue(
            all(
                candidate.extraction[
                    "variable"
                ]
                == "H"
                for candidate
                in mapped.candidates
            )
        )

        self.assertTrue(
            all(
                candidate.adapter_accepted
                for candidate
                in mapped.candidates
            )
        )

    def test_03_original_analysis_is_not_mutated(
        self,
    ):
        analysis = build_analysis()

        decisions = {
            candidate.candidate_id: {
                "Hardness H": "H"
            }
            for candidate
            in analysis.candidates
        }

        apply_analysis_variable_mappings(
            analysis,
            decisions,
        )

        self.assertTrue(
            all(
                candidate.extraction[
                    "variable"
                ]
                == "Hardness H"
                for candidate
                in analysis.candidates
            )
        )

    def test_04_missing_mapping_fails_safe(
        self,
    ):
        analysis = build_analysis()

        with self.assertRaises(
            ValueError
        ):
            apply_analysis_variable_mappings(
                analysis,
                {},
            )


if __name__ == "__main__":
    unittest.main()
