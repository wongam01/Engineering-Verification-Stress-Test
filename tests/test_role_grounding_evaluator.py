import unittest
from types import SimpleNamespace

from src.ai.role_grounding_evaluator import (
    RoleGroundingAIOutput,
    evaluate_role_grounding_from_source,
)


class FakeResponses:

    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_parsed=self.parsed
        )


class FakeClient:

    def __init__(self, parsed):
        self.responses = FakeResponses(parsed)


class RoleGroundingEvaluatorTest(unittest.TestCase):

    def test_structured_grounding_call_preserves_role_and_source(self):
        parsed = RoleGroundingAIOutput(
            status="REJECTED",
            basis_type="OPERATIONAL_LIMIT",
            explanation=(
                "The source states an operating limit rather "
                "than an inspection acceptance criterion."
            ),
            supporting_text=(
                "Normal Operating Limit: 790 F"
            ),
        )

        client = FakeClient(parsed)

        result = evaluate_role_grounding_from_source(
            (
                "Normal Operating Limit: 790 F. "
                "The value is used during normal operation."
            ),
            "verification",
            "Marathon-style-source.pdf",
            client_override=client,
        )

        self.assertEqual(
            result["status"],
            "REJECTED",
        )
        self.assertEqual(
            result["basis_type"],
            "OPERATIONAL_LIMIT",
        )

        self.assertEqual(
            len(client.responses.calls),
            1,
        )

        call = client.responses.calls[0]
        system_prompt = call["input"][0]["content"]
        user_prompt = call["input"][1]["content"]

        self.assertIn(
            "normal operating limit",
            system_prompt.lower(),
        )
        self.assertIn(
            "acceptance",
            system_prompt.lower(),
        )
        self.assertIn(
            "PROPOSED_ROLE:\nverification",
            user_prompt,
        )
        self.assertIn(
            "Normal Operating Limit: 790 F",
            user_prompt,
        )

    def test_invalid_role_fails_safe_without_model_call(self):
        client = FakeClient(
            RoleGroundingAIOutput(
                status="SUPPORTED",
                basis_type="SHOULD_NOT_RUN",
                explanation="Should not run.",
                supporting_text="Should not run.",
            )
        )

        result = evaluate_role_grounding_from_source(
            "Some text",
            "operational",
            "source.pdf",
            client_override=client,
        )

        self.assertEqual(
            result["status"],
            "REVIEW_REQUIRED",
        )
        self.assertEqual(
            client.responses.calls,
            [],
        )

    def test_missing_source_text_fails_safe_without_model_call(self):
        client = FakeClient(
            RoleGroundingAIOutput(
                status="SUPPORTED",
                basis_type="SHOULD_NOT_RUN",
                explanation="Should not run.",
                supporting_text="Should not run.",
            )
        )

        result = evaluate_role_grounding_from_source(
            "",
            "verification",
            "source.pdf",
            client_override=client,
        )

        self.assertEqual(
            result["status"],
            "REVIEW_REQUIRED",
        )
        self.assertEqual(
            result["basis_type"],
            "SOURCE_TEXT_MISSING",
        )
        self.assertEqual(
            client.responses.calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
