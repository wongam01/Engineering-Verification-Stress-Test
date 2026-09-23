import tempfile
import unittest
from pathlib import Path

from src.ai.semantic_extraction_cache import (
    cached_semantic_extraction,
)


class SemanticExtractionCacheTest(
    unittest.TestCase
):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(
            self.temp.name
        )

        self.impl = (
            self.cache_dir
            / "parser.py"
        )

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
        text="Pressure shall be >= 5 bar.",
        source_name="source.pdf",
        compute,
    ):
        return cached_semantic_extraction(
            namespace="test",
            text=text,
            role=role,
            source_name=source_name,
            model="test-model",
            implementation_files=(
                self.impl,
            ),
            compute=compute,
            cache_dir=self.cache_dir,
        )

    def test_miss_then_hit_computes_once(self):
        calls = []

        def compute():
            calls.append(1)
            return [
                {
                    "constraint_id": "R1",
                }
            ]

        first = self.call(
            compute=compute
        )

        second = self.call(
            compute=compute
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            len(calls),
            1,
        )

    def test_role_changes_cache_identity(self):
        calls = []

        def compute():
            calls.append(1)
            return []

        self.call(
            role="requirement",
            compute=compute,
        )

        self.call(
            role="verification",
            compute=compute,
        )

        self.assertEqual(
            len(calls),
            2,
        )

    def test_parser_change_invalidates_cache(self):
        calls = []

        def compute():
            calls.append(1)
            return []

        self.call(
            compute=compute
        )

        self.impl.write_text(
            "VERSION = 2\n",
            encoding="utf-8",
        )

        self.call(
            compute=compute
        )

        self.assertEqual(
            len(calls),
            2,
        )

    def test_exception_is_not_cached(self):
        calls = []

        def fail():
            calls.append("fail")
            raise RuntimeError(
                "synthetic failure"
            )

        with self.assertRaises(
            RuntimeError
        ):
            self.call(
                compute=fail
            )

        def succeed():
            calls.append("success")
            return []

        self.call(
            compute=succeed
        )

        self.assertEqual(
            calls,
            [
                "fail",
                "success",
            ],
        )


if __name__ == "__main__":
    unittest.main()
