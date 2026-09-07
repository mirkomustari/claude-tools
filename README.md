# claude-tools

Standard-library helpers for Claude Code sessions. No dependencies, on
purpose: a checker that needs a package is a checker that stops starting one
day, in the one project whose interpreter lacks it, and is never reinstalled.

| Tool | What it does | How it runs |
|---|---|---|
| `mdcheck.py` | Checks one Markdown file for the defects that silently break it: anchors that resolve nowhere, links to missing files, unclosed code fences, duplicate headings a link points at, a long file with no table of contents, phrases that expire | PostToolUse hook (`--hook`), pre-commit (`id: mdcheck`), CLI (`FILE...`, `--all DIR`, `--selftest`) |
| `ctxbudget.py` | Lists what Claude Code loads at every session start for one project — CLAUDE.md files, unscoped rules, the memory index, skill descriptions — with lines, characters and a token estimate | CLI (`PROJECT_DIR`, `--project-only`, `--max-tokens N`, `--json`) |

Per-project knobs for `mdcheck` live in a `.mdcheck.json` at the repository root:

```json
{"check_links": true, "toc_min_lines": 200, "expiring_phrases": true}
```

As a pre-commit hook:

```yaml
- repo: https://github.com/mirkomustari/claude-tools
  rev: v0.1.0
  hooks:
    - id: mdcheck
```

`RICERCA_MD.md` (Italian) is the research record behind these tools: what was
evaluated, what was adopted, what was rejected and why.

MIT licence.
