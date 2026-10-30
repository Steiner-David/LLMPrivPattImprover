import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import yaml
from jinja2 import TemplateError
from requests import RequestException

from owasp_skillgen.fetcher import fetch_cheatsheet, list_cheatsheets
from owasp_skillgen.generator import generate_prompt_json, generate_skill
from owasp_skillgen.parser import parse
from privacy_patterngen.fetcher import PrivacyPatternSource, fetch_pattern, list_patterns
from privacy_patterngen.generator import (
    generate_privacy_pattern_json,
    generate_privacy_pattern_skill,
    slugify as slugify_privacy_pattern,
)
from privacy_patterngen.parser import parse_privacy_pattern
from privacy_patterngen.related_owasp import related_owasp_cheatsheets

OutputMode = Literal["both", "skill", "json"]


@dataclass(frozen=True)
class AppConfig:
    """Resolved configuration values used by the CLI."""

    output_dir: Path
    template_dir: Path
    template_name: str
    privacy_template_name: str = "privacy_skill.md.j2"


def _display_cheatsheet_name(filename: str) -> str:
    return filename.removesuffix(".md").replace("_", " ")


def _normalize_search_text(text: str) -> str:
    return re.sub(r"[\s_-]+", " ", text.lower()).strip()


def search_cheatsheets(term: str, filenames: list[str]) -> list[str]:
    """Find cheat sheet filenames whose filename or title contains term."""
    query = _normalize_search_text(term)
    if not query:
        return []

    matches = []
    for filename in filenames:
        searchable = _normalize_search_text(f"{filename} {_display_cheatsheet_name(filename)}")
        if query in searchable:
            matches.append(filename)
    return matches


def _parse_selection(selection: str, max_count: int) -> list[int]:
    text = selection.strip().lower()
    if not text:
        raise ValueError("Enter a number or 'all'.")
    if text == "all":
        return list(range(max_count))

    indices = []
    seen = set()
    for part in re.split(r"[,\s]+", text):
        if not part:
            continue
        if not part.isdecimal():
            raise ValueError("Use numbers like 1, 2 or 'all'.")

        number = int(part)
        if number < 1 or number > max_count:
            raise ValueError(f"Selection {number} is outside 1-{max_count}.")

        index = number - 1
        if index not in seen:
            indices.append(index)
            seen.add(index)

    if not indices:
        raise ValueError("Enter a number or 'all'.")
    return indices


def choose_cheatsheets(
    term: str,
    available_filenames: list[str],
    prompt: Callable[[str], str] | None = None,
) -> tuple[str, ...]:
    """Show matching cheat sheets and return the filenames selected by the user."""
    matches = search_cheatsheets(term, available_filenames)
    if not matches:
        print(f"No OWASP cheat sheets found containing '{term}'.")
        return ()

    print(f"\nFound {len(matches)} OWASP cheat sheet(s) containing '{term}':")
    for index, filename in enumerate(matches, start=1):
        print(f"  {index}. {_display_cheatsheet_name(filename)} ({filename})")

    prompt_func = prompt or input
    while True:
        try:
            selection = prompt_func("Choose cheat sheet number(s) or 'all': ")
        except EOFError:
            print("No selection received; nothing generated.")
            return ()

        if selection.strip().lower() in {"q", "quit", "cancel"}:
            print("Selection cancelled.")
            return ()

        try:
            selected_indices = _parse_selection(selection, len(matches))
        except ValueError as exc:
            print(f"  x {exc}")
            continue

        return tuple(matches[index] for index in selected_indices)


def _display_pattern_name(source: PrivacyPatternSource) -> str:
    return source.name.removesuffix(".md").replace("-", " ").replace("_", " ")


def search_privacy_patterns(
    term: str,
    sources: list[PrivacyPatternSource],
) -> list[PrivacyPatternSource]:
    """Find privacy pattern sources whose filename or display title contains term."""
    query = _normalize_search_text(term)
    if not query:
        return []

    matches = []
    for source in sources:
        searchable = _normalize_search_text(f"{source.name} {_display_pattern_name(source)}")
        if query in searchable:
            matches.append(source)
    return matches


def choose_privacy_patterns(
    term: str,
    available_sources: list[PrivacyPatternSource],
    prompt: Callable[[str], str] | None = None,
) -> tuple[PrivacyPatternSource, ...]:
    """Show matching privacy patterns and return the sources selected by the user."""
    matches = search_privacy_patterns(term, available_sources)
    if not matches:
        print(f"No privacy patterns found containing '{term}'.")
        return ()

    print(f"\nFound {len(matches)} privacy pattern(s) containing '{term}':")
    for index, source in enumerate(matches, start=1):
        print(f"  {index}. {_display_pattern_name(source)} ({source.name})")

    prompt_func = prompt or input
    while True:
        try:
            selection = prompt_func("Choose privacy pattern number(s) or 'all': ")
        except EOFError:
            print("No selection received; nothing generated.")
            return ()

        if selection.strip().lower() in {"q", "quit", "cancel"}:
            print("Selection cancelled.")
            return ()

        try:
            selected_indices = _parse_selection(selection, len(matches))
        except ValueError as exc:
            print(f"  x {exc}")
            continue

        return tuple(matches[index] for index in selected_indices)


