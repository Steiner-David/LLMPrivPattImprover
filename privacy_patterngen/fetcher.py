"""Fetch privacy pattern Markdown files from the PrivacyPatterns GitHub repository."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from skillgen_common.http import HttpClient, get_json, get_text

GITHUB_API_PATTERNS_URL = "https://api.github.com/repos/privacypatterns/patterns/contents/patterns"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/privacypatterns/patterns/master"
GITHUB_HTML_BASE = "https://github.com/privacypatterns/patterns/blob/master"
_PATTERN_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.md$")


@dataclass(frozen=True)
class PrivacyPatternSource:
    """A Markdown pattern file available from the source repository."""

    name: str
    path: str
    download_url: str
    html_url: str


def _validate_pattern_path(path: str) -> str:
    """Accept only Markdown files from the repository's patterns directory."""
    posix_path = PurePosixPath(path)
    parts = posix_path.parts
    if (
        len(parts) != 2
        or parts[0] != "patterns"
        or not _PATTERN_FILENAME_PATTERN.fullmatch(parts[1])
    ):
        raise ValueError(
            "Privacy pattern path must be a Markdown file inside the patterns directory."
        )
    return path


def _raw_url(path: str) -> str:
    return f"{GITHUB_RAW_BASE}/{path}"


def _html_url(path: str) -> str:
    return f"{GITHUB_HTML_BASE}/{path}"


def list_patterns(*, client: HttpClient | None = None) -> list[PrivacyPatternSource]:
    """Return Markdown privacy pattern sources from privacypatterns/patterns."""
    payload = get_json(GITHUB_API_PATTERNS_URL, client=client)

    if not isinstance(payload, list):
        raise ValueError("Unexpected GitHub response while listing privacy patterns.")

    sources = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        name = item.get("name")
        path = item.get("path")
        item_type = item.get("type")
        if item_type != "file" or not isinstance(name, str) or not isinstance(path, str):
            continue

        try:
            validated_path = _validate_pattern_path(path)
        except ValueError:
            continue
        if PurePosixPath(validated_path).name != name:
            continue

        sources.append(
            PrivacyPatternSource(
                name=name,
                path=validated_path,
                download_url=_raw_url(validated_path),
                html_url=_html_url(validated_path),
            )
        )

    return sorted(sources, key=lambda source: source.name.lower())


def fetch_pattern(source: PrivacyPatternSource, *, client: HttpClient | None = None) -> str:
    """Fetch one privacy pattern Markdown file."""
    path = _validate_pattern_path(source.path)
    if PurePosixPath(path).name != source.name:
        raise ValueError("Privacy pattern source name must match its repository path.")
    # Build the raw URL from the validated repository path instead of trusting
    # caller-provided or API-provided download_url values.
    return get_text(_raw_url(path), client=client)
