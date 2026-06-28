"""Template rendering helpers for generated Markdown artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PathInput = str | PathLike[str]


def render_template(template_dir: PathInput, template_name: str, context: Mapping[str, Any]) -> str:
    """Render a Jinja template and normalize the final newline for stable output."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(template_name)
    return template.render(**context).rstrip() + "\n"


def ensure_output_dir(output_dir: PathInput) -> Path:
    """Create and return an output directory."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
