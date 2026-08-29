import json
import unittest

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.method_case_io import (
    MethodCaseLoadError,
    load_method_case,
    run_method_case,
)


class TestMethodCaseIO(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sample_path = Path(
            "samples/cer_dent_method_case.json"
        )

        with cls.sample_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            cls.valid_case_data = json.load(file)

    # =====================================================
    # HELPER
    # =====================================================

    def load_temporary_case(
        self,
        case_data,
    ):
        """
        원본 CER JSON은 건드리지 않고,
        공격용 JSON을 임시 파일로 만들어 Loader에 넣는다.
        """

        with TemporaryDirectory() as temp_dir:
            path = (
                Path(temp_dir)
                / "method_case.json"
            )

            with path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    case_data,
                    file,
                    indent=2,
                )

            return load_method_case(path)

    # =====================================================
    # 1. VALID CER CASE
    # =====================================================

    def test_valid_cer_case_loads_and_runs(self):

        method_case, result = run_method_case(
            self.sample_path
        )

        self.assertEqual(
            method_case.case_id,
            "CER_DENT_A3",
        )

        self.assertEqual(
            method_case.case_name,
            "Pipeline Dent Fatigue Verification Method Cross-Check",
        )

        self.assertEqual(
            method_case.requirement.metric,
            "fatigue_life",
        )

        self.assertEqual(
            method_case.requirement.target,
            Decimal("150"),
        )

        self.assertEqual(
            len(method_case.methods),
            3,
        )

        self.assertEqual(
            method_case.methods[0].method,
            "INGAA_Table_6",
        )

        self.assertEqual(
            method_case.methods[0].role,
            "current_verification",
        )

        self.assertEqual(
            method_case.methods[1].method,
            "Kmax",
        )

        self.assertEqual(
            method_case.methods[1].role,
            "cross_check",
        )

        self.assertEqual(
            method_case.methods[2].method,
            "Kmax_OPS",
        )

        self.assertEqual(
            method_case.methods[2].role,
            "cross_check",
        )

        self.assertTrue(
            result.disagreement_found
        )

        self.assertFalse(
            result.indeterminate_found
        )

        self.assertTrue(
            result.verification_risk_found
        )

    # =====================================================
    # 2. INVALID ROLE
    # =====================================================

    def test_invalid_role_is_rejected(self):

        case_data = deepcopy(
            self.valid_case_data
        )

        case_data[
            "method_results"
        ][0]["role"] = "primary_method"

        with self.assertRaises(
            MethodCaseLoadError
        ):
            self.load_temporary_case(
                case_data
            )

    # =====================================================
    # 3. MISSING REQUIRED FIELD
    # =====================================================

    def test_missing_required_field_is_rejected(self):

        case_data = deepcopy(
            self.valid_case_data
        )

        del case_data[
            "method_results"
        ][0]["method"]

        with self.assertRaises(
            MethodCaseLoadError
        ):
            self.load_temporary_case(
                case_data
            )

    # =====================================================
    # 4. UNKNOWN METHOD FIELD
    # =====================================================

    def test_unknown_method_field_is_rejected(self):

        case_data = deepcopy(
            self.valid_case_data
        )

        case_data[
            "method_results"
        ][0][
            "unexpected_ai_field"
        ] = "hallucinated_value"

        with self.assertRaises(
            MethodCaseLoadError
        ):
            self.load_temporary_case(
                case_data
            )

    # =====================================================
    # 5. EMPTY METHOD RESULTS
    # =====================================================

    def test_empty_method_results_are_rejected(self):

        case_data = deepcopy(
            self.valid_case_data
        )

        case_data["method_results"] = []

        with self.assertRaises(
            MethodCaseLoadError
        ):
            self.load_temporary_case(
                case_data
            )

    # =====================================================
    # 6. BROKEN JSON
    # =====================================================

    def test_broken_json_is_rejected(self):

        with TemporaryDirectory() as temp_dir:
            path = (
                Path(temp_dir)
                / "broken_method_case.json"
            )

            path.write_text(
                """
                {
                    "case_id": "BROKEN",
                    "requirement": {
                        "metric": "fatigue_life"
                    },
                    "method_results": [
                """,
                encoding="utf-8",
            )

            with self.assertRaises(
                MethodCaseLoadError
            ):
                load_method_case(path)

    # =====================================================
    # 7. UNIT MISMATCH
    # =====================================================

    def test_unit_mismatch_is_rejected(self):

        case_data = deepcopy(
            self.valid_case_data
        )

        case_data[
            "method_results"
        ][1]["unit"] = "hours"

        with self.assertRaises(
            MethodCaseLoadError
        ):
            self.load_temporary_case(
                case_data
            )


if __name__ == "__main__":
    unittest.main()