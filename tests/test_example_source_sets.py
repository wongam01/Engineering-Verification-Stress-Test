import hashlib
import tempfile
import unittest
from pathlib import Path

from src.application.example_source_sets import (
    ExampleSourceFile,
    ExampleSourceSet,
    FORD_REAL_WORLD_SOURCE_SET,
    load_example_source_set,
)


class ExampleSourceSetTest(unittest.TestCase):
    def test_ford_manifest_contains_source_identity_only(self):
        source_set = FORD_REAL_WORLD_SOURCE_SET

        self.assertEqual(
            len(source_set.files),
            4,
        )

        for source in source_set.files:
            self.assertEqual(
                set(vars(source)),
                {
                    "filename",
                    "relative_path",
                },
            )

        self.assertEqual(
            len({
                source.relative_path
                for source in source_set.files
            }),
            4,
        )

    def test_loader_reads_exact_files_and_hashes_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "one.pdf").write_bytes(
                b"one"
            )
            (root / "two.pdf").write_bytes(
                b"two"
            )

            source_set = ExampleSourceSet(
                key="test",
                title="Test",
                description="Test source set",
                files=(
                    ExampleSourceFile(
                        filename="one.pdf",
                        relative_path="one.pdf",
                    ),
                    ExampleSourceFile(
                        filename="two.pdf",
                        relative_path="two.pdf",
                    ),
                ),
            )

            loaded = load_example_source_set(
                source_set,
                repository_root=root,
            )

            self.assertEqual(
                [item.filename for item in loaded],
                [
                    "one.pdf",
                    "two.pdf",
                ],
            )

            self.assertEqual(
                loaded[0].sha256,
                hashlib.sha256(
                    b"one"
                ).hexdigest(),
            )

            self.assertEqual(
                loaded[1].sha256,
                hashlib.sha256(
                    b"two"
                ).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
