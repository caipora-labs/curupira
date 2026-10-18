"""Fail when a translated docs page is not structurally equivalent to its English source.

Every page in ``docs/en`` must exist in ``docs/pt`` and ``docs/es`` with the same headings and
explicit heading ids, tables, code blocks, list items, admonitions, link targets, and
placeholders. Prose is translated, so only structure and code-like tokens are compared.

Usage: ``python .github/scripts/check_docs_parity.py [docs_dir]``
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

LANGUAGES = ("pt", "es")
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*(?:\{\s*#([\w-]+)\s*\})?\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
LINK = re.compile(r"\]\(([^)\s]+)\)")
PLACEHOLDER = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}|\{\{.*?\}\}|\{%.*?%\}")
MACRO_CALL = re.compile(r"\{\{\s*(\w+)\(.*?\)\s*\}\}")
ADMONITION = re.compile(r"^\s*!!!\s+\w+")


def fingerprint(text: str) -> dict[str, object]:
    """Structure of a page that translation must not change."""
    headings: list[int] = []
    ids: list[str] = []
    counts: Counter[str] = Counter()
    in_fence = False
    prose: list[str] = []
    for line in text.splitlines():
        if FENCE.match(line):
            counts["fences"] += 1
            in_fence = not in_fence
            continue
        if in_fence:
            continue  # code is compared through its placeholders, not its translated comments
        prose.append(line)
        heading = HEADING.match(line)
        if heading:
            headings.append(len(heading.group(1)))
            if heading.group(3):
                ids.append(heading.group(3))
        elif line.lstrip().startswith("|"):
            counts["table_rows"] += 1
        elif LIST_ITEM.match(line):
            counts["list_items"] += 1
        elif ADMONITION.match(line):
            counts["admonitions"] += 1
    body = "\n".join(prose)
    targets = Counter(
        target.split("#", 1)[0].replace("../en/", "") + _anchor(target)
        for target in LINK.findall(body)
        if not target.startswith(("http://", "https://", "mailto:"))
    )
    return {
        "headings": headings,
        "ids": sorted(ids),
        "counts": dict(counts),
        "links": targets,
        # Macro calls only differ by their language argument: `{{ triggers_table("pt") }}`.
        "placeholders": Counter(
            MACRO_CALL.sub(r"{{ \1() }}", match) for match in PLACEHOLDER.findall(text)
        ),
    }


def _anchor(target: str) -> str:
    return "#" + target.split("#", 1)[1] if "#" in target else ""


def compare(page: str, language: str, english: str, other: str) -> list[str]:
    problems: list[str] = []
    base, translated = fingerprint(english), fingerprint(other)
    labels = {
        "headings": "heading levels/order",
        "ids": "explicit heading ids",
        "counts": "table rows / list items / code blocks / admonitions",
        "links": "link targets",
        "placeholders": "${...} / {{ }} / {% %} placeholders",
    }
    for key, label in labels.items():
        if key == "ids":
            missing = sorted(set(base["ids"]) - set(translated["ids"]))  # type: ignore[arg-type]
            if missing:
                problems.append(f"{language}/{page}: missing explicit heading ids {missing}")
            continue
        if base[key] != translated[key]:
            problems.append(f"{language}/{page}: {label} differ from English")
            problems.append(f"    en: {base[key]}")
            problems.append(f"    {language}: {translated[key]}")
    front_en = english.startswith("---\n")
    if front_en != other.startswith("---\n"):
        problems.append(f"{language}/{page}: front matter differs from English")
    return problems


def explicit_ids(text: str) -> set[str]:
    return set(fingerprint(text)["ids"])  # type: ignore[arg-type]


def check_anchor_targets(docs: Path, language: str) -> list[str]:
    """Every `page.md#anchor` link in a translated page needs that id in the translated target."""
    problems: list[str] = []
    for page in sorted((docs / language).rglob("*.md")):
        base = page.parent
        for target in LINK.findall(page.read_text(encoding="utf-8")):
            if "#" not in target or target.startswith(("http://", "https://")):
                continue
            file_part, anchor = target.split("#", 1)
            destination = page if not file_part else (base / file_part).resolve()
            if not destination.is_file():
                continue
            if anchor not in explicit_ids(destination.read_text(encoding="utf-8")):
                name = page.relative_to(docs / language).as_posix()
                problems.append(
                    f"{language}/{name}: link {target!r} has no explicit id in the target"
                )
    return problems


def main(argv: list[str]) -> int:
    docs = Path(argv[1] if len(argv) > 1 else "docs")
    english_dir = docs / "en"
    problems: list[str] = []
    for source in sorted(english_dir.rglob("*.md")):
        page = source.relative_to(english_dir).as_posix()
        english = source.read_text(encoding="utf-8")
        for language in LANGUAGES:
            target = docs / language / page
            if not target.is_file():
                problems.append(f"{language}/{page}: missing translation")
                continue
            problems += compare(page, language, english, target.read_text(encoding="utf-8"))
    for language in LANGUAGES:
        problems += check_anchor_targets(docs, language)
        for extra in sorted((docs / language).rglob("*.md")):
            if not (english_dir / extra.relative_to(docs / language)).is_file():
                problems.append(f"{language}/{extra.relative_to(docs / language)}: no English page")
    if problems:
        print("\n".join(problems))
        print(
            f"\n{len([p for p in problems if not p.startswith('    ')])} documentation parity problem(s)"
        )
        return 1
    print("documentation parity ok: en, pt, es")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
