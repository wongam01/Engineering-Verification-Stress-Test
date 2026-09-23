from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path
from typing import Sequence

from src.ai.pdf_page_vision import (
    DEFAULT_RENDER_DPI,
    DEFAULT_VISION_MODEL,
    PAGE_TRANSCRIPTION_PROMPT,
    extract_pdf_page_with_vision,
    render_pdf_page_to_png,
)


CACHE_SCHEMA_VERSION = 1
DEFAULT_VISION_CACHE_WORKERS = 4


def default_vision_cache_dir() -> Path:
    configured = os.getenv(
        "EVST_VISION_CACHE_DIR",
        "",
    ).strip()

    if configured:
        return Path(configured).expanduser()

    return (
        Path.home()
        / ".cache"
        / "evst"
        / "vision_pages"
    )


def _prompt_sha256() -> str:
    return sha256(
        PAGE_TRANSCRIPTION_PROMPT.encode("utf-8")
    ).hexdigest()


def build_pdf_page_vision_cache_identity(
    pdf_bytes: bytes,
    *,
    page_number: int,
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
) -> dict[str, object]:
    if page_number < 1:
        raise ValueError(
            "page_number must be 1 or greater."
        )

    if dpi <= 0:
        raise ValueError(
            "dpi must be greater than zero."
        )

    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "pdf_sha256": sha256(pdf_bytes).hexdigest(),
        "page_number": page_number,
        "model": model,
        "dpi": dpi,
        "prompt_sha256": _prompt_sha256(),
    }


def build_pdf_page_vision_cache_key(
    pdf_bytes: bytes,
    *,
    page_number: int,
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
) -> str:
    identity = build_pdf_page_vision_cache_identity(
        pdf_bytes,
        page_number=page_number,
        model=model,
        dpi=dpi,
    )

    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return sha256(canonical).hexdigest()


def _cache_path(
    pdf_bytes: bytes,
    *,
    page_number: int,
    model: str,
    dpi: int,
    cache_dir: Path | None,
) -> Path:
    identity = build_pdf_page_vision_cache_identity(
        pdf_bytes,
        page_number=page_number,
        model=model,
        dpi=dpi,
    )

    cache_key = build_pdf_page_vision_cache_key(
        pdf_bytes,
        page_number=page_number,
        model=model,
        dpi=dpi,
    )

    root = (
        cache_dir
        if cache_dir is not None
        else default_vision_cache_dir()
    )

    return (
        Path(root)
        / str(identity["pdf_sha256"])
        / f"{cache_key}.json"
    )


def load_cached_pdf_page_transcription(
    pdf_bytes: bytes,
    *,
    page_number: int,
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
    cache_dir: Path | None = None,
) -> str | None:
    path = _cache_path(
        pdf_bytes,
        page_number=page_number,
        model=model,
        dpi=dpi,
        cache_dir=cache_dir,
    )

    if not path.is_file():
        return None

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None

    expected_identity = (
        build_pdf_page_vision_cache_identity(
            pdf_bytes,
            page_number=page_number,
            model=model,
            dpi=dpi,
        )
    )

    if payload.get("identity") != expected_identity:
        return None

    transcription = payload.get(
        "transcription"
    )

    if not isinstance(transcription, str):
        return None

    return transcription


def is_pdf_page_vision_cached(
    pdf_bytes: bytes,
    *,
    page_number: int,
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
    cache_dir: Path | None = None,
) -> bool:
    return (
        load_cached_pdf_page_transcription(
            pdf_bytes,
            page_number=page_number,
            model=model,
            dpi=dpi,
            cache_dir=cache_dir,
        )
        is not None
    )


