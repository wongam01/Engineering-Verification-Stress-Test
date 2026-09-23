from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


CACHE_SCHEMA_VERSION = 1


def default_semantic_extraction_cache_dir() -> Path:
    return (
        Path.home()
        / ".cache"
        / "evst"
        / "semantic_extractions"
    )


def _sha256_text(value: str) -> str:
    return sha256(
        value.encode("utf-8")
    ).hexdigest()


def _implementation_sha256(
    file_paths: Iterable[str | Path],
) -> str:
    """
    Fingerprint the actual parser implementation.

    Prompt/model-processing code changes therefore invalidate
    persistent extraction cache entries automatically.
    """

    entries = []

    for raw_path in file_paths:
        path = Path(raw_path).resolve()

        if not path.is_file():
            raise FileNotFoundError(
                f"Implementation file not found: {path}"
            )

        entries.append(
            (
                path.name,
                sha256(
                    path.read_bytes()
                ).hexdigest(),
            )
        )

    digest = sha256()

    for name, file_sha in sorted(entries):
        digest.update(
            name.encode("utf-8")
        )
        digest.update(b"\0")
        digest.update(
            file_sha.encode("ascii")
        )
        digest.update(b"\0")

    return digest.hexdigest()


def build_semantic_extraction_cache_identity(
    *,
    namespace: str,
    text: str,
    role: str,
    source_name: str,
    model: str,
    implementation_files: Iterable[str | Path],
) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "namespace": namespace,
        "input_text_sha256": _sha256_text(text),
        "role": role,
        "source_name": source_name,
        "model": model,
        "implementation_sha256": (
            _implementation_sha256(
                implementation_files
            )
        ),
    }


def _cache_path(
    identity: Mapping[str, Any],
    *,
    cache_dir: Path | None,
) -> Path:
    canonical = json.dumps(
        dict(identity),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    key = sha256(
        canonical
    ).hexdigest()

    root = (
        Path(cache_dir)
        if cache_dir is not None
        else default_semantic_extraction_cache_dir()
    )

    return (
        root
        / str(identity["namespace"])
        / f"{key}.json"
    )


def load_semantic_extraction_cache(
    *,
    namespace: str,
    text: str,
    role: str,
    source_name: str,
    model: str,
    implementation_files: Iterable[str | Path],
    cache_dir: Path | None = None,
) -> list[dict[str, Any]] | None:
    identity = build_semantic_extraction_cache_identity(
        namespace=namespace,
        text=text,
        role=role,
        source_name=source_name,
        model=model,
        implementation_files=implementation_files,
    )

    path = _cache_path(
        identity,
        cache_dir=cache_dir,
    )

    if not path.is_file():
        return None

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return None

    if payload.get("identity") != identity:
        return None

    result = payload.get("result")

    if not isinstance(result, list):
        return None

    if not all(
        isinstance(item, dict)
        for item in result
    ):
        return None

    return result


def store_semantic_extraction_cache(
    result: list[dict[str, Any]],
    *,
    namespace: str,
    text: str,
    role: str,
    source_name: str,
    model: str,
    implementation_files: Iterable[str | Path],
    cache_dir: Path | None = None,
) -> None:
    if not isinstance(result, list):
        raise TypeError(
            "Semantic extraction result must be a list."
        )

    if not all(
        isinstance(item, dict)
        for item in result
    ):
        raise TypeError(
            "Semantic extraction items must be dictionaries."
        )

    identity = build_semantic_extraction_cache_identity(
        namespace=namespace,
        text=text,
        role=role,
        source_name=source_name,
        model=model,
        implementation_files=implementation_files,
    )

    path = _cache_path(
        identity,
        cache_dir=cache_dir,
    )

    payload = {
        "identity": identity,
        "result": result,
    }

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)


def cached_semantic_extraction(
    *,
    namespace: str,
    text: str,
    role: str,
    source_name: str,
    model: str,
    implementation_files: Iterable[str | Path],
    compute: Callable[
        [],
        list[dict[str, Any]],
    ],
    cache_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Persistent cache for AI semantic extraction only.

    Engineer approvals, Role Grounding, Formal Models,
    witnesses, and solver outcomes are intentionally outside
    this cache.
    """

    implementation_files = tuple(
        implementation_files
    )

    cached = load_semantic_extraction_cache(
        namespace=namespace,
        text=text,
        role=role,
        source_name=source_name,
        model=model,
        implementation_files=implementation_files,
        cache_dir=cache_dir,
    )

    if cached is not None:
        return cached

    result = compute()

    store_semantic_extraction_cache(
        result,
        namespace=namespace,
        text=text,
        role=role,
        source_name=source_name,
        model=model,
        implementation_files=implementation_files,
        cache_dir=cache_dir,
    )

    return result
