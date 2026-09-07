"""Measure what Claude Code loads at the start of every session, file by file.

Every always-loaded line is paid for at every session start, and the published
guidance is blunt about the cost: adherence drops as the always-loaded set
grows. This prints that set for one project -- the user and project CLAUDE.md,
rules without a `paths:` scope, the auto-memory index, the skill descriptions
-- with lines, characters and a token *estimate*, so a diet has a number to
start from and a number to end on.

    python ctxbudget.py                  # the current directory's project
    python ctxbudget.py PROJECT_DIR
    python ctxbudget.py --project-only   # only files inside the repository (CI-safe)
    python ctxbudget.py --max-tokens N   # exit 2 when the estimate exceeds N

The token figure is characters / 4, and it says so in the output: this file
has no tokenizer and refuses to pretend. It is stable enough to compare a file
with itself before and after a rewrite, which is the only comparison a diet
needs. Block-level HTML comments in CLAUDE.md files are removed before
counting, because Claude Code removes them before injection.

Standard library only, like every tool in this directory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HTML_COMMENT = re.compile(r"^[ \t]*<!--.*?-->[ \t]*\n?", re.DOTALL | re.MULTILINE)
_PATHS_KEY = re.compile(r"^paths\s*:", re.MULTILINE)


def _estimate_tokens(text: str) -> int:
    return round(len(text) / 4)


def _strip_comments(text: str) -> str:
    return _HTML_COMMENT.sub("", text)


def _frontmatter(text: str) -> str:
    match = _FRONTMATTER.match(text)
    return match.group(1) if match else ""


def _is_path_scoped(text: str) -> bool:
    return bool(_PATHS_KEY.search(_frontmatter(text)))


def _skill_description(text: str) -> str:
    """Only name and description of a skill are loaded at startup."""
    return "\n".join(
        line for line in _frontmatter(text).splitlines()
        if re.match(r"^(name|description)\s*:", line)
    )


def _memory_index(project: Path) -> Path | None:
    """The harness derives the memory directory from the project path."""
    root = Path.home() / ".claude" / "projects"
    candidates = {
        re.sub(r"[^A-Za-z0-9]", "-", str(project)),
        re.sub(r"[^A-Za-z0-9]", "-", str(project).lower()),
    }
    for slug in candidates:
        index = root / slug / "memory" / "MEMORY.md"
        if index.is_file():
            return index
    return None


def collect(project: Path, project_only: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def add(kind: str, path: Path, text: str, loaded: str) -> None:
        rows.append({
            "kind": kind,
            "path": str(path),
            "lines": len(text.splitlines()),
            "chars": len(text),
            "tokens_est": _estimate_tokens(text),
            "loaded": loaded,
        })

    home = Path.home() / ".claude"
    scopes: list[tuple[str, Path]] = [("project", project)]
    if not project_only:
        scopes.insert(0, ("user", home))

    for scope, base in scopes:
        for name in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
            path = base / name
            if path.is_file():
                add(f"{scope} instructions", path, _strip_comments(path.read_text(encoding="utf-8")), "always")
        rules_dir = base / ("rules" if scope == "user" else ".claude/rules")
        for path in sorted(rules_dir.rglob("*.md")) if rules_dir.is_dir() else []:
            text = path.read_text(encoding="utf-8")
            if _is_path_scoped(text):
                add(f"{scope} rule (path-scoped)", path, text, "on demand")
            else:
                add(f"{scope} rule", path, text, "always")
        skills_dir = base / ("skills" if scope == "user" else ".claude/skills")
        for path in sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []:
            add(f"{scope} skill description", path, _skill_description(path.read_text(encoding="utf-8")), "always")

    if not project_only:
        index = _memory_index(project)
        if index is not None:
            text = index.read_text(encoding="utf-8")
            add("auto-memory index", index, "\n".join(text.splitlines()[:200]), "always")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="What is loaded at every session start.")
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--project-only", action="store_true", help="skip ~/.claude and memory")
    parser.add_argument("--max-tokens", type=int, help="exit 2 when the always-loaded estimate exceeds this")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    rows = collect(args.project.resolve(), args.project_only)
    always = [r for r in rows if r["loaded"] == "always"]
    total = sum(int(r["tokens_est"]) for r in always)

    if args.json:
        print(json.dumps({"rows": rows, "always_loaded_tokens_est": total}, indent=1))
    else:
        width = max((len(str(r["path"])) for r in rows), default=20)
        print(f"{'file':<{width}}  {'lines':>5}  {'chars':>6}  {'~tokens':>7}  loaded")
        for r in rows:
            print(f"{r['path']:<{width}}  {r['lines']:>5}  {r['chars']:>6}  {r['tokens_est']:>7}  {r['loaded']}")
        print(f"\nalways loaded: ~{total} tokens (characters / 4 -- an estimate, not a count)")

    if args.max_tokens is not None and total > args.max_tokens:
        print(f"over the budget of {args.max_tokens}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
