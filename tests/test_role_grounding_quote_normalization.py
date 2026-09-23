import unittest

from src.application.role_grounding import (
    evaluate_candidate_role_grounding,
)


SOURCE = (
    "Tip hardness inspection is a destructive test "
    "performed by a Rockwell C Indentation tester."
)


class RoleGroundingQuoteNormalizationTest(
    unittest.TestCase
):
    def test_wrapped_verbatim_quote_is_accepted(self):
        def evaluator(
            source_text,
            proposed_role,
            source_name,
        ):
            return {
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": "Explicit inspection criterion.",
                "supporting_text": (
                    "“" + SOURCE + "”"
                ),
            }

        result = evaluate_candidate_role_grounding(
            candidate_id="candidate-1",
            proposed_role="verification",
            source_text=SOURCE,
            source_name="source.pdf",
            evaluator=evaluator,
        )

        self.assertEqual(
            result.status,
            "SUPPORTED",
        )

    def test_changed_quote_is_still_blocked(self):
        def evaluator(
            source_text,
            proposed_role,
            source_name,
        ):
            return {
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": "Claimed support.",
                "supporting_text": (
                    "“Tip hardness automatically passes "
                    "inspection at 50 HRC.”"
                ),
            }

        result = evaluate_candidate_role_grounding(
            candidate_id="candidate-2",
            proposed_role="verification",
            source_text=SOURCE,
            source_name="source.pdf",
            evaluator=evaluator,
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )

        self.assertEqual(
            result.basis_type,
            "GROUNDING_SOURCE_TEXT_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
