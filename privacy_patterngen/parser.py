"""
Parse PrivacyPatterns Markdown into structured data for skill generation.
"""

import re
from dataclasses import dataclass

from skillgen_common.markdown import (
    dedupe_keep_order,
    first_paragraph,
    strip_html_comments,
    strip_inline_markdown,
)


@dataclass
class PrivacyPatternSection:
    """A section from a privacy pattern source document."""

    heading: str
    body: str


@dataclass
class ParsedPrivacyPattern:
    """Structured representation used by privacy pattern templates and JSON."""

    title: str
    excerpt: str
    summary: str
    context: str
    problem: str
    solution: str
    consequences: str
    examples: str
    categories: list[str]
    status: str
    sections: list[PrivacyPatternSection]
    triggers: list[str]
    raw_filename: str
    source_path: str
    source_url: str


_METADATA_PATTERN = re.compile(r"\{%\s*hyde(?P<body>.*?)%\}", re.IGNORECASE | re.DOTALL)
_FIELD_PATTERN = re.compile(r"^\s*([a-z_]+):\s*(.*)\s*$")
_METADATA_FIELDS = "title|type|excerpt|categories|status|address|display_in_list"
_METADATA_SPAN_PATTERN = re.compile(
    rf"\b({_METADATA_FIELDS}):\s*(.*?)"
    rf"(?=\s+\b(?:{_METADATA_FIELDS}):|$)",
    re.IGNORECASE | re.DOTALL,
)
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)")
_CATEGORY_LIST_PATTERN = re.compile(r"^\s*-\s+(.+?)\s*$")

_COMMON_SECTION_NAMES = {
    "summary",
    "context",
    "problem",
    "solution",
    "consequences",
    "examples",
}


def _strip_html_comments(text: str) -> str:
    return strip_html_comments(text)


def _clean_metadata_value(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _parse_categories(value: str) -> list[str]:
    categories = [
        _clean_metadata_value(match.group(1))
        for line in value.splitlines()
        if (match := _CATEGORY_LIST_PATTERN.match(line))
    ]
    if categories:
        return categories

    if re.search(r"(^|\s)-\s+", value):
        categories = [
            _clean_metadata_value(category)
            for category in re.findall(r"-\s*([^-]+?)(?=\s+-|$)", value)
        ]
    elif "," in value:
        categories = [_clean_metadata_value(category) for category in value.split(",")]
    else:
        categories = [_clean_metadata_value(value)] if value.strip() else []

    return [category for category in categories if category]


def _clean_markdown(text: str) -> str:
    return strip_inline_markdown(text)


def _first_paragraph(text: str) -> str:
    return first_paragraph(text)


def _title_from_filename(filename: str) -> str:
    stem = filename.rsplit("/", maxsplit=1)[-1].removesuffix(".md")
    return _clean_markdown(stem.replace("-", " ").replace("_", " ")) or "Privacy Pattern"


def _metadata_to_dict(metadata_body: str) -> dict[str, object]:
    metadata: dict[str, object] = {}
    current_field = ""

    span_matches = list(_METADATA_SPAN_PATTERN.finditer(metadata_body))
    if span_matches:
        for match in span_matches:
            field = match.group(1).strip().lower()
            value = match.group(2).strip()
            if field == "categories":
                metadata[field] = _parse_categories(value)
            else:
                metadata[field] = _clean_metadata_value(value)
        return metadata

    for line in metadata_body.splitlines():
        field_match = _FIELD_PATTERN.match(line)
        if field_match:
            current_field = field_match.group(1).strip().lower()
            value = field_match.group(2).strip()
            if current_field == "categories":
                metadata[current_field] = _parse_categories(value)
            else:
                metadata[current_field] = _clean_metadata_value(value)
            continue

        if current_field == "categories":
            category_match = _CATEGORY_LIST_PATTERN.match(line)
            if category_match:
                categories = metadata.setdefault("categories", [])
                if isinstance(categories, list):
                    categories.append(_clean_metadata_value(category_match.group(1)))

    return metadata


def _extract_metadata(markdown: str) -> tuple[dict[str, object], str]:
    match = _METADATA_PATTERN.search(markdown)
    if not match:
        return {}, markdown

    metadata = _metadata_to_dict(match.group("body"))
    body = markdown[: match.start()] + markdown[match.end() :]
    return metadata, body


def _section_lookup(sections: list[PrivacyPatternSection]) -> dict[str, str]:
    lookup = {}
    for section in sections:
        key = section.heading.strip().lower()
        if key in _COMMON_SECTION_NAMES:
            lookup[key] = section.body.strip()
    return lookup


def _dedupe_keep_order(items: list[str]) -> list[str]:
    cleaned = [_clean_markdown(item) for item in items]
    return dedupe_keep_order([item for item in cleaned if item], key=str.lower)


def _build_triggers(title: str, categories: list[str], summary: str) -> list[str]:
    words = re.findall(r"[a-z][a-z0-9-]{2,}", f"{title} {' '.join(categories)} {summary}".lower())
    ignored = {"and", "the", "with", "from", "that", "this", "into", "user", "users", "pattern"}
    return _dedupe_keep_order([word for word in words if word not in ignored])[:16]


def parse_privacy_pattern(
    markdown: str,
    filename: str = "",
    source_path: str = "",
    source_url: str = "",
) -> ParsedPrivacyPattern:
    """Parse raw PrivacyPatterns Markdown into the smaller model needed for output."""
    metadata, body = _extract_metadata(markdown)
    lines = body.splitlines()

    title = str(metadata.get("title") or "").strip()
    sections: list[PrivacyPatternSection] = []
    preamble: list[str] = []
    current_heading = ""
    current_body: list[str] = []

    def flush_section() -> None:
        nonlocal current_heading
        if current_heading:
            body = _strip_html_comments("\n".join(current_body)).strip()
            sections.append(PrivacyPatternSection(heading=current_heading, body=body))
        current_heading = ""
        current_body.clear()

    for line in lines:
        if line.strip() == "[TOC]":
            continue

        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            flush_section()
            level = len(heading_match.group(1))
            heading_text = _clean_markdown(heading_match.group(2))
            if level == 1 and not title:
                title = heading_text
            else:
                current_heading = heading_text
            continue

        if current_heading:
            current_body.append(line)
        else:
            preamble.append(line)

    flush_section()

    section_by_name = _section_lookup(sections)
    raw_categories = metadata.get("categories", [])
    categories = (
        [str(category) for category in raw_categories]
        if isinstance(raw_categories, list)
        else []
    )
    summary = (
        _first_paragraph(section_by_name.get("summary", ""))
        or _first_paragraph("\n".join(preamble))
        or str(metadata.get("excerpt") or "").strip()
    )
    title = title or _title_from_filename(filename or source_path)
    clean_categories = _dedupe_keep_order(categories)

    return ParsedPrivacyPattern(
        title=title,
        excerpt=str(metadata.get("excerpt") or "").strip(),
        summary=summary,
        context=section_by_name.get("context", "").strip(),
        problem=section_by_name.get("problem", "").strip(),
        solution=section_by_name.get("solution", "").strip(),
        consequences=section_by_name.get("consequences", "").strip(),
        examples=section_by_name.get("examples", "").strip(),
        categories=clean_categories,
        status=str(metadata.get("status") or "").strip(),
        sections=sections,
        triggers=_build_triggers(title, clean_categories, summary),
        raw_filename=filename or source_path.rsplit("/", maxsplit=1)[-1],
        source_path=source_path,
        source_url=source_url,
    )
