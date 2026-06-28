"""Small Markdown-normalization helpers used by parsers and JSON renderers."""

from __future__ import annotations

import re
from collections.abc import Callable, Hashable, Iterable
from typing import TypeVar

_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
_LIST_ITEM_PATTERN = re.compile(r"(?m)^\s*(?:[-*+]|\d+\.)\s+")
_HEADING_PATTERN = re.compile(r"(?m)^#+\s*")

T = TypeVar("T")


def strip_html_comments(text: str) -> str:
    """Remove Markdown/HTML comments from source text."""
    return _HTML_COMMENT_PATTERN.sub("", text)


def collapse_whitespace(text: str) -> str:
    """Normalize all whitespace runs to a single space."""
    return re.sub(r"\s+", " ", text).strip()


def strip_inline_markdown(
    text: str,
    *,
    remove_list_markers: bool = False,
    remove_html_tags: bool = False,
    remove_toc: bool = True,
) -> str:
    """Remove lightweight Markdown syntax while preserving the source wording."""
    text = strip_html_comments(text)
    if remove_list_markers:
        text = _LIST_ITEM_PATTERN.sub("", text)
    if remove_toc:
        text = text.replace("[TOC]", "")

    text = _LINK_PATTERN.sub(r"\1", text)
    text = _WIKI_LINK_PATTERN.sub(r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = _HEADING_PATTERN.sub("", text)
    if remove_html_tags:
        text = _HTML_TAG_PATTERN.sub("", text)
    return collapse_whitespace(text)


def first_paragraph(
    text: str,
    *,
    remove_list_markers: bool = False,
    remove_html_tags: bool = False,
) -> str:
    """Return the first non-empty paragraph after lightweight Markdown cleanup."""
    for paragraph in re.split(r"\n\s*\n", text):
        clean = strip_inline_markdown(
            paragraph,
            remove_list_markers=remove_list_markers,
            remove_html_tags=remove_html_tags,
        )
        if clean:
            return clean
    return ""


def paragraphs(
    text: str,
    *,
    remove_list_markers: bool = False,
    remove_html_tags: bool = False,
) -> list[str]:
    """Split Markdown into clean, non-empty paragraphs."""
    cleaned_paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        clean = strip_inline_markdown(
            paragraph,
            remove_list_markers=remove_list_markers,
            remove_html_tags=remove_html_tags,
        )
        if clean:
            cleaned_paragraphs.append(clean)
    return cleaned_paragraphs


def dedupe_keep_order(items: Iterable[T], *, key: Callable[[T], Hashable] | None = None) -> list[T]:
    """Return unique items while preserving their first-seen order."""
    deduped = []
    seen = set()
    key_func = key or (lambda item: item)
    for item in items:
        marker = key_func(item)
        if marker in seen:
            continue
        deduped.append(item)
        seen.add(marker)
    return deduped


def slugify(name: str, *, fallback: str) -> str:
    """Turn a display name into a stable, lowercase filename stem."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return slug.strip("_") or fallback