def _write_cache_record(
    pdf_bytes: bytes,
    *,
    page_number: int,
    transcription: str,
    model: str,
    dpi: int,
    cache_dir: Path | None,
) -> None:
    path = _cache_path(
        pdf_bytes,
        page_number=page_number,
        model=model,
        dpi=dpi,
        cache_dir=cache_dir,
    )

    identity = build_pdf_page_vision_cache_identity(
        pdf_bytes,
        page_number=page_number,
        model=model,
        dpi=dpi,
    )

    payload = {
        "identity": identity,
        "transcription": transcription,
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


def _transcribe_rendered_png_with_vision(
    png_bytes: bytes,
    *,
    client,
    model: str = DEFAULT_VISION_MODEL,
) -> str:
    """
    Send an already-rendered PNG to the Vision model.

    PDF rendering intentionally happens outside worker threads.
    This keeps native PDFium work single-threaded while allowing
    the network-bound Vision requests to run concurrently.
    """

    encoded_png = base64.b64encode(
        png_bytes
    ).decode("ascii")

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": PAGE_TRANSCRIPTION_PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/png;base64,"
                            + encoded_png
                        ),
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    output_text = getattr(
        response,
        "output_text",
        "",
    )

    return (output_text or "").strip()


def extract_pdf_page_with_vision_cached(
    pdf_bytes: bytes,
    *,
    page_number: int,
    client,
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
    cache_dir: Path | None = None,
) -> str:
    cached = load_cached_pdf_page_transcription(
        pdf_bytes,
        page_number=page_number,
        model=model,
        dpi=dpi,
        cache_dir=cache_dir,
    )

    if cached is not None:
        return cached

    transcription = extract_pdf_page_with_vision(
        pdf_bytes,
        page_number=page_number,
        client=client,
        model=model,
        dpi=dpi,
    )

    _write_cache_record(
        pdf_bytes,
        page_number=page_number,
        transcription=transcription,
        model=model,
        dpi=dpi,
        cache_dir=cache_dir,
    )

    return transcription


def warm_pdf_page_vision_cache(
    pdf_bytes: bytes,
    *,
    page_numbers: Sequence[int],
    client,
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
    cache_dir: Path | None = None,
    max_workers: int = DEFAULT_VISION_CACHE_WORKERS,
) -> tuple[int, ...]:
    """
    Warm persistent Vision transcription cache safely.

    Native PDF rendering is always performed sequentially in the
    calling thread. Only already-rendered PNG Vision requests are
    run concurrently. This avoids concurrent PDFium access.
    """

    normalized_pages = tuple(
        sorted(set(page_numbers))
    )

    if any(
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        or page_number < 1
        for page_number in normalized_pages
    ):
        raise ValueError(
            "page_numbers must contain positive integers."
        )

    if max_workers < 1:
        raise ValueError(
            "max_workers must be at least 1."
        )

    if not normalized_pages:
        return ()

    pending_pages = tuple(
        page_number
        for page_number in normalized_pages
        if not is_pdf_page_vision_cached(
            pdf_bytes,
            page_number=page_number,
            model=model,
            dpi=dpi,
            cache_dir=cache_dir,
        )
    )

    if not pending_pages:
        return normalized_pages

    # -----------------------------------------------------
    # PHASE 1 — native PDF rendering.
    #
    # Deliberately single-threaded. pypdfium2/PDFium work
    # must never run concurrently in this cache warmer.
    # -----------------------------------------------------

    rendered_pages: list[
        tuple[int, bytes]
    ] = []

    for page_number in pending_pages:
        png_bytes = render_pdf_page_to_png(
            pdf_bytes,
            page_number=page_number,
            dpi=dpi,
        )

        rendered_pages.append(
            (
                page_number,
                png_bytes,
            )
        )

    # -----------------------------------------------------
    # PHASE 2 — network-bound Vision requests.
    #
    # At this point worker threads never touch PDFium.
    # -----------------------------------------------------

    worker_count = min(
        max_workers,
        len(rendered_pages),
    )

    def transcribe_and_cache(
        page_number: int,
        png_bytes: bytes,
    ) -> int:
        transcription = (
            _transcribe_rendered_png_with_vision(
                png_bytes,
                client=client,
                model=model,
            )
        )

        _write_cache_record(
            pdf_bytes,
            page_number=page_number,
            transcription=transcription,
            model=model,
            dpi=dpi,
            cache_dir=cache_dir,
        )

        return page_number

    if worker_count == 1:
        for page_number, png_bytes in rendered_pages:
            transcribe_and_cache(
                page_number,
                png_bytes,
            )

        return normalized_pages

    futures = {}

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as executor:
        for page_number, png_bytes in rendered_pages:
            future = executor.submit(
                transcribe_and_cache,
                page_number,
                png_bytes,
            )

            futures[future] = page_number

        for future in as_completed(futures):
            future.result()

    return normalized_pages

