"""Template rendering helpers for generated Markdown artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import Any
import hashlib
import re

import yaml
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


def write_skill(
    *,
    template_dir: PathInput,
    template_name: str,
    output_dir: PathInput,
    context: Mapping[str, Any],
    namespace: str,
    identity: str,
    title: str,
    description: str,
    source: str,
) -> Path:
    """Write a Codex entry point with safely serialized metadata and full source.

    The source is appended after rendering, so Jinja syntax and whitespace in
    the original document are preserved. A source-derived suffix distinguishes
    identical titles and names that normalize to the same slug.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "document"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
    stem = f"{namespace}-{slug}"[:52].rstrip("-")
    name = f"{stem}-{digest}"
    description = " ".join(description.replace("<", "").replace(">", "").split())
    if len(description) > 1024:
        description = description[:1021].rstrip() + "..."
    metadata = yaml.safe_dump(
        {"name": name, "description": description},
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )
    body = render_template(template_dir, template_name, context)
    rendered = f"---\n{metadata}---\n\n{body}\n## Complete source document\n\n{source}"
    if not rendered.endswith("\n"):
        rendered += "\n"
    out_path = ensure_output_dir(Path(output_dir) / name) / "SKILL.md"
    out_path.write_text(rendered, encoding="utf-8")
    return out_path
