#!/usr/bin/env python3
"""Audit a folder of agent skills against the Agent Skills specification.

Standard library only. Writes a Markdown report; by default to
local/skills-audit.md, which is gitignored so a personal audit never
reaches a public repository.

Usage:
    python tools/audit_skills.py [SKILLS_DIR] [-o REPORT]

SKILLS_DIR defaults to ~/.claude/skills.
"""
import argparse
import os
import re
import sys
from pathlib import Path

NAME_MAX = 64          # specification: name is 1 to 64 characters
DESC_MAX = 1024        # specification: description is 1 to 1024 characters
LINES_MAX = 500        # best practice: SKILL.md body under 500 lines
FILES_WARN = 200       # more files than this usually means a bundled venv
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VENV_NAMES = {".venv", "venv", "node_modules", "__pycache__"}


def frontmatter(text):
    """Return the frontmatter as a dict of top level keys to raw values."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            fields[key] += " " + line.strip()
    return None


def walk(skill_dir):
    """Return (file count, folder names), skipping unreadable links."""
    files, dirs = 0, set()
    for _, subdirs, names in os.walk(skill_dir, onerror=lambda e: None):
        files += len(names)
        dirs.update(subdirs)
    return files, dirs


def audit(skill_dir):
    """Return (name, desc_len, lines, files, problems) for one skill."""
    problems = []
    skill_md = skill_dir / "SKILL.md"
    files, dirs = walk(skill_dir)
    if not skill_md.is_file():
        return skill_dir.name, 0, 0, files, ["no SKILL.md"]
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    lines = len(text.splitlines())
    meta = frontmatter(text)
    if meta is None:
        return skill_dir.name, 0, lines, files, ["no frontmatter"]
    name = meta.get("name", "").strip("\"'")
    desc = meta.get("description", "").strip("\"'")
    if not name:
        problems.append("name missing")
    elif len(name) > NAME_MAX or not NAME_RE.match(name):
        problems.append("name breaks the spec")
    elif name != skill_dir.name:
        problems.append("name differs from folder")
    if not desc:
        problems.append("description missing")
    elif len(desc) > DESC_MAX:
        problems.append(f"description over {DESC_MAX}")
    if lines > LINES_MAX:
        problems.append(f"SKILL.md over {LINES_MAX} lines")
    bundled = sorted(dirs & VENV_NAMES)
    if bundled:
        problems.append("contains " + ", ".join(bundled))
    elif files > FILES_WARN:
        problems.append(f"over {FILES_WARN} files")
    return name or skill_dir.name, len(desc), lines, files, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("skills_dir", nargs="?",
                        default=str(Path.home() / ".claude" / "skills"))
    parser.add_argument("-o", "--output", default="local/skills-audit.md")
    args = parser.parse_args()

    root = Path(args.skills_dir).expanduser()
    if not root.is_dir():
        sys.exit(f"not a folder: {root}")
    skills = sorted(p for p in root.iterdir()
                    if p.is_dir() and (p / "SKILL.md").exists())
    rows = [audit(p) for p in skills]
    flagged = sum(1 for r in rows if r[4])
    summary = (f"{len(rows)} skill{'s' if len(rows) != 1 else ''} checked, "
               f"{flagged} with problems")

    out = ["# Skills audit", "",
           summary + ".", "",
           "| Skill | Description chars | SKILL.md lines | Files | Problems |",
           "|---|---|---|---|---|"]
    for name, desc_len, lines, files, problems in rows:
        out.append(f"| `{name}` | {desc_len} | {lines} | {files} | "
                   f"{'; '.join(problems) or 'none'} |")
    report = Path(args.output)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(summary)
    print(f"wrote {report}")


if __name__ == "__main__":
    main()
