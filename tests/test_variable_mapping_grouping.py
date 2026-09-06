import unittest

from src.application.variable_mapping import (
    normalize_source_variable_group_key,
)


class VariableMappingGroupingTest(
    unittest.TestCase
):
    def test_natural_language_case_variation_groups(
        self,
    ):
        self.assertEqual(
            normalize_source_variable_group_key(
                "Hardness H"
            ),
            normalize_source_variable_group_key(
                "hardness H"
            ),
        )

    def test_natural_language_whitespace_groups(
        self,
    ):
        self.assertEqual(
            normalize_source_variable_group_key(
                "Hardness   H"
            ),
            normalize_source_variable_group_key(
                "Hardness H"
            ),
        )

    def test_symbol_case_is_preserved(
        self,
    ):
        self.assertNotEqual(
            normalize_source_variable_group_key(
                "H"
            ),
            normalize_source_variable_group_key(
                "h"
            ),
        )


if __name__ == "__main__":
    unittest.main()
