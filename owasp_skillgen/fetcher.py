"""Fetch OWASP Cheat Sheet Markdown files from GitHub."""

import re

from skillgen_common.http import HttpClient, get_json, get_text

GITHUB_API_CONTENTS_URL = "https://api.github.com/repos/OWASP/CheatSheetSeries/contents/cheatsheets"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets"
_CHEATSHEET_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.md$")


def _validate_cheatsheet_name(name: str) -> str:
    """Accept only plain Markdown filenames from the OWASP cheatsheets folder."""
    if not _CHEATSHEET_FILENAME_PATTERN.fullmatch(name):
        raise ValueError(
            "Cheat sheet name must be a Markdown filename, "
            "for example Password_Storage_Cheat_Sheet.md."
        )
    return name


def fetch_cheatsheet(name: str, *, client: HttpClient | None = None) -> str:
    """Fetch a single OWASP cheat sheet by validated filename."""
    # Validate before building the URL so callers cannot pass arbitrary paths.
    name = _validate_cheatsheet_name(name)
    return get_text(f"{GITHUB_RAW_BASE}/{name}", client=client)


def list_cheatsheets(*, client: HttpClient | None = None) -> list[str]:
    """Return Markdown cheat sheet filenames from the OWASP CheatSheetSeries repo."""
    payload = get_json(GITHUB_API_CONTENTS_URL, client=client)

    if not isinstance(payload, list):
        raise ValueError("Unexpected GitHub response while listing cheat sheets.")

    filenames = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        item_type = item.get("type")
        if item_type != "file" or not isinstance(name, str):
            continue
        try:
            filenames.append(_validate_cheatsheet_name(name))
        except ValueError:
            continue

    return sorted(filenames, key=str.lower)
