# Security and Privacy Skill Generator

Generate Codex-style Skill Markdown files and compact JSON knowledge payloads from security and privacy source documents.

The tool currently supports three input modes:

- OWASP Cheat Sheet Series Markdown files fetched from GitHub
- PrivacyPatterns Markdown files fetched from GitHub
- Local Markdown files processed with the OWASP-style parser

Generated Markdown is meant for human-readable skill instructions. Generated JSON is a distilled, source-linked knowledge payload suitable for prompt context, indexing, or other downstream tooling.

## Academic Context

This tool was created for the course **Privacy Engineering in Practice (PEng in Practice)** at the **University of Salzburg**.

## Requirements

- Python 3.10 or newer
- Network access for `--sheet` and `--pattern` modes
- Python packages from `requirements.txt`

The project is run as a script from this repository. The current tree does not include a package manifest or a test suite.

## Quick Start

Generate both Skill Markdown and JSON for an exact OWASP cheat sheet filename:

```bash
python main.py --sheet Password_Storage_Cheat_Sheet.md
```

Search OWASP cheat sheets interactively and generate only JSON:

```bash
python main.py --sheet password --json
```

Search PrivacyPatterns interactively and generate only Skill Markdown:

```bash
python main.py --pattern metadata --skill
```

Process a local Markdown file as an OWASP-style document:

```bash
python main.py --local ./my_cheat_sheet.md
```

## CLI

```text
python main.py [--config CONFIG] (--sheet SHEET | --pattern PATTERN | --local LOCAL) [--skill | --json]
```

Inputs:

- `--sheet SHEET`: fetch an OWASP cheat sheet. If `SHEET` ends in `.md`, it is treated as an exact filename from the OWASP `cheatsheets/` directory. Otherwise it is used as a search term and you choose one or more matches interactively.
- `--pattern PATTERN`: fetch a PrivacyPatterns document. If `PATTERN` ends in `.md`, it is matched against exact filenames from the PrivacyPatterns `patterns/` directory. Otherwise it is used as a search term and you choose one or more matches interactively.
- `--local LOCAL`: read a local `.md` file instead of fetching from GitHub. Local files use the OWASP parser, OWASP Skill template, and OWASP JSON schema.

Output modes:

- default: generate both Markdown and JSON
- `--skill`: generate only Skill Markdown
- `--json`: generate only JSON knowledge

Selection prompts accept one number, several numbers separated by commas or spaces, `all`, `q`, `quit`, or `cancel`.

## Output Layout

For OWASP cheat sheets and local Markdown files, output is written directly under `output_dir`:

```text
output/
  password_storage_cheat_sheet.md
  password_storage_cheat_sheet.json
```

For PrivacyPatterns, output is grouped by pattern slug. The tool also scans the parsed pattern for security-relevant keywords and generates related OWASP cheat sheet output under the same pattern folder.

```text
output/
  aggregation_gateway/
    skill/
      aggregation_gateway.md
    json/
      aggregation_gateway.json
    owasp/
      skill/
        cryptographic_storage_cheat_sheet.md
        key_management_cheat_sheet.md
        user_privacy_protection_cheat_sheet.md
      json/
        cryptographic_storage_cheat_sheet.json
        key_management_cheat_sheet.json
        user_privacy_protection_cheat_sheet.json
```

Related OWASP generation uses keyword rules in `privacy_patterngen/related_owasp.py`. A privacy pattern can map to cheat sheets such as User Privacy Protection, Cryptographic Storage, Key Management, TLS, Access Control, Authentication, Session Management, Logging, or File Upload.

## Generated Content

OWASP Skill Markdown includes:

- a skill description built from the cheat sheet title and trigger words
- OWASP-aligned usage instructions
- a short context paragraph
- extracted practical recommendations
- source notes from the first sections
- up to three reference code examples
- links to the OWASP web page and raw GitHub Markdown

OWASP JSON includes:

- `document_type: "owasp_cheat_sheet_knowledge"`
- source links
- prompt usage instructions
- distilled `knowledge_items` classified as `concept`, `requirement`, `implementation`, `testing`, or `warning`
- compact excerpts and limited code examples where available

PrivacyPatterns Skill Markdown includes:

- a skill description built from the pattern title and triggers
- privacy-by-design usage instructions
- context, problem, solution, consequences, and examples when present
- source classification metadata
- links to PrivacyPatterns and GitHub source pages

PrivacyPatterns JSON uses `schema_version: 1` and includes:

- `document_type: "privacy_pattern_knowledge"`
- source links
- category and status metadata
- prompt usage instructions
- structured context, problem, solution, consequences, examples, and source sections

## Configuration

`config.yaml` controls output and template locations:

```yaml
output_dir: output
template_dir: templates
template_name: skill.md.j2
privacy_template_name: privacy_skill.md.j2
```

Relative paths are resolved relative to the config file location, not the shell's current working directory.

Template names must be filenames, not paths. `template_name` is used for OWASP and local documents. `privacy_template_name` is used for PrivacyPatterns documents.

Use a different config file with:

```bash
python main.py --config path/to/config.yaml --sheet password
```

## Project Structure

```text
main.py                    CLI, config loading, selection prompts, workflows
config.yaml                default output and template configuration
requirements.txt           runtime Python dependencies
templates/                 Jinja templates for generated Skill Markdown
owasp_skillgen/            OWASP fetcher, parser, Markdown renderer, JSON renderer
privacy_patterngen/        PrivacyPatterns fetcher, parser, renderer, related OWASP mapper
skillgen_common/           shared HTTP, Markdown cleanup, slugging, and template helpers
output/                    generated artifacts
```

## Source Fetching

The OWASP fetcher reads:

- GitHub API listing: `OWASP/CheatSheetSeries/contents/cheatsheets`
- raw Markdown: `raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/...`

The PrivacyPatterns fetcher reads:

- GitHub API listing: `privacypatterns/patterns/contents/patterns`
- raw Markdown: `raw.githubusercontent.com/privacypatterns/patterns/master/patterns/...`

Both fetchers validate filenames and repository paths before building raw URLs, and HTTP requests use a 10 second timeout.

## Notes

- Generated files are overwritten when the same slug is generated again.
- Local input must have a `.md` suffix.
- Search mode requires an interactive terminal for selection.
- GitHub network failures skip the current item or fail listing before generation starts.
