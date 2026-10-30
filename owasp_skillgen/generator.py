"""
Render parsed OWASP cheat sheets into Skill Markdown files.
"""

import json
import re
from os import PathLike
from pathlib import Path

from skillgen_common.markdown import (
    dedupe_keep_order,
    paragraphs as markdown_paragraphs,
    slugify as common_slugify,
    strip_inline_markdown,
)
from skillgen_common.rendering import ensure_output_dir, write_skill

from .parser import CodeBlock, ParsedCheatSheet, Section

PathInput = str | PathLike[str]

_ACTIONABLE_PATTERN = re.compile(
    r"\b("
    r"must|should|never|always|avoid|do not|don't|use|validate|ensure|set|close|"
    r"rotate|disable|limit|implement|check|log|monitor|test|reject|sanitize|"
    r"authenticate|authorize|encrypt|hash|store|configure|require|prefer|scan"
    r")\b",
    re.IGNORECASE,
)
_LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*)")
_TESTING_HINT_PATTERN = re.compile(r"\b(test|testing|scan|tool|zap|fuzz)\b")
_WARNING_HINT_PATTERN = re.compile(
    r"\b(avoid|never|dangerous|insecure|risk|vulnerab|attack|leak|bypass)\b"
)
_IMPLEMENTATION_HINT_PATTERN = re.compile(
    r"\b(configure|implement|example|code|schema|header|cookie|token)\b"
)


def slugify(name: str) -> str:
    """Turn a title into a safe filename slug."""
    return common_slugify(name, fallback="owasp_cheat_sheet")


def generate_skill(
    sheet: ParsedCheatSheet,
    template_dir: PathInput = "templates",
    output_dir: PathInput = "output",
    template_name: str = "skill.md.j2",
) -> Path:
    """
    Render one ParsedCheatSheet into a Skill Markdown file.
    """
    return write_skill(
        template_dir=template_dir,
        template_name=template_name,
        output_dir=output_dir,
        context={"sheet": sheet},
        namespace="local" if sheet.local_source else "owasp",
        identity=sheet.local_source or sheet.raw_filename or sheet.title,
        title=sheet.title,
        description=(
            f"Review or implement {sheet.title} guidance when the requested design or code "
            f"concerns this topic, using the bundled {'local document' if sheet.local_source else 'OWASP cheat sheet'}."
        ),
        source=sheet.raw_markdown,
    )


def _code_block_to_dict(code_block: CodeBlock, max_chars: int | None = None) -> dict[str, str]:
    code = code_block.code.strip()
    if max_chars is not None and len(code) > max_chars:
        code = code[:max_chars].rstrip() + " ..."
    return {
        "language": code_block.language,
        "code": code,
    }


def _clean_markdown(text: str) -> str:
    """Remove common Markdown syntax while preserving the OWASP wording."""
    return strip_inline_markdown(
        text,
        remove_list_markers=True,
        remove_html_tags=True,
    )


def _paragraphs(text: str) -> list[str]:
    return markdown_paragraphs(text, remove_list_markers=True, remove_html_tags=True)


def _list_items(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        match = _LIST_ITEM_PATTERN.match(line)
        if match:
            clean = _clean_markdown(match.group(1))
            if clean:
                items.append(clean)
    return items


def _sentences(text: str) -> list[str]:
    sentence_candidates = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`])", _clean_markdown(text))
    return [sentence.strip() for sentence in sentence_candidates if sentence.strip()]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    return dedupe_keep_order(items, key=str.lower)


def _distill_guidance(section: Section, max_items: int = 4) -> list[str]:
    """Extract compact, prompt-friendly guidance from one parsed section."""
    candidates = _list_items(section.body)

    for sentence in _sentences(section.body):
        if _ACTIONABLE_PATTERN.search(sentence):
            candidates.append(sentence)

    if not candidates:
        candidates.extend(_paragraphs(section.body)[:1])

    return _dedupe_keep_order(candidates)[:max_items]


def _source_excerpt(section: Section, max_chars: int = 320) -> str:
    paragraphs = _paragraphs(section.body)
    if not paragraphs:
        return ""

    excerpt = paragraphs[0]
    if len(excerpt) > max_chars:
        return excerpt[:max_chars].rstrip() + " ..."
    return excerpt


def _classify_section(section: Section, guidance: list[str]) -> str:
    text = f"{section.heading} {' '.join(guidance)}".lower()

    if _TESTING_HINT_PATTERN.search(text):
        return "testing"
    if _WARNING_HINT_PATTERN.search(text):
        return "warning"
    if section.code_blocks or _IMPLEMENTATION_HINT_PATTERN.search(text):
        return "implementation"
    if _ACTIONABLE_PATTERN.search(text):
        return "requirement"
    return "concept"


def _knowledge_item(section: Section, index: int) -> dict[str, object] | None:
    guidance = _distill_guidance(section)
    if not guidance and not section.code_blocks:
        return None

    item: dict[str, object] = {
        "id": f"K{index:03d}",
        "category": _classify_section(section, guidance),
        "title": section.heading,
        "source_section": section.heading,
        "guidance": guidance,
    }

    excerpt = _source_excerpt(section)
    if excerpt:
        item["source_excerpt"] = excerpt

    if section.code_blocks:
        item["code_examples"] = [
            _code_block_to_dict(code_block, max_chars=1200)
            for code_block in section.code_blocks[:2]
        ]

    return item


def _build_knowledge_items(sheet: ParsedCheatSheet) -> list[dict[str, object]]:
    items = []
    for section in sheet.sections:
        item = _knowledge_item(section, len(items) + 1)
        if item:
            items.append(item)
    return items


def cheat_sheet_to_knowledge_payload(sheet: ParsedCheatSheet) -> dict[str, object]:
    """Convert a parsed cheat sheet into distilled OWASP knowledge for prompt context."""
    html_filename = (
        f"{sheet.raw_filename.removesuffix('.md')}.html" if sheet.raw_filename else ""
    )
    return {
        "schema_version": 2,
        "document_type": "owasp_cheat_sheet_knowledge",
        "topic": sheet.title,
        "summary": sheet.introduction,
        "source": {
            "raw_filename": sheet.raw_filename,
            "owasp_cheat_sheet": f"https://cheatsheetseries.owasp.org/cheatsheets/{html_filename}",
            "github_raw": (
                "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/"
                f"{sheet.raw_filename}"
            ),
        },
        "prompt_usage": {
            "use_when": sheet.triggers,
            "instructions": [
                "Use this OWASP-derived knowledge as security guidance for the topic.",
                "Prefer concrete implementation advice over generic security background.",
                (
                    "When giving advice, preserve OWASP constraints and cite the source section "
                    "when useful."
                ),
                "Do not invent requirements that are not supported by the extracted knowledge.",
            ],
        },
        "knowledge_items": _build_knowledge_items(sheet),
    }


def cheat_sheet_to_prompt_payload(sheet: ParsedCheatSheet) -> dict[str, object]:
    """Backward-compatible alias for the prompt knowledge payload."""
    return cheat_sheet_to_knowledge_payload(sheet)


def generate_prompt_json(
    sheet: ParsedCheatSheet,
    output_dir: PathInput = "output",
) -> Path:
    """
    Write one ParsedCheatSheet as distilled JSON knowledge suitable for prompt context.
    """
    out_dir = ensure_output_dir(output_dir)

    out_path = out_dir / f"{slugify(sheet.title)}.json"
    rendered = json.dumps(cheat_sheet_to_knowledge_payload(sheet), ensure_ascii=False, indent=2)
    out_path.write_text(rendered + "\n", encoding="utf-8")
    return out_path
