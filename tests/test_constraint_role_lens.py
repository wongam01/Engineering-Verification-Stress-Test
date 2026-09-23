import unittest

from src.ai.multi_constraint_parser import (
    build_constraint_role_directive,
)


class ConstraintRoleLensTest(unittest.TestCase):
    def test_requirement_lens_is_normative(self):
        prompt = build_constraint_role_directive(
            "requirement"
        )

        self.assertIn(
            "REQUIREMENT",
            prompt,
        )
        self.assertIn(
            "normative",
            prompt,
        )
        self.assertIn(
            "inspection / verification / acceptance",
            prompt,
        )

    def test_verification_lens_requires_acceptance_context(self):
        prompt = build_constraint_role_directive(
            "verification"
        )

        self.assertIn(
            "VERIFICATION",
            prompt,
        )
        self.assertIn(
            "합격·불합격",
            prompt,
        )
        self.assertIn(
            "Requirement와 Verification Criterion",
            prompt,
        )

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            build_constraint_role_directive(
                "unknown"
            )


if __name__ == "__main__":
    unittest.main()
