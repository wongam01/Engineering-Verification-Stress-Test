import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.application.role_grounding import (
    evaluate_candidate_role_grounding,
)


class RoleGroundingCacheIntegrationTest(unittest.TestCase):
    def test_default_evaluator_reuses_cached_payload(self):
        calls = []

        def fake_evaluator(
            source_text,
            proposed_role,
            source_name,
        ):
            calls.append(
                (
                    source_text,
                    proposed_role,
                    source_name,
                )
            )

            return {
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_NORMATIVE_REQUIREMENT"
                ),
                "explanation": (
                    "The source explicitly states "
                    "a normative requirement."
                ),
                "supporting_text": (
                    "Pressure shall be >= 5 bar."
                ),
            }

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            with patch(
                "src.ai.role_grounding_cache."
                "default_role_grounding_cache_dir",
                return_value=cache_dir,
            ):
                with patch(
                    "src.ai.role_grounding_evaluator."
                    "evaluate_role_grounding_from_source",
                    side_effect=fake_evaluator,
                ):
                    first = (
                        evaluate_candidate_role_grounding(
                            candidate_id="candidate-1",
                            proposed_role="requirement",
                            source_text=(
                                "Pressure shall be >= 5 bar."
                            ),
                            source_name="source.pdf",
                        )
                    )

                    second = (
                        evaluate_candidate_role_grounding(
                            candidate_id="candidate-2",
                            proposed_role="requirement",
                            source_text=(
                                "Pressure shall be >= 5 bar."
                            ),
                            source_name="source.pdf",
                        )
                    )

        self.assertEqual(
            len(calls),
            1,
        )

        self.assertEqual(
            first.status,
            "SUPPORTED",
        )

        self.assertEqual(
            second.status,
            "SUPPORTED",
        )

        self.assertEqual(
            first.candidate_id,
            "candidate-1",
        )

        self.assertEqual(
            second.candidate_id,
            "candidate-2",
        )

    def test_custom_evaluator_bypasses_persistent_cache(self):
        calls = []

        def custom_evaluator(
            source_text,
            proposed_role,
            source_name,
        ):
            calls.append(1)

            return {
                "status": "SUPPORTED",
                "basis_type": "TEST",
                "explanation": "supported",
                "supporting_text": (
                    "Pressure shall be >= 5 bar."
                ),
            }

        for candidate_id in (
            "candidate-1",
            "candidate-2",
        ):
            result = evaluate_candidate_role_grounding(
                candidate_id=candidate_id,
                proposed_role="requirement",
                source_text=(
                    "Pressure shall be >= 5 bar."
                ),
                source_name="source.pdf",
                evaluator=custom_evaluator,
            )

            self.assertEqual(
                result.status,
                "SUPPORTED",
            )

        self.assertEqual(
            len(calls),
            2,
        )


if __name__ == "__main__":
    unittest.main()
