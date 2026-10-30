"""
Render parsed privacy patterns into Skill Markdown files and JSON knowledge.
"""

import json
from os import PathLike
from pathlib import Path

from skillgen_common.markdown import paragraphs, slugify as common_slugify
from skillgen_common.rendering import ensure_output_dir, write_skill

from .parser import ParsedPrivacyPattern, PrivacyPatternSection

PathInput = str | PathLike[str]


def slugify(name: str) -> str:
    """Turn a title into a safe filename slug."""
    return common_slugify(name, fallback="privacy_pattern")


def _paragraphs(text: str) -> list[str]:
    return paragraphs(text)


def _section_to_dict(section: PrivacyPatternSection, index: int) -> dict[str, object]:
    content = _paragraphs(section.body)
    return {
        "id": f"P{index:03d}",
        "title": section.heading,
        "source_section": section.heading,
        "content": content,
    }


def generate_privacy_pattern_skill(
    pattern: ParsedPrivacyPattern,
    template_dir: PathInput = "templates",
    output_dir: PathInput = "output",
    template_name: str = "privacy_skill.md.j2",
) -> Path:
    """Render one ParsedPrivacyPattern into a Skill Markdown file."""
    return write_skill(
        template_dir=template_dir,
        template_name=template_name,
        output_dir=output_dir,
        context={"pattern": pattern},
        namespace="privacy",
        identity=pattern.source_path or pattern.raw_filename or pattern.title,
        title=pattern.title,
        description=(
            f"Apply the {pattern.title} privacy pattern when designing, implementing, or "
            "reviewing data handling that involves this pattern's problem and solution."
        ),
        source=pattern.raw_markdown,
    )


def privacy_pattern_to_knowledge_payload(pattern: ParsedPrivacyPattern) -> dict[str, object]:
    """Convert a parsed privacy pattern into distilled JSON prompt context."""
    return {
        "schema_version": 1,
        "document_type": "privacy_pattern_knowledge",
        "topic": pattern.title,
        "summary": pattern.summary or pattern.excerpt,
        "source": {
            "raw_filename": pattern.raw_filename,
            "source_path": pattern.source_path,
            "github": pattern.source_url,
            "privacy_patterns": (
                "https://privacypatterns.org/patterns/"
                f"{pattern.raw_filename.removesuffix('.md')}"
            ),
        },
        "classification": {
            "categories": pattern.categories,
            "status": pattern.status,
        },
        "prompt_usage": {
            "use_when": pattern.triggers,
            "instructions": [
                "Use this privacy-pattern-derived knowledge as privacy-by-design guidance.",
                (
                    "Prefer the pattern's problem, context, solution, and consequences over "
                    "generic privacy advice."
                ),
                "Explain tradeoffs and consequences when applying the pattern to a system.",
                (
                    "Do not invent requirements that are not supported by the extracted "
                    "pattern knowledge."
                ),
            ],
        },
        "privacy_pattern": {
            "context": _paragraphs(pattern.context),
            "problem": _paragraphs(pattern.problem),
            "solution": _paragraphs(pattern.solution),
            "consequences": _paragraphs(pattern.consequences),
            "examples": _paragraphs(pattern.examples),
        },
        "sections": [
            _section_to_dict(section, index)
            for index, section in enumerate(pattern.sections, start=1)
        ],
    }


def generate_privacy_pattern_json(
    pattern: ParsedPrivacyPattern,
    output_dir: PathInput = "output",
) -> Path:
    """Write one ParsedPrivacyPattern as JSON knowledge suitable for prompt context."""
    out_dir = ensure_output_dir(output_dir)

    out_path = out_dir / f"{slugify(pattern.title)}.json"
    rendered = json.dumps(
        privacy_pattern_to_knowledge_payload(pattern),
        ensure_ascii=False,
        indent=2,
    )
    out_path.write_text(rendered + "\n", encoding="utf-8")
    return out_path
