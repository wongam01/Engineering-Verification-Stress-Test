import json
import unittest
from pathlib import Path

from src.application.gap_classification import (
    ACCEPTANCE_BOUNDARY_GAP,
    CLASSIFIED,
    COVERAGE_GAP,
    INDETERMINATE,
    NO_GAP,
    NOT_EVALUATED,
    PARTIALLY_CLASSIFIED,
    RELATIONAL_ACCEPTANCE_BOUNDARY_GAP,
    REVIEW_REQUIRED,
    UNCLASSIFIED,
    classify_verification_gap,
)
from src.application.escape_execution import (
    run_verification_escape_workflow,
)
from src.application.formal_review import (
    build_exact_approved_review_records,
)
from src.core.models import EngineeringCase
from src.core.pipeline import (
    PipelineResult,
    RequirementPipelineResult,
)
from src.core.stress_tester import StressTestResult
from src.core.validator import ValidationResult
from src.core.review_completeness import (
    build_required_review_targets,
)


ROOT = Path(__file__).resolve().parents[1]


def build_case(
    requirements,
    verification_constraints=(),
    variables=None,
):
    if variables is None:
        variables = {
            "H": {
                "unit": "HRC",
                "feasible_min": "40",
                "feasible_max": "70",
            }
        }

    return EngineeringCase.from_dict(
        {
            "name": "Controlled 4E fixture",
            "variables": variables,
            "requirements": list(requirements),
            "verification_constraints": list(
                verification_constraints
            ),
        }
    )


def pipeline_result(*stress_results):
    requirement_results = [
        RequirementPipelineResult(
            requirement_id=stress.requirement_id,
            stress_result=stress,
        )
        for stress in stress_results
    ]

    if any(item.escape_found for item in stress_results):
        status = "VERIFICATION_GAP_FOUND"
    elif any(
        item.solver_status == "UNKNOWN"
        for item in stress_results
    ):
        status = "SOLVER_INDETERMINATE"
    else:
        status = "NO_ESCAPE_FOUND"

    return PipelineResult(
        status=status,
        validation=ValidationResult(valid=True),
        requirement_results=requirement_results,
    )


def stress(
    requirement_id,
    requirement_type,
    *,
    escape_found=True,
    direction="above_maximum",
    solver_status="SOLVED",
):
    return StressTestResult(
        requirement_id=requirement_id,
        requirement_type=requirement_type,
        escape_found=escape_found,
        direction=direction,
        solver_status=solver_status,
    )


