"""Map privacy patterns to OWASP cheat sheets that can add security context."""

from __future__ import annotations

import re
from dataclasses import dataclass

from skillgen_common.markdown import dedupe_keep_order

from .parser import ParsedPrivacyPattern


@dataclass(frozen=True)
class RelatedOwaspRule:
    """A keyword rule that points a privacy pattern to one or more cheat sheets."""

    filenames: tuple[str, ...]
    keywords: tuple[str, ...]


RELATED_OWASP_RULES: tuple[RelatedOwaspRule, ...] = (
    RelatedOwaspRule(
        filenames=("User_Privacy_Protection_Cheat_Sheet.md",),
        keywords=(
            "personal data",
            "data subject",
            "data subjects",
            "data minimization",
            "minimization",
            "metadata",
            "location",
            "geolocation",
            "tracking",
            "consent",
            "transparency",
            "disclosure",
            "anonym*",
            "pseudonym*",
            "identifi*",
        ),
    ),
    RelatedOwaspRule(
        filenames=("Cryptographic_Storage_Cheat_Sheet.md",),
        keywords=(
            "encrypt*",
            "decrypt*",
            "cryptograph*",
            "cipher*",
            "homomorphic",
            "paillier",
            "hash*",
            "tokenization",
        ),
    ),
    RelatedOwaspRule(
        filenames=("Key_Management_Cheat_Sheet.md",),
        keywords=(
            "key",
            "keys",
            "shared secret",
            "secret sharing",
            "shamir",
            "hsm",
            "certificate",
        ),
    ),
    RelatedOwaspRule(
        filenames=("Transport_Layer_Security_Cheat_Sheet.md",),
        keywords=(
            "tls",
            "ssl",
            "https",
            "transport security",
            "certificate",
        ),
    ),
    RelatedOwaspRule(
        filenames=("Access_Control_Cheat_Sheet.md",),
        keywords=(
            "access control",
            "permission*",
            "authorization",
            "authorize",
            "role",
            "roles",
            "restrict access",
        ),
    ),
    RelatedOwaspRule(
        filenames=("Authentication_Cheat_Sheet.md",),
        keywords=(
            "authentication",
            "login",
            "identity",
            "credential*",
            "verify user",
        ),
    ),
    RelatedOwaspRule(
        filenames=("Session_Management_Cheat_Sheet.md",),
        keywords=(
            "session",
            "cookie",
            "cookies",
        ),
    ),
    RelatedOwaspRule(
        filenames=("Logging_Cheat_Sheet.md",),
        keywords=(
            "log",
            "logs",
            "logging",
            "audit",
            "monitoring",
        ),
    ),
    RelatedOwaspRule(
        filenames=("File_Upload_Cheat_Sheet.md",),
        keywords=(
            "upload",
            "uploads",
            "file upload",
            "image upload",
            "document upload",
        ),
    ),
)


def _pattern_text(pattern: ParsedPrivacyPattern) -> str:
    section_text = " ".join(section.body for section in pattern.sections)
    return " ".join(
        [
            pattern.title,
            pattern.excerpt,
            pattern.summary,
            pattern.context,
            pattern.problem,
            pattern.solution,
            pattern.consequences,
            pattern.examples,
            " ".join(pattern.categories),
            " ".join(pattern.triggers),
            section_text,
        ]
    ).lower()


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    escaped = re.escape(keyword.lower()).replace(r"\*", r"[a-z0-9_-]*")
    return re.compile(rf"\b{escaped}\b")


def _matches_keyword(text: str, keyword: str) -> bool:
    return bool(_keyword_pattern(keyword).search(text))


def related_owasp_cheatsheets(pattern: ParsedPrivacyPattern) -> tuple[str, ...]:
    """Return OWASP cheat sheet filenames that add useful context for a pattern."""
    text = _pattern_text(pattern)
    filenames: list[str] = []

    for rule in RELATED_OWASP_RULES:
        if any(_matches_keyword(text, keyword) for keyword in rule.keywords):
            filenames.extend(rule.filenames)

    return tuple(dedupe_keep_order(filenames))