def resolve_privacy_pattern_selection(
    term: str,
    available_sources: list[PrivacyPatternSource],
    prompt: Callable[[str], str] | None = None,
) -> tuple[PrivacyPatternSource, ...]:
    """Return exact privacy pattern filename matches without prompting, otherwise search."""
    if term.endswith(".md"):
        exact_matches = [
            source for source in available_sources if source.name.lower() == term.lower()
        ]
        if exact_matches:
            return tuple(exact_matches)
        print(f"No privacy pattern found named '{term}'.")
        return ()

    return choose_privacy_patterns(term, available_sources, prompt=prompt)


def _require_string(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Config value '{key}' must be a non-empty string.")
    return value.strip()


def _optional_string(value: Any, key: str, default: str) -> str:
    if value is None:
        return default
    return _require_string(value, key)


def _require_template_filename(value: Any, key: str, default: str | None = None) -> str:
    raw_name = (
        _optional_string(value, key, default)
        if default is not None
        else _require_string(value, key)
    )
    if "/" in raw_name or "\\" in raw_name:
        raise ValueError(f"Config value '{key}' must be a template filename, not a path.")
    return raw_name


def load_config(path: str = "config.yaml") -> tuple[AppConfig, Path]:
    """Load config.yaml and resolve paths relative to the config file location."""
    config_path = Path(path).resolve()
    with config_path.open(encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}

    if not isinstance(raw_config, dict):
        raise ValueError("Config file must contain a YAML mapping.")

    # Keep config portable: relative paths are interpreted next to config.yaml,
    # not wherever the command happens to be executed from.
    config_dir = config_path.parent
    template_dir = _require_string(raw_config.get("template_dir"), "template_dir")
    output_dir = _require_string(raw_config.get("output_dir"), "output_dir")
    config = AppConfig(
        template_dir=(config_dir / template_dir).resolve(),
        output_dir=(config_dir / output_dir).resolve(),
        template_name=_require_template_filename(raw_config.get("template_name"), "template_name"),
        privacy_template_name=_require_template_filename(
            raw_config.get("privacy_template_name"),
            "privacy_template_name",
            "privacy_skill.md.j2",
        ),
    )
    return config, config_path


def process_one(
    filename: str,
    config: AppConfig,
    local_path: str | None = None,
    output_mode: OutputMode = "both",
    skill_output_dir: Path | None = None,
    json_output_dir: Path | None = None,
) -> tuple[Path, ...] | None:
    """Read or fetch one Markdown file, parse it, and render the requested outputs."""
    print(f"\n-> Processing: {filename}")

    if local_path:
        print(f"  Reading local file: {local_path}")
        local_file = Path(local_path)
        if local_file.suffix.lower() != ".md":
            print(f"  x Local input must be a Markdown file: {local_path}")
            return None
        try:
            markdown = local_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"  x Failed to read {local_path}: {exc}")
            return None
    else:
        # Network work is isolated here so failures skip only the current file.
        print("  Fetching from OWASP GitHub...")
        try:
            markdown = fetch_cheatsheet(filename)
        except (RequestException, ValueError) as exc:
            print(f"  x Failed to fetch {filename}: {exc}")
            return None

    sheet = parse(markdown, filename)
    if local_path:
        sheet.local_source = str(Path(local_path).resolve())
    print(
        f"  Parsed: '{sheet.title}' | {len(sheet.sections)} sections "
        f"| {len(sheet.all_code_blocks)} code blocks "
        f"| {len(sheet.recommendations)} recommendations"
    )

    generated_paths: list[Path] = []

    if output_mode in ("both", "skill"):
        try:
            markdown_path = generate_skill(
                sheet,
                template_dir=config.template_dir,
                output_dir=skill_output_dir or config.output_dir,
                template_name=config.template_name,
            )
        except (OSError, TemplateError) as exc:
            print(f"  x Failed to generate Markdown for {filename}: {exc}")
            return None
        generated_paths.append(markdown_path)
        print(f"  OK Markdown written -> {markdown_path}")

    if output_mode in ("both", "json"):
        try:
            json_path = generate_prompt_json(
                sheet,
                output_dir=json_output_dir or config.output_dir,
            )
        except OSError as exc:
            print(f"  x Failed to generate JSON for {filename}: {exc}")
            return None
        generated_paths.append(json_path)
        print(f"  OK JSON written -> {json_path}")

    return tuple(generated_paths)