class GapClassificationTest(unittest.TestCase):
    def test_ford_like_upper_escape_is_acceptance_boundary_gap(
        self,
    ):
        case = build_case(
            requirements=[
                {
                    "id": "R_HARDNESS",
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "max": "57",
                }
            ],
            variables={
                "H": {
                    "unit": "HRC",
                    "feasible_min": "40",
                    "feasible_max": "70",
                    "verification_min": "50",
                }
            },
        )

        report = classify_verification_gap(
            case,
            pipeline_result(
                stress("R_HARDNESS", "range")
            ),
        )

        item = report.items[0]
        self.assertEqual(report.status, CLASSIFIED)
        self.assertEqual(item.status, CLASSIFIED)
        self.assertEqual(
            item.classification_code,
            ACCEPTANCE_BOUNDARY_GAP,
        )
        self.assertEqual(
            item.verification_ids,
            ("variable:H",),
        )
        self.assertEqual(
            str(item.effective_verification_lower),
            "50",
        )
        self.assertIsNone(
            item.effective_verification_upper
        )

    def test_scalar_atoms_form_deterministic_effective_interval(
        self,
    ):
        case = build_case(
            requirements=[
                {
                    "id": "R1",
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "max": "57",
                }
            ],
            verification_constraints=[
                {
                    "id": "V_LOWER_1",
                    "type": "lower_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "48",
                },
                {
                    "id": "V_LOWER_2",
                    "type": "lower_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "51",
                },
                {
                    "id": "V_RANGE",
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "49",
                    "max": "62",
                },
                {
                    "id": "V_UPPER",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "60",
                },
            ],
        )

        item = classify_verification_gap(
            case,
            pipeline_result(stress("R1", "range")),
        ).items[0]

        self.assertEqual(
            str(item.effective_verification_lower),
            "51",
        )
        self.assertEqual(
            str(item.effective_verification_upper),
            "60",
        )
        self.assertEqual(
            item.verification_ids,
            (
                "V_LOWER_1",
                "V_LOWER_2",
                "V_RANGE",
                "V_UPPER",
            ),
        )

    def test_4d_thermal_is_relational_boundary_gap(self):
        data = json.loads(
            (
                ROOT
                / "demos"
                / "unseen_4d_thermal_balance"
                / "expected_case.json"
            ).read_text(encoding="utf-8")
        )
        case = EngineeringCase.from_dict(data)

        item = classify_verification_gap(
            case,
            pipeline_result(
                stress(
                    "R_BALANCE",
                    "abs_difference_max",
                )
            ),
        ).items[0]

        self.assertEqual(
            item.classification_code,
            RELATIONAL_ACCEPTANCE_BOUNDARY_GAP,
        )
        self.assertEqual(
            str(item.effective_verification_upper),
            "5",
        )
        self.assertEqual(
            item.verification_ids,
            ("V_BALANCE",),
        )

    def test_existing_escape_workflow_exposes_classification_report(
        self,
    ):
        data = json.loads(
            (
                ROOT
                / "demos"
                / "unseen_4d_thermal_balance"
                / "expected_case.json"
            ).read_text(encoding="utf-8")
        )
        case = EngineeringCase.from_dict(data)
        targets = build_required_review_targets(case)
        records = build_exact_approved_review_records(
            targets,
            "4E-CONTROLLED-REVIEWER",
            True,
            reviewed_at="2026-09-07T00:00:00+00:00",
        )

        result = run_verification_escape_workflow(
            case,
            records,
            generate_patches=False,
        )

        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )
        self.assertIsNotNone(result.gap_classification)
        self.assertEqual(
            result.gap_classification.status,
            CLASSIFIED,
        )
        self.assertEqual(
            result.to_dict()["gap_classification"]["items"][0][
                "classification_code"
            ],
            RELATIONAL_ACCEPTANCE_BOUNDARY_GAP,
        )

    def test_difference_min_uses_maximum_verification_minimum(
        self,
    ):
        variables = {
            name: {
                "unit": "bar",
                "feasible_min": "0",
                "feasible_max": "20",
            }
            for name in ("P_IN", "P_OUT")
        }
        case = build_case(
            requirements=[
                {
                    "id": "R_DIFF",
                    "type": "difference_min",
                    "unit": "bar",
                    "left": "P_IN",
                    "right": "P_OUT",
                    "min": "5",
                }
            ],
            verification_constraints=[
                {
                    "id": "V_DIFF_1",
                    "type": "difference_min",
                    "unit": "bar",
                    "left": "P_IN",
                    "right": "P_OUT",
                    "min": "2",
                },
                {
                    "id": "V_DIFF_2",
                    "type": "difference_min",
                    "unit": "bar",
                    "left": "P_IN",
                    "right": "P_OUT",
                    "min": "3",
                },
            ],
            variables=variables,
        )

        item = classify_verification_gap(
            case,
            pipeline_result(
                stress(
                    "R_DIFF",
                    "difference_min",
                    direction="below_minimum",
                )
            ),
        ).items[0]

        self.assertEqual(
            item.classification_code,
            RELATIONAL_ACCEPTANCE_BOUNDARY_GAP,
        )
        self.assertEqual(
            str(item.effective_verification_lower),
            "3",
        )

    def test_sum_upper_uses_minimum_verification_limit(self):
        variables = {
            name: {
                "unit": "kW",
                "feasible_min": "0",
                "feasible_max": "20",
            }
            for name in ("A", "B")
        }
        case = build_case(
            requirements=[
                {
                    "id": "R_SUM",
                    "type": "sum_upper",
                    "unit": "kW",
                    "variables": ["A", "B"],
                    "limit": "10",
                }
            ],
            verification_constraints=[
                {
                    "id": "V_SUM_1",
                    "type": "sum_upper",
                    "unit": "kW",
                    "variables": ["B", "A"],
                    "limit": "14",
                },
                {
                    "id": "V_SUM_2",
                    "type": "sum_upper",
                    "unit": "kW",
                    "variables": ["A", "B"],
                    "limit": "12",
                },
            ],
            variables=variables,
        )

        item = classify_verification_gap(
            case,
            pipeline_result(stress("R_SUM", "sum_upper")),
        ).items[0]

        self.assertEqual(
            item.classification_code,
            RELATIONAL_ACCEPTANCE_BOUNDARY_GAP,
        )
        self.assertEqual(
            str(item.effective_verification_upper),
            "12",
        )

    def test_missing_corresponding_verification_is_coverage_gap(
        self,
    ):
        case = build_case(
            requirements=[
                {
                    "id": "R_COVERAGE",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                }
            ]
        )

        item = classify_verification_gap(
            case,
            pipeline_result(
                stress("R_COVERAGE", "upper_bound")
            ),
        ).items[0]

        self.assertEqual(item.status, CLASSIFIED)
        self.assertEqual(item.classification_code, COVERAGE_GAP)
        self.assertTrue(item.missing_verification)

    def test_incompatible_relation_structures_require_review(
        self,
    ):
        variables = {
            name: {
                "unit": "degC",
                "feasible_min": "0",
                "feasible_max": "20",
            }
            for name in ("A", "B")
        }
        case = build_case(
            requirements=[
                {
                    "id": "R_ABS",
                    "type": "abs_difference_max",
                    "unit": "degC",
                    "left": "A",
                    "right": "B",
                    "limit": "2",
                }
            ],
            verification_constraints=[
                {
                    "id": "V_DIRECTIONAL",
                    "type": "difference_min",
                    "unit": "degC",
                    "left": "A",
                    "right": "B",
                    "min": "-5",
                }
            ],
            variables=variables,
        )

        report = classify_verification_gap(
            case,
            pipeline_result(
                stress("R_ABS", "abs_difference_max")
            ),
        )
        item = report.items[0]

        self.assertEqual(report.status, REVIEW_REQUIRED)
        self.assertEqual(item.status, REVIEW_REQUIRED)
        self.assertEqual(item.classification_code, UNCLASSIFIED)

    def test_no_escape_has_no_classification_code(self):
        case = build_case(
            requirements=[
                {
                    "id": "R1",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                }
            ]
        )

        report = classify_verification_gap(
            case,
            pipeline_result(
                stress(
                    "R1",
                    "upper_bound",
                    escape_found=False,
                    direction=None,
                )
            ),
        )

        self.assertEqual(report.status, NO_GAP)
        self.assertEqual(report.items[0].status, NO_GAP)
        self.assertIsNone(report.items[0].classification_code)

    def test_solver_unknown_is_indeterminate_not_no_gap(self):
        case = build_case(
            requirements=[
                {
                    "id": "R1",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                }
            ]
        )

        report = classify_verification_gap(
            case,
            pipeline_result(
                stress(
                    "R1",
                    "upper_bound",
                    escape_found=False,
                    direction=None,
                    solver_status="UNKNOWN",
                )
            ),
        )

        self.assertEqual(report.status, INDETERMINATE)
        self.assertEqual(report.items[0].status, INDETERMINATE)
        self.assertIsNone(report.items[0].classification_code)

    def test_unit_mismatch_fails_safe_without_conversion(self):
        case = build_case(
            requirements=[
                {
                    "id": "R1",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                }
            ],
            verification_constraints=[
                {
                    "id": "V1",
                    "type": "upper_bound",
                    "unit": "HV",
                    "variable": "H",
                    "max": "60",
                }
            ],
        )

        item = classify_verification_gap(
            case,
            pipeline_result(stress("R1", "upper_bound")),
        ).items[0]

        self.assertEqual(item.status, REVIEW_REQUIRED)
        self.assertEqual(item.classification_code, UNCLASSIFIED)
        self.assertIn("units", item.ambiguity_reasons[0])

    def test_multiple_same_family_v_uses_strictest_boundary(
        self,
    ):
        data = json.loads(
            (
                ROOT
                / "demos"
                / "unseen_4d_thermal_balance"
                / "expected_case.json"
            ).read_text(encoding="utf-8")
        )
        data["verification_constraints"].extend(
            [
                {
                    "id": "V_BALANCE_WIDE",
                    "type": "abs_difference_max",
                    "unit": "degC",
                    "left": "T_A",
                    "right": "T_B",
                    "limit": "8",
                },
                {
                    "id": "V_BALANCE_STRICTER",
                    "type": "abs_difference_max",
                    "unit": "degC",
                    "left": "T_B",
                    "right": "T_A",
                    "limit": "4",
                },
            ]
        )
        case = EngineeringCase.from_dict(data)

        item = classify_verification_gap(
            case,
            pipeline_result(
                stress(
                    "R_BALANCE",
                    "abs_difference_max",
                )
            ),
        ).items[0]

        self.assertEqual(item.status, CLASSIFIED)
        self.assertEqual(
            str(item.effective_verification_upper),
            "4",
        )
        self.assertEqual(
            item.verification_ids,
            (
                "V_BALANCE",
                "V_BALANCE_STRICTER",
                "V_BALANCE_WIDE",
            ),
        )

    def test_multiple_requirements_have_item_results_and_partial_report(
        self,
    ):
        case = build_case(
            requirements=[
                {
                    "id": "R_CLASSIFIED",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                },
                {
                    "id": "R_NO_GAP",
                    "type": "lower_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                },
                {
                    "id": "R_UNKNOWN",
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "max": "57",
                },
            ],
            verification_constraints=[
                {
                    "id": "V1",
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "max": "60",
                }
            ],
        )

        report = classify_verification_gap(
            case,
            pipeline_result(
                stress("R_CLASSIFIED", "upper_bound"),
                stress(
                    "R_NO_GAP",
                    "lower_bound",
                    escape_found=False,
                    direction=None,
                ),
                stress(
                    "R_UNKNOWN",
                    "range",
                    escape_found=False,
                    direction=None,
                    solver_status="UNKNOWN",
                ),
            ),
        )

        self.assertEqual(report.status, PARTIALLY_CLASSIFIED)
        self.assertEqual(
            [item.status for item in report.items],
            [CLASSIFIED, NO_GAP, INDETERMINATE],
        )

    def test_confirmed_escape_plus_ambiguity_is_partial(self):
        variables = {
            "H": {
                "unit": "HRC",
                "feasible_min": "40",
                "feasible_max": "70",
            },
            "A": {
                "unit": "degC",
                "feasible_min": "0",
                "feasible_max": "20",
            },
            "B": {
                "unit": "degC",
                "feasible_min": "0",
                "feasible_max": "20",
            },
        }
        case = build_case(
            requirements=[
                {
                    "id": "R_SCALAR",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                },
                {
                    "id": "R_RELATION",
                    "type": "abs_difference_max",
                    "unit": "degC",
                    "left": "A",
                    "right": "B",
                    "limit": "2",
                },
            ],
            verification_constraints=[
                {
                    "id": "V_SCALAR",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "60",
                },
                {
                    "id": "V_RELATION_INCOMPATIBLE",
                    "type": "difference_min",
                    "unit": "degC",
                    "left": "A",
                    "right": "B",
                    "min": "-5",
                },
            ],
            variables=variables,
        )

        report = classify_verification_gap(
            case,
            pipeline_result(
                stress("R_SCALAR", "upper_bound"),
                stress("R_RELATION", "abs_difference_max"),
            ),
        )

        self.assertEqual(report.status, PARTIALLY_CLASSIFIED)
        self.assertEqual(report.items[0].status, CLASSIFIED)
        self.assertEqual(report.items[1].status, REVIEW_REQUIRED)
        self.assertEqual(
            report.items[1].classification_code,
            UNCLASSIFIED,
        )

    def test_indeterminate_is_not_hidden_by_review_required(self):
        variables = {
            "H": {
                "unit": "HRC",
                "feasible_min": "40",
                "feasible_max": "70",
            },
            "A": {
                "unit": "degC",
                "feasible_min": "0",
                "feasible_max": "20",
            },
            "B": {
                "unit": "degC",
                "feasible_min": "0",
                "feasible_max": "20",
            },
        }
        case = build_case(
            requirements=[
                {
                    "id": "R_REVIEW",
                    "type": "abs_difference_max",
                    "unit": "degC",
                    "left": "A",
                    "right": "B",
                    "limit": "2",
                },
                {
                    "id": "R_UNKNOWN",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                },
            ],
            verification_constraints=[
                {
                    "id": "V_INCOMPATIBLE",
                    "type": "difference_min",
                    "unit": "degC",
                    "left": "A",
                    "right": "B",
                    "min": "-5",
                }
            ],
            variables=variables,
        )

        report = classify_verification_gap(
            case,
            pipeline_result(
                stress("R_REVIEW", "abs_difference_max"),
                stress(
                    "R_UNKNOWN",
                    "upper_bound",
                    escape_found=False,
                    direction=None,
                    solver_status="UNKNOWN",
                ),
            ),
        )

        self.assertEqual(report.status, INDETERMINATE)
        self.assertEqual(
            [item.status for item in report.items],
            [REVIEW_REQUIRED, INDETERMINATE],
        )

    def test_missing_pipeline_result_is_not_evaluated(self):
        case = build_case(
            requirements=[
                {
                    "id": "R1",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                }
            ]
        )

        report = classify_verification_gap(case, None)

        self.assertEqual(report.status, NOT_EVALUATED)
        self.assertEqual(report.items[0].status, NOT_EVALUATED)
        self.assertIsNone(report.items[0].classification_code)

    def test_pipeline_identity_mismatch_requires_review(self):
        case = build_case(
            requirements=[
                {
                    "id": "R1",
                    "type": "upper_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "max": "57",
                }
            ]
        )
        mismatched = RequirementPipelineResult(
            requirement_id="R1",
            stress_result=stress(
                "R_OTHER",
                "upper_bound",
            ),
        )
        result = PipelineResult(
            status="VERIFICATION_GAP_FOUND",
            validation=ValidationResult(valid=True),
            requirement_results=[mismatched],
        )

        report = classify_verification_gap(case, result)

        self.assertEqual(report.status, REVIEW_REQUIRED)
        self.assertEqual(report.items[0].status, REVIEW_REQUIRED)
        self.assertEqual(
            report.items[0].classification_code,
            UNCLASSIFIED,
        )


if __name__ == "__main__":
    unittest.main()