# =========================================================
# Prepared transcription bundle
#
# Page-level cache remains the durable source of truth.
# A bundle is only a performance index that groups all cached
# transcriptions for one physical PDF into one JSON read.
# =========================================================

def _normalize_bundle_pages(
    page_numbers: Sequence[int],
) -> tuple[int, ...]:
    normalized = tuple(
        sorted(set(page_numbers))
    )

    if any(
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        or page_number < 1
        for page_number in normalized
    ):
        raise ValueError(
            "page_numbers must contain positive integers."
        )

    return normalized


def build_pdf_vision_bundle_identity(
    pdf_bytes: bytes,
    *,
    page_numbers: Sequence[int],
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
) -> dict[str, object]:
    normalized_pages = _normalize_bundle_pages(
        page_numbers
    )

    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "pdf_sha256": sha256(pdf_bytes).hexdigest(),
        "page_numbers": list(normalized_pages),
        "model": model,
        "dpi": dpi,
        "prompt_sha256": _prompt_sha256(),
    }


def _bundle_path(
    pdf_bytes: bytes,
    *,
    page_numbers: Sequence[int],
    model: str,
    dpi: int,
    cache_dir: Path | None,
) -> Path:
    identity = build_pdf_vision_bundle_identity(
        pdf_bytes,
        page_numbers=page_numbers,
        model=model,
        dpi=dpi,
    )

    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    bundle_key = sha256(
        canonical
    ).hexdigest()

    root = (
        cache_dir
        if cache_dir is not None
        else default_vision_cache_dir()
    )

    return (
        Path(root)
        / str(identity["pdf_sha256"])
        / f"bundle-{bundle_key}.json"
    )


def load_pdf_vision_transcription_bundle(
    pdf_bytes: bytes,
    *,
    page_numbers: Sequence[int],
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
    cache_dir: Path | None = None,
) -> dict[int, str] | None:
    normalized_pages = _normalize_bundle_pages(
        page_numbers
    )

    if not normalized_pages:
        return {}

    path = _bundle_path(
        pdf_bytes,
        page_numbers=normalized_pages,
        model=model,
        dpi=dpi,
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

    expected_identity = (
        build_pdf_vision_bundle_identity(
            pdf_bytes,
            page_numbers=normalized_pages,
            model=model,
            dpi=dpi,
        )
    )

    if payload.get("identity") != expected_identity:
        return None

    raw_transcriptions = payload.get(
        "transcriptions"
    )

    if not isinstance(
        raw_transcriptions,
        dict,
    ):
        return None

    restored: dict[int, str] = {}

    for page_number in normalized_pages:
        value = raw_transcriptions.get(
            str(page_number)
        )

        if not isinstance(value, str):
            return None

        restored[page_number] = value

    return restored


def build_pdf_vision_transcription_bundle(
    pdf_bytes: bytes,
    *,
    page_numbers: Sequence[int],
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
    cache_dir: Path | None = None,
) -> dict[int, str] | None:
    """
    Build one aggregate transcription file from already-complete
    page-level cache records.

    No Vision API calls are made here.
    """

    normalized_pages = _normalize_bundle_pages(
        page_numbers
    )

    if not normalized_pages:
        return {}

    transcriptions: dict[int, str] = {}

    for page_number in normalized_pages:
        transcription = (
            load_cached_pdf_page_transcription(
                pdf_bytes,
                page_number=page_number,
                model=model,
                dpi=dpi,
                cache_dir=cache_dir,
            )
        )

        if transcription is None:
            return None

        transcriptions[
            page_number
        ] = transcription

    identity = build_pdf_vision_bundle_identity(
        pdf_bytes,
        page_numbers=normalized_pages,
        model=model,
        dpi=dpi,
    )

    path = _bundle_path(
        pdf_bytes,
        page_numbers=normalized_pages,
        model=model,
        dpi=dpi,
        cache_dir=cache_dir,
    )

    payload = {
        "identity": identity,
        "transcriptions": {
            str(page_number): transcription
            for page_number, transcription
            in transcriptions.items()
        },
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

    return transcriptions
