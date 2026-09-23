from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any


CACHE_SCHEMA_VERSION = 1

NON_CACHEABLE_BASIS_TYPES = {
    "GROUNDING_EVALUATOR_ERROR",
    "GROUNDING_OUTPUT_MISSING",
}

_LOCK_GUARD = Lock()
_KEY_LOCKS: dict[str, Lock] = {}


def default_role_grounding_cache_dir() -> Path:
    return (
        Path.home()
        / ".cache"
        / "evst"
        / "role_grounding"
    )


def _sha256_text(value: str) -> str:
    return sha256(
        value.encode("utf-8")
    ).hexdigest()


def _implementation_sha256(
    file_paths: Iterable[str | Path],
) -> str:
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
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha.encode("ascii"))
        digest.update(b"\0")

    return digest.hexdigest()


def build_role_grounding_cache_identity(
    *,
    source_text: str,
    proposed_role: str,
    source_name: str,
    model: str,
    implementation_files: Iterable[str | Path],
) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "source_text_sha256": _sha256_text(
            source_text
        ),
        "proposed_role": proposed_role,
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
        else default_role_grounding_cache_dir()
    )

    return root / f"{key}.json"


def _load_path(
    path: Path,
    identity: Mapping[str, Any],
) -> dict[str, Any] | None:
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

    if payload.get("identity") != dict(identity):
        return None

    result = payload.get("result")

    if not isinstance(result, dict):
        return None

    return result


def load_role_grounding_cache(
    *,
    source_text: str,
    proposed_role: str,
    source_name: str,
    model: str,
    implementation_files: Iterable[str | Path],
    cache_dir: Path | None = None,
) -> dict[str, Any] | None:
    identity = build_role_grounding_cache_identity(
        source_text=source_text,
        proposed_role=proposed_role,
        source_name=source_name,
        model=model,
        implementation_files=implementation_files,
    )

    path = _cache_path(
        identity,
        cache_dir=cache_dir,
    )

    return _load_path(
        path,
        identity,
    )


def _store_path(
    path: Path,
    identity: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    payload = {
        "identity": dict(identity),
        "result": dict(result),
    }

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)

        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )

    temporary.replace(path)


def _lock_for_path(
    path: Path,
) -> Lock:
    key = str(path.resolve())

    with _LOCK_GUARD:
        lock = _KEY_LOCKS.get(key)

        if lock is None:
            lock = Lock()
            _KEY_LOCKS[key] = lock

        return lock


def cached_role_grounding_payload(
    *,
    source_text: str,
    proposed_role: str,
    source_name: str,
    model: str,
    implementation_files: Iterable[str | Path],
    compute: Callable[
        [],
        Mapping[str, Any],
    ],
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    implementation_files = tuple(
        implementation_files
    )

    identity = build_role_grounding_cache_identity(
        source_text=source_text,
        proposed_role=proposed_role,
        source_name=source_name,
        model=model,
        implementation_files=implementation_files,
    )

    path = _cache_path(
        identity,
        cache_dir=cache_dir,
    )

    cached = _load_path(
        path,
        identity,
    )

    if cached is not None:
        return cached

    lock = _lock_for_path(path)

    with lock:
        cached = _load_path(
            path,
            identity,
        )

        if cached is not None:
            return cached

        result = dict(
            compute()
        )

        basis_type = str(
            result.get(
                "basis_type",
                "",
            )
        ).strip()

        if basis_type in NON_CACHEABLE_BASIS_TYPES:
            return result

        _store_path(
            path,
            identity,
            result,
        )

        return result