def process_privacy_pattern(
    source: PrivacyPatternSource,
    config: AppConfig,
    output_mode: OutputMode = "both",
) -> tuple[Path, ...] | None:
    """Fetch one privacy pattern, render it, and render useful related OWASP outputs."""
    print(f"\n-> Processing privacy pattern: {source.name}")
    print("  Fetching from PrivacyPatterns GitHub...")

    try:
        markdown = fetch_pattern(source)
    except (RequestException, ValueError) as exc:
        print(f"  x Failed to fetch {source.name}: {exc}")
        return None

    pattern = parse_privacy_pattern(
        markdown,
        filename=source.name,
        source_path=source.path,
        source_url=source.html_url,
    )
    print(
        f"  Parsed: '{pattern.title}' | {len(pattern.sections)} sections "
        f"| {len(pattern.categories)} categories"
    )

    generated_paths: list[Path] = []
    pattern_output_dir = config.output_dir / slugify_privacy_pattern(pattern.title)
    pattern_skill_dir = pattern_output_dir / "skill"
    pattern_json_dir = pattern_output_dir / "json"

    if output_mode in ("both", "skill"):
        try:
            markdown_path = generate_privacy_pattern_skill(
                pattern,
                template_dir=config.template_dir,
                output_dir=pattern_skill_dir,
                template_name=config.privacy_template_name,
            )
        except (OSError, TemplateError) as exc:
            print(f"  x Failed to generate Markdown for {source.name}: {exc}")
            return None
        generated_paths.append(markdown_path)
        print(f"  OK Markdown written -> {markdown_path}")

    if output_mode in ("both", "json"):
        try:
            json_path = generate_privacy_pattern_json(pattern, output_dir=pattern_json_dir)
        except OSError as exc:
            print(f"  x Failed to generate JSON for {source.name}: {exc}")
            return None
        generated_paths.append(json_path)
        print(f"  OK JSON written -> {json_path}")

    related_owasp = related_owasp_cheatsheets(pattern)
    if related_owasp:
        print(
            "  Related OWASP cheat sheet(s): "
            f"{', '.join(_display_cheatsheet_name(filename) for filename in related_owasp)}"
        )
    else:
        print("  No related OWASP cheat sheets found.")

    related_config = AppConfig(
        output_dir=pattern_output_dir / "owasp",
        template_dir=config.template_dir,
        template_name=config.template_name,
        privacy_template_name=config.privacy_template_name,
    )
    for filename in related_owasp:
        owasp_paths = process_one(
            filename,
            related_config,
            output_mode=output_mode,
            skill_output_dir=related_config.output_dir / "skill",
            json_output_dir=related_config.output_dir / "json",
        )
        if owasp_paths is None:
            return None
        generated_paths.extend(owasp_paths)

    return tuple(generated_paths)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate LLM Skill files and JSON knowledge from OWASP cheat sheets "
            "or privacy patterns"
        )
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--sheet",
        help=(
            "Cheat sheet filename or search term "
            "(e.g. Password_Storage_Cheat_Sheet.md or password)"
        ),
    )
    source.add_argument(
        "--pattern",
        help=(
            "Privacy pattern filename or search term "
            "(e.g. Strip-invisible-metadata.md or metadata)"
        ),
    )
    source.add_argument("--local", help="Path to a local .md file to process instead of fetching")
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--skill",
        action="store_const",
        const="skill",
        dest="output_mode",
        help="Generate only Skill Markdown",
    )
    output.add_argument(
        "--json",
        action="store_const",
        const="json",
        dest="output_mode",
        help="Generate only JSON knowledge",
    )
    parser.set_defaults(output_mode="both")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        config, config_path = load_config(args.config)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.exit(2, f"Failed to load config: {exc}\n")

    print(f"Using config: {config_path}")
    output_mode: OutputMode = args.output_mode
    failed = False

    if args.local:
        filename = Path(args.local).name
        failed = (
            process_one(filename, config, local_path=args.local, output_mode=output_mode) is None
        )
    elif args.pattern:
        try:
            available_sources = list_patterns()
        except (RequestException, ValueError) as exc:
            parser.exit(1, f"Failed to list privacy patterns: {exc}\n")

        selected_sources = resolve_privacy_pattern_selection(args.pattern, available_sources)
        if not selected_sources and args.pattern.endswith(".md"):
            failed = True

        for source in selected_sources:
            if process_privacy_pattern(source, config, output_mode=output_mode) is None:
                failed = True
    elif args.sheet.endswith(".md"):
        failed = process_one(args.sheet, config, output_mode=output_mode) is None
    else:
        try:
            available_filenames = list_cheatsheets()
        except (RequestException, ValueError) as exc:
            parser.exit(1, f"Failed to list OWASP cheat sheets: {exc}\n")

        for filename in choose_cheatsheets(args.sheet, available_filenames):
            if process_one(filename, config, output_mode=output_mode) is None:
                failed = True

    print("\nDone.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
