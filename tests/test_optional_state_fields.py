import unittest

from z3 import Solver, sat, unsat

from src.core.constraint_engine import (
    build_feasible_constraints,
    build_verification_constraints,
    create_z3_variables,
)
from src.core.models import EngineeringCase


class OptionalStateFieldTests(unittest.TestCase):

    def make_case(
        self,
        *,
        nominal=None,
        verification_min=None,
        verification_max=None,
        verification_constraints=None,
    ):
        variable = {
            "unit": "unit",
            "feasible_min": "0",
            "feasible_max": "10",
        }

        if nominal is not None:
            variable["nominal"] = nominal

        if verification_min is not None:
            variable["verification_min"] = (
                verification_min
            )

        if verification_max is not None:
            variable["verification_max"] = (
                verification_max
            )

        return EngineeringCase.from_dict(
            {
                "name": "optional state field test",
                "variables": {
                    "X": variable,
                },
                "requirements": [
                    {
                        "id": "R1",
                        "type": "range",
                        "unit": "unit",
                        "variable": "X",
                        "min": "2",
                        "max": "8",
                    }
                ],
                "verification_constraints": (
                    verification_constraints
                    or []
                ),
            }
        )

    def test_missing_nominal_is_none(self):
        case = self.make_case()

        self.assertIsNone(
            case.variables["X"].nominal
        )

    def test_missing_verification_bounds_are_none(
        self,
    ):
        case = self.make_case()

        self.assertIsNone(
            case.variables[
                "X"
            ].verification_min
        )

        self.assertIsNone(
            case.variables[
                "X"
            ].verification_max
        )

    def test_no_variable_verification_bounds_adds_no_constraints(
        self,
    ):
        case = self.make_case()

        variables = create_z3_variables(
            case,
            prefix="optional_none",
        )

        constraints = (
            build_verification_constraints(
                case,
                variables,
            )
        )

        self.assertEqual(
            constraints,
            [],
        )

    def test_lower_variable_bound_is_one_sided(
        self,
    ):
        case = self.make_case(
            verification_min="3",
        )

        variables = create_z3_variables(
            case,
            prefix="optional_lower",
        )

        solver = Solver()
        solver.add(
            *build_verification_constraints(
                case,
                variables,
            )
        )

        x = variables.get("X")

        solver.push()
        solver.add(x == 2)
        self.assertEqual(
            solver.check(),
            unsat,
        )
        solver.pop()

        solver.push()
        solver.add(x == 9)
        self.assertEqual(
            solver.check(),
            sat,
        )
        solver.pop()

    def test_upper_variable_bound_is_one_sided(
        self,
    ):
        case = self.make_case(
            verification_max="7",
        )

        variables = create_z3_variables(
            case,
            prefix="optional_upper",
        )

        solver = Solver()
        solver.add(
            *build_verification_constraints(
                case,
                variables,
            )
        )

        x = variables.get("X")

        solver.push()
        solver.add(x == 8)
        self.assertEqual(
            solver.check(),
            unsat,
        )
        solver.pop()

        solver.push()
        solver.add(x == 1)
        self.assertEqual(
            solver.check(),
            sat,
        )
        solver.pop()

    def test_relational_lower_bound_without_variable_range(
        self,
    ):
        case = self.make_case(
            verification_constraints=[
                {
                    "id": "V1",
                    "type": "lower_bound",
                    "unit": "unit",
                    "variable": "X",
                    "min": "3",
                }
            ],
        )

        variables = create_z3_variables(
            case,
            prefix="optional_relation",
        )

        solver = Solver()

        solver.add(
            *build_feasible_constraints(
                case,
                variables,
            )
        )

        solver.add(
            *build_verification_constraints(
                case,
                variables,
            )
        )

        x = variables.get("X")

        solver.push()
        solver.add(x == 5)
        self.assertEqual(
            solver.check(),
            sat,
        )
        solver.pop()

        solver.push()
        solver.add(x == 2)
        self.assertEqual(
            solver.check(),
            unsat,
        )
        solver.pop()


if __name__ == "__main__":
    unittest.main()
