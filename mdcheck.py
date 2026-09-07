"""Check one Markdown file for the defects that silently break it.

Runs as a Claude Code `PostToolUse` hook after any `.md` is written, in every
project, and as a plain CLI for pre-commit, CI or a human.

    python mdcheck.py --hook          # hook JSON on stdin; checks one file
    python mdcheck.py FILE...         # explicit files
    python mdcheck.py --all DIR       # walk a tree
    python mdcheck.py --selftest      # prove the checks fire

WHAT IT DOES NOT DO, and this matters more than what it does. "Optimised" has
two halves. The mechanical half -- anchors that resolve, links that exist,
slugs that do not collide, fences that close -- is decidable, and that half is
here. The half that is worth more -- front-loading, density, whether an index
row actually answers the question the file gets opened for, whether the content
is still TRUE -- is judgement, and no script reaches it. This is a floor, not a
ceiling. Do not read a clean run as "the document is good".

TO UNINSTALL: delete the `hooks` key from ~/.claude/settings.json. Nothing else
is touched -- no project files, no git hooks, no installed packages.

Design constraints, each paid for by a specific failure mode:

* Standard library only. A checker with dependencies is a checker that stops
  starting one day, in the one project whose interpreter lacks them, and never
  starts again. That rules out pymarkdownlnt (pure Python, good tool) for this
  role; it belongs in a repo's own CI where a dependency is fine.
* A crash exits 0. The guardian must never cost more than what it guards: a
  hook that breaks sessions is uninstalled within a day, and it takes the
  useful part with it.
* One file per invocation in hook mode. No tree walk, no git subprocess.
* Link checking is opt-in per project. Notes and thesis folders are full of
  relative links to unversioned material; firing there would spend the
  credibility the checker needs for the cases that matter.

Per-project configuration is a `.mdcheck.json` at the repository root
(searched upwards from the file for a directory containing `.git`):

    {"check_links": true, "toc_min_lines": 100, "expiring_phrases": true}

`toc_min_lines` follows Anthropic's own skill-authoring guidance: give any
reference file over ~100 lines a table of contents, so a reader that samples
the head still sees the full scope. `expiring_phrases` is the one lexical
approximation of a judgement rule -- "per ora", "currently", a hand-kept
status line -- and it is opt-in for the same reason link checking is: notes
are allowed to be dated; a reference document is not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import get_close_matches
from pathlib import Path

HARD = "hard"
SOFT = "soft"

#: Path components that mean "not ours". Checked as whole components, so a
#: directory honestly named `my-vendor-notes` is not swept up by `vendor`.
_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "site-packages", "dist", "build", "target", "vendor", "third_party",
    ".tox", ".nox", "htmlcov", "_build", ".next", ".cache", "__pycache__",
})

#: A generated file is not a file anyone can fix.
_GENERATED = re.compile(
    r"<!--\s*generated|DO NOT EDIT|auto-?generated|@generated", re.IGNORECASE
)
_OFF = re.compile(r"<!--\s*mdcheck:\s*off\s*-->", re.IGNORECASE)
_IGNORE = re.compile(r"<!--\s*mdcheck:\s*ignore\s+([\w,\s]+?)\s*-->", re.IGNORECASE)

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
#: A URL a checker cannot resolve: a scheme, or a template placeholder.
_UNRESOLVABLE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|[{<$])", re.IGNORECASE)

#: A phrase that is true on the day it is written and wrong later, in the two
#: languages this machine writes. Word-bounded: "oggigiorno" is not "oggi".
_EXPIRING = re.compile(
    r"\b(per ora|al momento|attualmente|oggi|currently|for now|at the moment|"
    r"as of now|recently|di recente)\b",
    re.IGNORECASE,
)
#: A heading, title or file name that declares its content historical: a
#: dated report is *supposed* to say what was true that day.
_HISTORICAL = re.compile(
    r"storic|histor|changelog|milestone|audit|deviation|risultati|decision|defect",
    re.IGNORECASE,
)
_DATED = re.compile(r"\d{4}-\d{2}")
#: A "where the project is" line: a promise to edit it by hand at every step.
_STATUS_LINE = re.compile(
    r"^\s*(?:#{1,6}\s+|\*\*)\s*(?:where the project is|stato attuale|current state)",
    re.IGNORECASE,
)


class Finding:
    """One problem, with the repair in it. An unactionable warning is noise."""

    def __init__(self, line: int, severity: str, what: str, fix: str = "") -> None:
        self.line, self.severity, self.what, self.fix = line, severity, what, fix

    def __str__(self) -> str:
        tail = f"  → {self.fix}" if self.fix else ""
        return f"  L{self.line} {self.severity}  {self.what}{tail}"


def slug(heading: str) -> str:
    """GitHub's anchor rule: lowercase, drop punctuation, spaces to hyphens."""
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", heading.strip().lower()))


