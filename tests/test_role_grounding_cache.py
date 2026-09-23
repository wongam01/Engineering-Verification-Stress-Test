import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import sleep

from src.ai.role_grounding_cache import (
    cached_role_grounding_payload,
)


class RoleGroundingCacheTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp.name)

        self.impl = self.cache_dir / "evaluator.py"
        self.impl.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def call(
        self,
        *,
        role="requirement",
        source_text="Pressure shall be >= 5 bar.",
        compute,
    ):
        return cached_role_grounding_payload(
            source_text=source_text,
            proposed_role=role,
            source_name="source.pdf",
            model="test-model",
            implementation_files=(self.impl,),
            compute=compute,
            cache_dir=self.cache_dir,
        )

    def test_miss_then_hit_computes_once(self):
        calls = []

        def compute():
            calls.append(1)
            return {
                "status": "SUPPORTED",
                "basis_type": "TEST",
                "explanation": "supported",
                "supporting_text": "Pressure",
            }

        first = self.call(compute=compute)
        second = self.call(compute=compute)

        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)

    def test_role_changes_identity(self):
        calls = []

        def compute():
            calls.append(1)
            return {
                "status": "REVIEW_REQUIRED",
                "basis_type": "AMBIGUOUS_ROLE_CONTEXT",
                "explanation": "ambiguous",
                "supporting_text": "",
            }

        self.call(
            role="requirement",
            compute=compute,
        )

        self.call(
            role="verification",
            compute=compute,
        )

        self.assertEqual(len(calls), 2)

    def test_implementation_change_invalidates(self):
        calls = []

        def compute():
            calls.append(1)
            return {
                "status": "REJECTED",
                "basis_type": "TEST",
                "explanation": "rejected",
                "supporting_text": "Pressure",
            }

        self.call(compute=compute)

        self.impl.write_text(
            "VERSION = 2\n",
            encoding="utf-8",
        )

        self.call(compute=compute)

        self.assertEqual(len(calls), 2)

    def test_transient_error_is_not_cached(self):
        calls = []

        def failure():
            calls.append("failure")
            return {
                "status": "REVIEW_REQUIRED",
                "basis_type": "GROUNDING_EVALUATOR_ERROR",
                "explanation": "temporary",
                "supporting_text": "",
            }

        self.call(compute=failure)

        def success():
            calls.append("success")
            return {
                "status": "SUPPORTED",
                "basis_type": "TEST",
                "explanation": "supported",
                "supporting_text": "Pressure",
            }

        self.call(compute=success)

        self.assertEqual(
            calls,
            ["failure", "success"],
        )

    def test_parallel_same_key_computes_once(self):
        calls = []

        def compute():
            calls.append(1)
            sleep(0.02)
            return {
                "status": "SUPPORTED",
                "basis_type": "TEST",
                "explanation": "supported",
                "supporting_text": "Pressure",
            }

        with ThreadPoolExecutor(
            max_workers=4
        ) as executor:
            results = list(
                executor.map(
                    lambda _: self.call(
                        compute=compute
                    ),
                    range(4),
                )
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(results), 4)
        self.assertTrue(
            all(
                result == results[0]
                for result in results
            )
        )


if __name__ == "__main__":
    unittest.main()
