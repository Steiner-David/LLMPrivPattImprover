"""Render parsed documents into self-contained Skill Markdown files."""

from os import PathLike
from pathlib import Path

from skillgen_common.markdown import slugify as common_slugify
from skillgen_common.rendering import write_skill

from .parser import ParsedPrivacyPattern

PathInput = str | PathLike[str]


def slugify(name: str) -> str:
    """Turn a title into a safe filename slug."""
    return common_slugify(name, fallback="privacy_pattern")


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
