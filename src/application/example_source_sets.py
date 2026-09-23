from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class ExampleSourceFile:
    filename: str
    relative_path: str


@dataclass(frozen=True)
class ExampleSourceSet:
    key: str
    title: str
    description: str
    files: tuple[ExampleSourceFile, ...]


@dataclass(frozen=True)
class LoadedExampleSource:
    filename: str
    content: bytes
    sha256: str


FORD_REAL_WORLD_SOURCE_SET = ExampleSourceSet(
    key="ford_nano_valve_public_records",
    title="Ford Nano Intake Valve Hardness",
    description=(
        "Original public engineering records. "
        "The manifest identifies source files only; "
        "engineering roles and numeric constraints "
        "are discovered by the generic pipeline."
    ),
    files=(
        ExampleSourceFile(
            "INRD-EA23002-13504P1.pdf",
            "validation/real_case_02_ford/source/"
            "INRD-EA23002-13504P1.pdf",
        ),
        ExampleSourceFile(
            "INRD-EA23002-13506.pdf",
            "validation/real_case_02_ford/source/"
            "INRD-EA23002-13506.pdf",
        ),
        ExampleSourceFile(
            "INRD-EA23002-13508P1.pdf",
            "validation/real_case_02_ford/source/"
            "INRD-EA23002-13508P1.pdf",
        ),
        ExampleSourceFile(
            "INRL-EA23002-13503.pdf",
            "validation/real_case_02_ford/source/"
            "INRL-EA23002-13503.pdf",
        ),
    ),
)


def load_example_source_set(
    source_set: ExampleSourceSet,
    *,
    repository_root: Path | None = None,
) -> tuple[LoadedExampleSource, ...]:
    root = (
        repository_root
        if repository_root is not None
        else Path(__file__).resolve().parents[2]
    )

    loaded = []

    for source in source_set.files:
        source_path = (
            root / source.relative_path
        )

        if not source_path.is_file():
            raise FileNotFoundError(
                "Example source file not found: "
                + str(source_path)
            )

        content = source_path.read_bytes()

        loaded.append(
            LoadedExampleSource(
                filename=source.filename,
                content=content,
                sha256=hashlib.sha256(
                    content
                ).hexdigest(),
            )
        )

    return tuple(loaded)
