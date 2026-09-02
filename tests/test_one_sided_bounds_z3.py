import unittest
from decimal import Decimal

from z3 import (
    Real,
    Solver,
    sat,
    unsat,
)

from src.core.constraint_engine import (
    Z3VariableSet,
    build_requirement_expression,
)
from src.core.models import RequirementSpec


class OneSidedBoundZ3Tests(unittest.TestCase):
    def make_variables(self):
        variable = Real("test_P")

        return (
            variable,
            Z3VariableSet(
                variables={
                    "P": variable,
                }
            ),
        )

    def test_lower_bound_builds_expected_metadata(self):
        _, z3_variables = self.make_variables()

        requirement = RequirementSpec.from_dict(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        expression = build_requirement_expression(
            requirement,
            z3_variables,
        )

        self.assertEqual(
            expression.requirement_id,
            "R1",
        )
        self.assertEqual(
            expression.requirement_type,
            "lower_bound",
        )
        self.assertEqual(
            expression.limit_value,
            Decimal("4"),
        )
        self.assertEqual(
            expression.violation_direction,
            "lower",
        )

    def test_lower_bound_passes_at_boundary(self):
        variable, z3_variables = self.make_variables()

        requirement = RequirementSpec.from_dict(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        expression = build_requirement_expression(
            requirement,
            z3_variables,
        )

        solver = Solver()
        solver.add(variable == 4)
        solver.add(expression.pass_condition)

        self.assertEqual(
            solver.check(),
            sat,
        )

    def test_lower_bound_fails_below_boundary(self):
        variable, z3_variables = self.make_variables()

        requirement = RequirementSpec.from_dict(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        expression = build_requirement_expression(
            requirement,
            z3_variables,
        )

        solver = Solver()
        solver.add(variable == 3)
        solver.add(expression.fail_condition)

        self.assertEqual(
            solver.check(),
            sat,
        )

    def test_upper_bound_builds_expected_metadata(self):
        _, z3_variables = self.make_variables()

        requirement = RequirementSpec.from_dict(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        expression = build_requirement_expression(
            requirement,
            z3_variables,
        )

        self.assertEqual(
            expression.requirement_id,
            "R2",
        )
        self.assertEqual(
            expression.requirement_type,
            "upper_bound",
        )
        self.assertEqual(
            expression.limit_value,
            Decimal("6"),
        )
        self.assertEqual(
            expression.violation_direction,
            "upper",
        )

    def test_upper_bound_passes_at_boundary(self):
        variable, z3_variables = self.make_variables()

        requirement = RequirementSpec.from_dict(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        expression = build_requirement_expression(
            requirement,
            z3_variables,
        )

        solver = Solver()
        solver.add(variable == 6)
        solver.add(expression.pass_condition)

        self.assertEqual(
            solver.check(),
            sat,
        )

    def test_upper_bound_fails_above_boundary(self):
        variable, z3_variables = self.make_variables()

        requirement = RequirementSpec.from_dict(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        expression = build_requirement_expression(
            requirement,
            z3_variables,
        )

        solver = Solver()
        solver.add(variable == 7)
        solver.add(expression.fail_condition)

        self.assertEqual(
            solver.check(),
            sat,
        )


if __name__ == "__main__":
    unittest.main()