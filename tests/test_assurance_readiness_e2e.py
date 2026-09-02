import unittest

from src.core.assurance_readiness import (
    evaluate_assurance_readiness,
)

from src.core.json_io import (
    load_engineering_case,
)


class AssuranceReadinessE2ETest(
    unittest.TestCase
):

    def test_heating_skid_is_assurance_ready(
        self,
    ):
        # =================================================
        # LOAD REAL DEMO CASE
        # =================================================

        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        # =================================================
        # ASSURANCE READINESS
        # =================================================

        result = (
            evaluate_assurance_readiness(
                case
            )
        )

        self.assertTrue(
            result.ready
        )

        self.assertEqual(
            result.status,
            "READY",
        )

        self.assertEqual(
            result.issues,
            [],
        )

        # =================================================
        # F SOURCE TRACEABILITY
        # =================================================

        self.assertEqual(
            len(case.variables),
            5,
        )

        for (
            variable_name,
            variable,
        ) in case.variables.items():

            evidence = (
                variable.feasible_evidence
            )

            self.assertIsNotNone(
                evidence,
                msg=(
                    f"{variable_name} "
                    "has no F evidence"
                ),
            )

            self.assertEqual(
                evidence.source_type,
                "engineer_assumption",
            )

            self.assertEqual(
                evidence.approval_status,
                "approved",
            )

            self.assertTrue(
                evidence.source_reference
            )

        # =================================================
        # CORE CASE STILL PRESERVED
        # =================================================

        self.assertEqual(
            case.name,
            "Heating Skid Verification Case",
        )


if __name__ == "__main__":
    unittest.main()