def _strip_code(lines: list[str]) -> tuple[list[str], int | None]:
    """Blank out fenced code, and report an unclosed fence's line number.

    Headings and links inside a code block are examples, not claims.
    """
    out: list[str] = []
    fence: str | None = None
    opened_at: int | None = None
    for number, line in enumerate(lines, start=1):
        marker = _FENCE.match(line)
        if fence is None and marker:
            fence, opened_at = marker.group(1), number
            out.append("")
            continue
        if fence is not None:
            if marker and marker.group(1)[0] == fence[0]:
                fence, opened_at = None, None
            out.append("")
            continue
        out.append(line)
    return out, opened_at


def _config_for(path: Path) -> dict[str, object]:
    """Nearest `.mdcheck.json` at or above the file's repository root."""
    for parent in [path.parent, *path.parents]:
        candidate = parent / ".mdcheck.json"
        if candidate.is_file():
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}
            return loaded if isinstance(loaded, dict) else {}
        if (parent / ".git").exists():
            break
    return {}


def check_text(text: str, path: Path, config: dict[str, object]) -> list[Finding]:
    """Every check, on one file's content."""
    findings: list[Finding] = []
    lines = text.split("\n")
    disabled = set()
    for match in _IGNORE.finditer(text):
        disabled |= {part.strip() for part in match.group(1).split(",")}

    body, unclosed = _strip_code(lines)

    # U3 - an unclosed fence swallows the rest of the document.
    if unclosed is not None and "fences" not in disabled:
        findings.append(Finding(
            unclosed, HARD, "code fence opened and never closed",
            "everything below it renders as code",
        ))

    headings = [
        (number, _HEADING.match(line).group(2))  # type: ignore[union-attr]
        for number, line in enumerate(body, start=1)
        if _HEADING.match(line)
    ]

    anchors = {slug(h) for _, h in headings}
    targeted = {
        t[1:] for line in body for t in _LINK.findall(line) if t.startswith("#")
    }

    # U2 - two headings, one slug: GitHub numbers the second, and every link
    # to it reaches the first instead, in silence.
    #
    # Reported ONLY when a link actually goes there, and that condition was
    # measured rather than guessed. Reporting every collision fired six times
    # on this machine's most careful repository ("Output tags" under three FR
    # sections, "Original plan" under two deviations) and dozens of times on
    # exam notes built from a repeated section template -- all of it normal
    # structure, none of it linked to. A collision nothing points at is not a
    # defect; it is how documents with recurring sections are shaped.
    # markdownlint concedes the same ground with `siblings_only`; this is the
    # sharper form of the concession, since it asks whether a link exists.
    if "slugs" not in disabled:
        seen: dict[str, int] = {}
        for number, heading in headings:
            key = slug(heading)
            if key not in seen:
                seen[key] = number
            elif key in targeted:
                findings.append(Finding(
                    number, HARD, f"duplicate anchor #{key}, and a link goes there",
                    f"the link reaches line {seen[key]} instead of this one",
                ))

    # U1 and U4 - links that land nowhere.
    check_links = bool(config.get("check_links", False))
    for number, line in enumerate(body, start=1):
        for target in _LINK.findall(line):
            if target.startswith("#"):
                if "anchors" in disabled:
                    continue
                name = target[1:]
                if name and name not in anchors:
                    near = get_close_matches(name, sorted(anchors), n=1)
                    findings.append(Finding(
                        number, HARD, f"anchor ({target}) matches no heading",
                        f"closest is #{near[0]}" if near else "no heading is close",
                    ))
            elif check_links and "links" not in disabled:
                if _UNRESOLVABLE.match(target):
                    continue
                relative = target.split("#", 1)[0]
                if relative and not (path.parent / relative).exists():
                    findings.append(Finding(
                        number, HARD, f"link ({target}) points at no file",
                        "the path does not exist on disk",
                    ))

    # C1 - a long reference file with no table of contents. Anthropic's own
    # skill-authoring guidance: over ~100 lines, a reader that samples the head
    # should still be able to see the whole scope.
    floor = config.get("toc_min_lines")
    if isinstance(floor, int) and len(lines) > floor and "toc" not in disabled:
        if not headings:
            findings.append(Finding(
                1, SOFT, f"{len(lines)} lines and no headings at all",
                "a reader sampling the head sees none of the scope",
            ))
        elif not re.search(r"\]\(#", text):
            findings.append(Finding(
                1, SOFT, f"{len(lines)} lines, no table of contents",
                "over the project's floor; an index makes the scope visible",
            ))

    # C2 - a phrase that expires ("per ora", "currently") outside anything
    # declared historical, and C3 - a hand-maintained status line. Both are
    # opt-in like link checking, and both are SOFT: they approximate a
    # judgement rule, and an approximation does not get to fail a commit.
    if config.get("expiring_phrases") and "expiring" not in disabled:
        title = headings[0][1] if headings else ""
        historical_file = any(
            rx.search(text) for rx in (_HISTORICAL, _DATED) for text in (title, path.name)
        )
        if not historical_file:
            heading_at = dict(headings)
            current = ""
            for number, line in enumerate(body, start=1):
                if number in heading_at:
                    current = heading_at[number]
                    continue
                if _STATUS_LINE.search(line):
                    findings.append(Finding(
                        number, SOFT, "a hand-maintained status line",
                        "point at the dated log instead; it already is the status",
                    ))
                    continue
                if _HISTORICAL.search(current):
                    continue
                hit = _EXPIRING.search(line)
                if hit:
                    findings.append(Finding(
                        number, SOFT, f"«{hit.group(0)}» will be wrong one day",
                        "state the fact, or move it under a heading named historical",
                    ))

    return findings


