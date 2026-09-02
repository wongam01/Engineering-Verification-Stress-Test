import unittest

from src.ai.multi_constraint_parser import (
    prepare_document_lines,
)


class DocumentPreprocessingTests(
    unittest.TestCase
):
    def test_existing_compact_requirement_ids_still_split(
        self,
    ):
        text = """R1. Temperature shall be at least 95 degC.
continued requirement text

R2. Pressure shall not exceed 5 bar.
"""

        prepared_text, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            2,
        )

        self.assertIn(
            "R1. Temperature shall be at least 95 degC.",
            source_map["L1"],
        )

        self.assertIn(
            "continued requirement text",
            source_map["L1"],
        )

        self.assertIn(
            "R2. Pressure shall not exceed 5 bar.",
            source_map["L2"],
        )

        self.assertIn(
            "L1:",
            prepared_text,
        )

        self.assertIn(
            "L2:",
            prepared_text,
        )

    def test_spaced_requirement_ids_split(
        self,
    ):
        text = """REQ 10: Temperature shall be at least 95 degC.

REQ 11: Pressure shall not exceed 5 bar.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            2,
        )

    def test_bracketed_engineering_ids_split(
        self,
    ):
        text = """a. [ABC 18] Proof pressure shall meet the requirement.

b. [ABC 19] Every unit shall be tested.

c. [ABC 20] All applicable parts shall be tested.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            3,
        )

        self.assertIn(
            "[ABC 18]",
            source_map["L1"],
        )

        self.assertIn(
            "[ABC 19]",
            source_map["L2"],
        )

        self.assertIn(
            "[ABC 20]",
            source_map["L3"],
        )

    def test_bracketed_heading_without_numeric_id_is_not_constraint(
        self,
    ):
        text = """[DESIGN SPECIFICATION]

R1. Temperature shall be at least 95 degC.

R2. Pressure shall not exceed 5 bar.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            2,
        )

        combined = "\n".join(
            source_map.values()
        )

        self.assertNotIn(
            "[DESIGN SPECIFICATION]",
            combined,
        )

    def test_line_wrapped_continuation_remains_with_requirement(
        self,
    ):
        text = """a. [ABC 18] Proof pressure shall be at least
1.5 times reference pressure for every applicable unit.

b. [ABC 19] Leak testing shall be performed.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            2,
        )

        self.assertIn(
            "1.5 times reference pressure",
            source_map["L1"],
        )

    def test_numeric_enumerator_before_bracketed_id_split(
        self,
    ):
        text = """b. [ABC 28] Main requirement.

(1) [ABC 29] First subordinate requirement.

(2) [ABC 30] Second subordinate requirement.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            3,
        )

        self.assertIn(
            "[ABC 28]",
            source_map["L1"],
        )

        self.assertIn(
            "[ABC 29]",
            source_map["L2"],
        )

        self.assertIn(
            "[ABC 30]",
            source_map["L3"],
        )

    def test_blank_separated_anonymous_paragraph_is_separate_block(
        self,
    ):
        text = """b. [ABC 19] This capability shall be demonstrated on every unit.
Pressure shall be applied individually to each line.

Included after every proof test is a leak test at 1.0e0 reference pressure.
The resulting leak rate shall be below 1e-6 cc/sec.

c. [ABC 20] All applicable parts shall be tested.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            3,
        )

        self.assertIn(
            "[ABC 19]",
            source_map["L1"],
        )

        self.assertNotIn(
            "Included after every proof test",
            source_map["L1"],
        )

        self.assertIn(
            "Included after every proof test",
            source_map["L2"],
        )

        self.assertNotIn(
            "[ABC 19]",
            source_map["L2"],
        )

        self.assertIn(
            "[ABC 20]",
            source_map["L3"],
        )

    def test_anonymous_multiline_paragraph_stays_together(
        self,
    ):
        text = """R1. Primary requirement.

Additional normative paragraph starts here.
Its second physical line remains in the same paragraph.

R2. Next requirement.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            3,
        )

        self.assertIn(
            "Additional normative paragraph starts here.",
            source_map["L2"],
        )

        self.assertIn(
            "Its second physical line remains in the same paragraph.",
            source_map["L2"],
        )

        self.assertNotIn(
            "R1.",
            source_map["L2"],
        )


    def test_incomplete_requirement_continues_across_synthetic_page_boundary(
        self,
    ):
        text = """R1. The proof test shall be applied externally to

===== PDF PAGE 2 =====

ENGINEERING SPECIFICATION

APPROVED FOR RELEASE

2 of 4

the housing until the test is complete.

R2. The next requirement shall be verified.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        self.assertEqual(
            len(source_map),
            2,
        )

        self.assertIn(
            "R1. The proof test shall be applied externally to",
            source_map["L1"],
        )

        self.assertIn(
            "the housing until the test is complete.",
            source_map["L1"],
        )

        self.assertIn(
            "===== PDF PAGE 2 =====",
            source_map["L1"],
        )

        self.assertIn(
            "R2. The next requirement",
            source_map["L2"],
        )

    def test_completed_requirement_does_not_absorb_next_page_anonymous_paragraph(
        self,
    ):
        text = """R1. The first requirement is complete.

===== PDF PAGE 2 =====

ENGINEERING SPECIFICATION

2 of 4

Independent normative paragraph on the next page.

R2. The second requirement is complete.
"""

        _, source_map = (
            prepare_document_lines(
                text
            )
        )

        r1_line_id = next(
            line_id
            for line_id, source_text
            in source_map.items()
            if "R1." in source_text
        )

        anonymous_line_id = next(
            line_id
            for line_id, source_text
            in source_map.items()
            if (
                "Independent normative paragraph"
                in source_text
            )
        )

        self.assertNotEqual(
            r1_line_id,
            anonymous_line_id,
        )

        self.assertNotIn(
            "Independent normative paragraph",
            source_map[
                r1_line_id
            ],
        )


if __name__ == "__main__":
    unittest.main()