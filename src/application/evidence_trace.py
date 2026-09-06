import re
from collections.abc import Sequence


_PAGE_MARKER_PATTERN = re.compile(
    r"(?m)^\s*===== PDF PAGE (\d+) =====\s*$"
)


def extract_explicit_source_pages(
    source_text: str,
) -> tuple[int, ...]:
    """
    source_text 안에 명시적으로 보존된
    synthetic PDF page marker만 읽는다.

    페이지 번호를 추측하지 않는다.
    """

    pages: list[int] = []
    seen: set[int] = set()

    for match in _PAGE_MARKER_PATTERN.finditer(
        source_text
    ):
        page = int(
            match.group(1)
        )

        if page <= 0:
            continue

        if page in seen:
            continue

        seen.add(page)
        pages.append(page)

    return tuple(pages)


def select_single_source_page(
    source_pages: Sequence[int],
) -> int | None:
    """
    정확히 하나의 명시적 page만 확인된 경우에만
    source_page 단일값을 제공한다.

    여러 page에 걸친 evidence라면
    단일 page라고 축약하지 않는다.
    """

    if len(source_pages) != 1:
        return None

    return int(
        source_pages[0]
    )


def build_source_reference(
    *,
    source_name: str,
    source_block_id: str | None,
    source_pages: Sequence[int],
) -> str | None:
    """
    사람이 읽을 수 있는 deterministic source reference.

    예:
    requirement.pdf:p3:L2
    requirement.pdf:p3,p4:L2
    requirement.pdf:L2
    """

    parts = [
        source_name
    ]

    if source_pages:
        pages = ",".join(
            f"p{page}"
            for page in source_pages
        )

        parts.append(
            pages
        )

    if source_block_id:
        parts.append(
            source_block_id
        )

    if len(parts) == 1:
        return None

    return ":".join(
        parts
    )