def check_file(path: Path) -> list[Finding] | None:
    """None means "deliberately not checked"; a list means it was."""
    if any(part in _SKIP_DIRS for part in path.parts):
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    head = "\n".join(text.split("\n")[:5])
    if _GENERATED.search(head) or _OFF.search(text):
        return None
    return check_text(text, path, _config_for(path))


#: A wall of identical findings is not read, it is dismissed. One transcript
#: in the thesis project produced thirteen at once; five and a count is the
#: readable form of the same information.
_MAX_SHOWN = 5


def _report(path: Path, findings: list[Finding]) -> str:
    shown = findings[:_MAX_SHOWN]
    lines = [f"mdcheck {path.name} — {len(findings)} issue(s)"]
    lines += [str(f) for f in shown]
    if len(findings) > len(shown):
        lines.append(f"  … and {len(findings) - len(shown)} more of the same kind")
    return "\n".join(lines)


def _run_hook() -> int:
    """Never fail loudly: a broken hook costs more than the defects it finds."""
    try:
        payload = json.load(sys.stdin)
        raw = (payload.get("tool_input") or {}).get("file_path")
        if not raw or not str(raw).lower().endswith((".md", ".markdown")):
            return 0
        path = Path(raw)
        findings = check_file(path)
        if not findings:
            return 0
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": _report(path, findings),
        }}))
    except Exception:  # noqa: BLE001 - deliberate: silence beats breakage
        return 0
    return 0


