"""Render parsed documents into self-contained Skill Markdown files."""

from os import PathLike
from pathlib import Path

from skillgen_common.rendering import write_skill

from .parser import ParsedCheatSheet

PathInput = str | PathLike[str]


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
