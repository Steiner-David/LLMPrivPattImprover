# Security and Privacy Skill Generator

Generate self-contained Codex skills and compact JSON knowledge payloads from security and privacy source documents.

The tool currently supports three input modes:

- OWASP Cheat Sheet Series Markdown files fetched from GitHub
- PrivacyPatterns Markdown files fetched from GitHub
- Local Markdown files processed with the OWASP-style parser

Generated skills contain YAML discovery metadata, task instructions, and the complete original Markdown in a single `SKILL.md`. Generated JSON remains a distilled, source-linked knowledge payload suitable for prompt context, indexing, or other downstream tooling.

## Academic Context

This tool was created for the course **Privacy Engineering in Practice (PEng in Practice)** at the **University of Salzburg**.

## Requirements

- Python 3.10 or newer
- Network access for `--sheet` and `--pattern` modes
- Python packages from `requirements.txt`

The project is run as a script from this repository. The project has no package manifest. Offline regression tests use Python's standard-library `unittest`.

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

Each skill is a directory containing a single uppercase `SKILL.md`. Skill names use
lowercase letters, digits, and hyphens, with an `owasp-`, `privacy-`, or `local-`
prefix and a stable ten-character source-identity hash. The hash distinguishes
sources with identical titles or normalized names. Names are at most 63 characters.
For local documents, identity includes the resolved local path.

OWASP and local skills are written directly under `output_dir`; their JSON files
keep the existing title-based filenames. For example (`<hash>` is illustrative):

```text
output/
  owasp-password-storage-cheat-sheet-<hash>/
    SKILL.md
  password_storage_cheat_sheet.json
```

PrivacyPatterns output remains grouped by pattern slug. Each related OWASP
skill is a separate, self-contained skill folder:

```text
output/
  aggregation_gateway/
    skill/
      privacy-aggregation-gateway-<hash>/
        SKILL.md
    json/
      aggregation_gateway.json
    owasp/
      skill/
        owasp-cryptographic-storage-cheat-sheet-<hash>/
          SKILL.md
        owasp-key-management-cheat-sheet-<hash>/
          SKILL.md
      json/
        cryptographic_storage_cheat_sheet.json
        key_management_cheat_sheet.json
```

Related OWASP generation uses keyword rules in `privacy_patterngen/related_owasp.py`. A privacy pattern can map to cheat sheets such as User Privacy Protection, Cryptographic Storage, Key Management, TLS, Access Control, Authentication, Session Management, Logging, or File Upload.

## Generated Content

Every generated skill includes:

- YAML frontmatter containing `name` and a task-focused `description`
- a workflow for applying the source to design, implementation, or review tasks
- source attribution (local documents are identified as local in the skill)
- the **complete original Markdown**, including all sections, metadata, comments,
  links, and code examples, with no excerpt limits or truncation

Source text is appended after template rendering so embedded Jinja or Hyde syntax
is preserved literally. No separate reference files are generated. The skill can
therefore be large: preserving the complete source takes priority over brevity.
The compact JSON extraction is independent and retains its existing schemas and
limits, including its existing OWASP-style treatment of local input.

OWASP JSON includes:

- `document_type: "owasp_cheat_sheet_knowledge"`
- source links
- prompt usage instructions
- distilled `knowledge_items` classified as `concept`, `requirement`, `implementation`, `testing`, or `warning`
- compact excerpts and limited code examples where available

PrivacyPatterns skills additionally expose parsed categories and status above the
complete original source, which also preserves the original classification metadata.

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

Templates define the Markdown workflow body. The generator adds YAML frontmatter
and the complete source document, even when a custom body template is used. Do not
add another discovery frontmatter block to a custom body template.

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

- Regenerating the same skill overwrites its `SKILL.md`; JSON files retain title-slug overwrite behavior.
- Local input must have a `.md` suffix.
- Search mode requires an interactive terminal for selection.
- GitHub network failures skip the current item or fail listing before generation starts.

## Using generated skills in Codex

Copy an individual generated skill directory (the directory containing `SKILL.md`)
into your target repository's `.agents/skills/` directory, or into
`~/.agents/skills/` for personal use. Copy any desired related OWASP skill folders
as well. The generator only writes artifacts; it does not install skills.

For example, the installed layout is:

```text
.agents/skills/
  privacy-aggregation-gateway-<hash>/
    SKILL.md
```

Codex uses the frontmatter description to select skills and reads the body when a
skill is invoked. Explicit invocation is also available through `$<skill-name>`.
See the [official Codex skill documentation](https://learn.chatgpt.com/docs/build-skills).
Optional UI metadata (`agents/openai.yaml`) is not needed for these instruction-only skills.

Existing generated `<slug>.md` files are not migrated or deleted automatically.
Regenerate from the original input to produce the new folders. Previously truncated
artifacts cannot restore information that was omitted from them.

## Validation

Run the offline regression suite:

```bash
python -m unittest discover -s tests -v
```

Tests cover metadata, source preservation, stable names and collision separation,
local provenance, and local/privacy workflows across all output modes. Network
fetches are mocked. These checks validate artifact structure and preservation;
they do not guarantee that Codex will select the skill for every intended prompt.