def _selftest() -> int:
    """Each check, watched failing. One never seen to fail is not known to work."""
    cases = {
        "broken anchor": ("# Title\n\n[go](#nope)\n", "anchor"),
        # A collision only matters when a link goes there; the fixture has to
        # carry the link, or it is testing the case that is deliberately mute.
        "duplicate slug a link points at": (
            "# Same\n\n[go](#same)\n\n## Same\n", "duplicate anchor"
        ),
        "unclosed fence": ("# T\n\n```python\nx = 1\n", "never closed"),
    }
    failures = []
    for label, (text, expected) in cases.items():
        found = check_text(text, Path("x.md"), {})
        if any(expected in f.what for f in found):
            print(f"  caught: {label}")
        else:
            failures.append(label)

    clean = check_text("# Title\n\n## Part\n\n[go](#part)\n", Path("x.md"), {})
    if clean:
        failures.append(f"false positive on a clean file: {[f.what for f in clean]}")
    else:
        print("  clean file: no findings")

    fenced = check_text("# T\n\n```\n# Not a heading\n```\n\n## Real\n", Path("x.md"), {})
    if fenced:
        failures.append(f"false positive inside a code fence: {[f.what for f in fenced]}")
    else:
        print("  headings inside a fence: ignored")

    # The measured case: a document built from a repeated section template.
    # Silence here is the whole reason the rule is conditional.
    repeated = check_text("# Exam\n\n## Setup\n\n## Notes\n\n## Setup\n", Path("x.md"), {})
    if repeated:
        failures.append(f"false positive on repeated sections: {[f.what for f in repeated]}")
    else:
        print("  repeated section headings nobody links to: ignored")

    # The opt-in lexical checks: each seen firing, and silent where a dated or
    # historical section makes the same words legitimate.
    expiring_on = {"expiring_phrases": True}
    live = "# Guide\n\n## Stato\n\nPer ora il comando fallisce.\n"
    if any("per ora" in f.what.lower() for f in check_text(live, Path("x.md"), expiring_on)):
        print("  caught: expiring phrase under a live heading")
    else:
        failures.append("expiring phrase under a live heading")
    status = "# Guide\n\n**Where the project is** (2026-09-07): M1 done.\n"
    if any("status line" in f.what for f in check_text(status, Path("x.md"), expiring_on)):
        print("  caught: hand-maintained status line")
    else:
        failures.append("hand-maintained status line")
    for label, fixture, cfg in (
        ("expiring phrase under a historical heading",
         "# Guide\n\n## Storico\n\nPer ora il comando falliva.\n", expiring_on),
        ("expiring phrase in a dated report",
         "# Referto (2026-08-02)\n\n## Stato\n\nPer ora fallisce.\n", expiring_on),
        ("expiring phrase with the check off", live, {}),
    ):
        if check_text(fixture, Path("x.md"), cfg):
            failures.append(f"false positive: {label}")
        else:
            print(f"  {label}: ignored")

    if failures:
        print(f"FAILED: {failures}")
        return 1
    print("every check fires, and none fires on a clean file")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Markdown files.")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--hook", action="store_true", help="read hook JSON on stdin")
    parser.add_argument("--all", type=Path, metavar="DIR", help="walk a tree")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    if args.hook:
        return _run_hook()
    if args.selftest:
        return _selftest()

    targets = list(args.paths)
    if args.all:
        # Path.rglob, never glob.glob: a directory named `[djmeta]` is a
        # character class to the latter, which then returns nothing at all.
        targets += sorted(args.all.rglob("*.md"))
    if not targets:
        parser.error("give paths, --all DIR, --hook or --selftest")

    worst = 0
    for path in targets:
        findings = check_file(path)
        if not findings:
            continue
        print(_report(path, findings))
        if any(f.severity == HARD for f in findings):
            worst = 2
    return worst


if __name__ == "__main__":
    sys.exit(main())
