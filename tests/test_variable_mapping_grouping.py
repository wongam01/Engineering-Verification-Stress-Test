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

    def test_hardness_label_groups_with_symbol(
        self,
    ):
        self.assertEqual(
            normalize_source_variable_group_key(
                "Hardness H"
            ),
            normalize_source_variable_group_key(
                "H"
            ),
        )

    def test_pressure_label_groups_with_symbol(
        self,
    ):
        self.assertEqual(
            normalize_source_variable_group_key(
                "Pressure P"
            ),
            normalize_source_variable_group_key(
                "P"
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

    def test_label_symbol_case_is_preserved(
        self,
    ):
        self.assertNotEqual(
            normalize_source_variable_group_key(
                "Hardness H"
            ),
            normalize_source_variable_group_key(
                "h"
            ),
        )

    def test_regular_word_is_not_treated_as_symbol(
        self,
    ):
        self.assertNotEqual(
            normalize_source_variable_group_key(
                "Outlet Temperature"
            ),
            normalize_source_variable_group_key(
                "Temperature"
            ),
        )

    def test_mass_flow_is_not_grouped_with_flow(
        self,
    ):
        self.assertNotEqual(
            normalize_source_variable_group_key(
                "Mass Flow"
            ),
            normalize_source_variable_group_key(
                "Flow"
            ),
        )

    def test_explicit_identifier_forms_still_group(
        self,
    ):
        for label, symbol in [
            ("Temperature T", "T"),
            ("Temperature T1", "T1"),
            ("Inlet Pressure P_IN", "P_IN"),
        ]:
            with self.subTest(
                label=label,
                symbol=symbol,
            ):
                self.assertEqual(
                    normalize_source_variable_group_key(
                        label
                    ),
                    normalize_source_variable_group_key(
                        symbol
                    ),
                )

    def test_whitespace_variation_groups(
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


if __name__ == "__main__":
    unittest.main()
