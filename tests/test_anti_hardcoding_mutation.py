import unittest

from src.application.escape_execution import (
    run_escape_core_pipeline,
)
from src.core.models import EngineeringCase


def build_mutation_case(
    *,
    name="Generic Pressure Case",
    variable="P",
    unit="MPa",
    feasible_min="3.2",
    feasible_max="3.5",
    requirement_min="2.0",
    requirement_max="3.0",
    verification_min="2.0",
    source_reference="mutation_evidence:generic",
):
    """
    Generic single-variable case for anti-hardcoding validation.

    Formal question:
        exists x:
        F(x) and V(x) and not R(x)

    No Ford-specific filename, variable, unit, or numeric boundary
    is required by this fixture.
    """

    return EngineeringCase.from_dict(
        {
            "name": name,
            "variables": {
                variable: {
                    "unit": unit,
                    "feasible_min": feasible_min,
                    "feasible_max": feasible_max,
                    "feasible_evidence": {
                        "source_type": "observed_test_data",
                        "source_reference": source_reference,
                        "approval_status": "approved",
                    },
                },
            },
            "requirements": [
                {
                    "id": "R_GENERIC",
                    "type": "range",
                    "unit": unit,
                    "variable": variable,
                    "min": requirement_min,
                    "max": requirement_max,
                    "description": (
                        "Generic engineering requirement"
                    ),
                },
            ],
            "verification_constraints": [
                {
                    "id": "V_GENERIC",
                    "type": "lower_bound",
                    "unit": unit,
                    "variable": variable,
                    "min": verification_min,
                    "description": (
                        "Generic acceptance criterion"
                    ),
                },
            ],
        }
    )


def solve(case):
    result = run_escape_core_pipeline(
        case,
        generate_patches=False,
    )

    stress = (
        result
        .requirement_results[0]
        .stress_result
    )

    return result, stress


class AntiHardcodingMutationTest(
    unittest.TestCase
):
    def test_01_feasible_domain_mutation_flips_result(self):
        escape_case = build_mutation_case(
            feasible_min="3.2",
            feasible_max="3.5",
        )

        safe_case = build_mutation_case(
            feasible_min="2.2",
            feasible_max="2.8",
        )

        escape_result, escape_stress = solve(
            escape_case
        )
        safe_result, safe_stress = solve(
            safe_case
        )

        self.assertEqual(
            escape_result.status,
            "VERIFICATION_GAP_FOUND",
        )
        self.assertTrue(
            escape_stress.escape_found
        )

        self.assertEqual(
            safe_result.status,
            "NO_ESCAPE_FOUND",
        )
        self.assertFalse(
            safe_stress.escape_found
        )

    def test_02_requirement_mutation_flips_result(self):
        narrow_requirement = build_mutation_case(
            requirement_max="3.0",
        )

        widened_requirement = build_mutation_case(
            requirement_max="4.0",
        )

        narrow_result, narrow_stress = solve(
            narrow_requirement
        )
        wide_result, wide_stress = solve(
            widened_requirement
        )

        self.assertEqual(
            narrow_result.status,
            "VERIFICATION_GAP_FOUND",
        )
        self.assertTrue(
            narrow_stress.escape_found
        )

        self.assertEqual(
            wide_result.status,
            "NO_ESCAPE_FOUND",
        )
        self.assertFalse(
            wide_stress.escape_found
        )

    def test_03_variable_name_and_unit_are_generic(self):
        pressure_case = build_mutation_case(
            name="Pressure Mutation Case",
            variable="P",
            unit="MPa",
            source_reference=(
                "pressure_test:record_01"
            ),
        )

        temperature_case = build_mutation_case(
            name="Temperature Mutation Case",
            variable="T",
            unit="degC",
            source_reference=(
                "temperature_test:record_77"
            ),
        )

        pressure_result, pressure_stress = solve(
            pressure_case
        )
        temperature_result, temperature_stress = solve(
            temperature_case
        )

        self.assertEqual(
            pressure_result.status,
            "VERIFICATION_GAP_FOUND",
        )
        self.assertEqual(
            temperature_result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            pressure_stress.escape_found
        )
        self.assertTrue(
            temperature_stress.escape_found
        )

        self.assertIn(
            "P",
            pressure_stress.state,
        )
        self.assertNotIn(
            "T",
            pressure_stress.state,
        )

        self.assertIn(
            "T",
            temperature_stress.state,
        )
        self.assertNotIn(
            "P",
            temperature_stress.state,
        )

    def test_04_case_and_source_identity_do_not_change_math(self):
        alpha_case = build_mutation_case(
            name="Alpha Engineering Record",
            source_reference=(
                "alpha_document.pdf#page=4"
            ),
        )

        beta_case = build_mutation_case(
            name="Completely Different Case Name",
            source_reference=(
                "unrelated_source_xyz.pdf#page=91"
            ),
        )

        alpha_result, alpha_stress = solve(
            alpha_case
        )
        beta_result, beta_stress = solve(
            beta_case
        )

        self.assertEqual(
            alpha_result.status,
            beta_result.status,
        )
        self.assertEqual(
            alpha_result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            alpha_stress.escape_found
        )
        self.assertTrue(
            beta_stress.escape_found
        )


if __name__ == "__main__":
    unittest.main()
