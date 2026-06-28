"""
Parse OWASP Cheat Sheet Markdown into structured data for skill generation.
"""

import re
from dataclasses import dataclass, field

from skillgen_common.markdown import first_paragraph, strip_inline_markdown


@dataclass
class CodeBlock:
    """A fenced Markdown code block found in the source cheat sheet."""

    language: str
    code: str


@dataclass
class Section:
    """A Markdown heading and the content that belongs to it."""

    heading: str
    level: int
    body: str
    code_blocks: list[CodeBlock] = field(default_factory=list)


@dataclass
class ParsedCheatSheet:
    """Structured representation used by the Jinja template."""

    title: str
    introduction: str
    sections: list[Section]
    all_code_blocks: list[CodeBlock]
    recommendations: list[str]
    triggers: list[str]
    raw_filename: str


_LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*)")
_RECOMMENDATION_PATTERN = re.compile(
    r"\b(must|should|avoid|do not|never|always|recommend|recommended|prefer|use|don't)\b",
    re.IGNORECASE,
)
_FENCED_CODE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})\s*([A-Za-z0-9_+.#-]*)?.*$")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)")

_TRIGGER_WORDS = [
    "password",
    "hash",
    "salt",
    "bcrypt",
    "argon2",
    "pbkdf2",
    "scrypt",
    "encryption",
    "authentication",
    "token",
    "session",
    "injection",
    "sanitize",
    "validate",
    "csrf",
    "xss",
    "tls",
    "ssl",
    "secret",
    "credential",
    "key",
    "certificate",
    "oauth",
    "jwt",
    "privacy",
    "gdpr",
    "pii",
    "minimization",
    "anonymize",
    "pseudonym",
]


def _strip_inline_markdown(text: str) -> str:
    """Remove simple inline Markdown so extracted snippets read naturally."""
    return strip_inline_markdown(text)


def _first_paragraph(text: str) -> str:
    """Return the first non-empty paragraph after light Markdown cleanup."""
    return first_paragraph(text)


def _title_from_filename(filename: str) -> str:
    """Build a readable fallback title when the Markdown has no H1 heading."""
    stem = filename.rsplit("/", maxsplit=1)[-1].removesuffix(".md")
    return _strip_inline_markdown(stem.replace("_", " ")) or "OWASP Cheat Sheet"


def _extract_recommendation(line: str) -> str | None:
    """Return actionable list items, ignoring descriptive bullets."""
    match = _LIST_ITEM_PATTERN.match(line)
    if not match:
        return None

    clean = _strip_inline_markdown(match.group(1))
    if not clean:
        return None

    if _RECOMMENDATION_PATTERN.search(clean[:120]):
        return clean
    return None


def _closes_code_block(candidate_fence: str, opening_fence: str) -> bool:
    """Return whether a fence marker closes the current fenced code block."""
    return candidate_fence[0] == opening_fence[0] and len(candidate_fence) >= len(opening_fence)


def parse(markdown: str, filename: str = "") -> ParsedCheatSheet:
    """Parse raw OWASP Markdown into the smaller model needed for skill output."""
    lines = markdown.splitlines()

    # Output collections built while walking the Markdown once from top to bottom.
    title = ""
    sections: list[Section] = []
    all_code_blocks: list[CodeBlock] = []
    recommendations: list[str] = []
    seen_recommendations: set[str] = set()
    intro_buffer: list[str] = []

    current_section_heading = ""
    current_section_level = 0
    current_section_body: list[str] = []
    current_section_code_blocks: list[CodeBlock] = []

    # Fenced code blocks temporarily suspend normal heading/list parsing.
    in_code_block = False
    code_block_fence = ""
    code_block_lang = ""
    code_block_lines: list[str] = []
    seen_title = False

    def flush_section() -> None:
        """Store the current section before starting a new one."""
        nonlocal current_section_heading, current_section_level
        if current_section_heading:
            sections.append(
                Section(
                    heading=current_section_heading,
                    level=current_section_level,
                    body="\n".join(current_section_body).strip(),
                    code_blocks=list(current_section_code_blocks),
                )
            )
        current_section_heading = ""
        current_section_level = 0
        current_section_body.clear()
        current_section_code_blocks.clear()

    for line in lines:
        if line.strip() == "[TOC]":
            continue

        code_fence_match = _FENCED_CODE_PATTERN.match(line)
        if code_fence_match:
            fence = code_fence_match.group(1)
            # Markdown allows both ``` and ~~~ fences; close only on a compatible marker.
            if not in_code_block:
                in_code_block = True
                code_block_fence = fence
                code_block_lang = code_fence_match.group(2) or "text"
                code_block_lines = []
                continue
            if _closes_code_block(fence, code_block_fence):
                in_code_block = False
                code_block = CodeBlock(language=code_block_lang, code="\n".join(code_block_lines))
                all_code_blocks.append(code_block)
                if current_section_heading:
                    current_section_code_blocks.append(code_block)
                continue

        if in_code_block:
            # Code lines are kept verbatim and excluded from recommendations.
            code_block_lines.append(line)
            continue

        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            flush_section()
            level = len(heading_match.group(1))
            heading_text = _strip_inline_markdown(heading_match.group(2))

            # The first H1 becomes the document title; all other headings are sections.
            if level == 1 and not title:
                title = heading_text
                seen_title = True
            else:
                current_section_heading = heading_text
                current_section_level = level
            continue

        if seen_title and not current_section_heading:
            # Text between the title and first section is the best introduction candidate.
            intro_buffer.append(line)
        elif not title and not current_section_heading:
            # Documents without a title can still contain useful preamble text.
            intro_buffer.append(line)

        recommendation = _extract_recommendation(line)
        if recommendation and recommendation not in seen_recommendations:
            recommendations.append(recommendation)
            seen_recommendations.add(recommendation)

        if current_section_heading:
            current_section_body.append(line)

    if in_code_block:
        # Keep an unterminated final code fence instead of silently losing it.
        code_block = CodeBlock(language=code_block_lang or "text", code="\n".join(code_block_lines))
        all_code_blocks.append(code_block)
        if current_section_heading:
            current_section_code_blocks.append(code_block)

    flush_section()

    # Prefer intro text after the H1, then an explicit Introduction section,
    # then the first useful paragraph from any section.
    introduction = _first_paragraph("\n".join(intro_buffer))
    if not introduction:
        for section in sections:
            if section.heading.lower() == "introduction":
                introduction = _first_paragraph(section.body)
                if introduction:
                    break

    if not introduction:
        for section in sections:
            introduction = _first_paragraph(section.body)
            if introduction:
                break

    lower_md = markdown.lower()
    # Trigger words become the generated skill description's matching hints.
    triggers = [word for word in _TRIGGER_WORDS if re.search(rf"\b{re.escape(word)}\b", lower_md)]

    return ParsedCheatSheet(
        title=title or _title_from_filename(filename),
        introduction=introduction,
        sections=sections,
        all_code_blocks=all_code_blocks,
        recommendations=recommendations[:12],
        triggers=triggers,
        raw_filename=filename,
    )
