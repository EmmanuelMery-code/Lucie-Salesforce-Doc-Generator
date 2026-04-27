"""Inject AI usage tags into the BadPattern org metadata.

Adds ``@IAgenerated``, ``@IAassisted`` and ``@MadeInClaude`` markers to the
descriptions of every custom element retrieved from the org with alias
``badPattern`` (custom objects, custom fields, validation rules, record
types, custom flows) and prepends a tag header to every Apex class /
trigger source file. The tags are distributed round-robin so the
generated report shows a representative mix of all three values.

The script is idempotent: it skips any file whose targeted location
already carries one of the configured tags, so it can be re-run safely
after a fresh ``retrieve``.
"""

from __future__ import annotations

import re
import sys
from itertools import cycle
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "Bad Pattern20260425" / "retrieveAfter" / "force-app" / "main" / "default"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AI_TAGS: tuple[str, ...] = ("@IAgenerated", "@IAassisted", "@MadeInClaude")

# Friendly summaries used in the description so the resulting line still
# reads naturally instead of being a bare tag.
DESCRIPTION_TEMPLATES: dict[str, str] = {
    "@IAgenerated": "Genere avec assistance IA. {tag}",
    "@IAassisted": "Revise avec assistance IA. {tag}",
    "@MadeInClaude": "Concu avec Claude. {tag}",
}


def _has_any_tag(text: str) -> bool:
    """Return ``True`` when ``text`` already carries any configured tag."""

    lowered = text.casefold()
    return any(tag.casefold() in lowered for tag in AI_TAGS)


def _build_description(tag: str) -> str:
    template = DESCRIPTION_TEMPLATES.get(tag, "{tag}")
    return template.format(tag=tag)


# ---------------------------------------------------------------------------
# XML helpers (regex based for safe round-trip)
# ---------------------------------------------------------------------------


def _insert_description(
    xml: str,
    description: str,
    *,
    after_tags: tuple[str, ...] = ("fullName", "active", "apiVersion"),
    before_tags: tuple[str, ...] = ("label",),
    indent: str = "    ",
) -> tuple[str, bool]:
    """Insert a ``<description>`` element into ``xml``.

    When the document already has a ``<description>`` element the function
    appends the new text inside it (with a space separator) so the existing
    content is preserved. Otherwise the new element is inserted after the
    first occurrence of one of ``after_tags`` (or, failing that, before the
    first ``before_tags`` element). Returns the updated XML and a flag
    telling whether anything was changed.
    """

    description_pattern = re.compile(
        r"<description>(?P<body>.*?)</description>", re.DOTALL
    )
    existing = description_pattern.search(xml)
    if existing is not None:
        body = existing.group("body")
        if _has_any_tag(body):
            return xml, False
        new_body = body.rstrip()
        joiner = " " if new_body and not new_body.endswith((".", "!", "?")) else " "
        if not new_body:
            new_body = description
        else:
            new_body = f"{new_body}{joiner}{description}"
        replacement = f"<description>{new_body}</description>"
        return description_pattern.sub(replacement, xml, count=1), True

    for after_tag in after_tags:
        anchor = re.compile(
            rf"(?P<indent>[ \t]*)<{after_tag}>[^<]*</{after_tag}>\s*\n"
        )
        match = anchor.search(xml)
        if match:
            insertion_point = match.end()
            indent_used = match.group("indent") or indent
            return (
                xml[:insertion_point]
                + f"{indent_used}<description>{description}</description>\n"
                + xml[insertion_point:],
                True,
            )

    for before_tag in before_tags:
        anchor = re.compile(rf"(?P<indent>[ \t]*)<{before_tag}>")
        match = anchor.search(xml)
        if match:
            insertion_point = match.start()
            indent_used = match.group("indent") or indent
            return (
                xml[:insertion_point]
                + f"{indent_used}<description>{description}</description>\n"
                + xml[insertion_point:],
                True,
            )

    return xml, False


# ---------------------------------------------------------------------------
# File walkers
# ---------------------------------------------------------------------------


def _iter_custom_object_files(objects_dir: Path) -> list[Path]:
    """Return the metadata files for objects ending in ``__c``."""

    return sorted(
        path
        for path in objects_dir.glob("*__c/*.object-meta.xml")
        if path.is_file()
    )


def _iter_custom_field_files(objects_dir: Path) -> list[Path]:
    """Return field metadata files whose API name ends in ``__c``.

    Custom fields under standard objects (e.g. ``Account/SLA__c``) are
    included, while standard fields under custom objects are not (none
    actually exist in the BadPattern retrieval, but the filter keeps the
    semantics correct).
    """

    return sorted(
        path
        for path in objects_dir.rglob("fields/*__c.field-meta.xml")
        if path.is_file()
    )


def _iter_validation_rule_files(objects_dir: Path) -> list[Path]:
    """Return validation rule files belonging to custom objects."""

    return sorted(
        path
        for path in objects_dir.glob("*__c/validationRules/*.validationRule-meta.xml")
        if path.is_file()
    )


def _iter_record_type_files(objects_dir: Path) -> list[Path]:
    """Return record type files belonging to custom objects."""

    return sorted(
        path
        for path in objects_dir.glob("*__c/recordTypes/*.recordType-meta.xml")
        if path.is_file()
    )


def _iter_flow_files(flows_dir: Path) -> list[Path]:
    """Return all flow metadata files."""

    return sorted(flows_dir.glob("*.flow-meta.xml"))


def _iter_apex_files(default_dir: Path) -> list[Path]:
    """Return Apex class and trigger source files (not the meta XML)."""

    classes = sorted(default_dir.glob("classes/*.cls"))
    triggers = sorted(default_dir.glob("triggers/*.trigger"))
    return classes + triggers


# ---------------------------------------------------------------------------
# Apex tagger
# ---------------------------------------------------------------------------


APEX_HEADER_TEMPLATE = (
    "/**\n"
    " * {description}\n"
    " * Tag: {tag}\n"
    " */\n"
)


def _tag_apex_file(path: Path, tag: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if _has_any_tag(text):
        return False
    description = _build_description(tag)
    header = APEX_HEADER_TEMPLATE.format(description=description, tag=tag)
    new_text = header + text if not text.startswith("/**") else text
    if new_text == text:
        # File already starts with a javadoc; insert the tag inside it.
        new_text = re.sub(
            r"^/\*\*",
            f"/**\n * Tag: {tag}",
            text,
            count=1,
        )
    path.write_text(new_text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# XML tagger
# ---------------------------------------------------------------------------


def _tag_xml_file(path: Path, tag: str) -> bool:
    description = _build_description(tag)
    text = path.read_text(encoding="utf-8")
    if _has_any_tag(text):
        return False
    new_text, changed = _insert_description(text, description)
    if changed:
        path.write_text(new_text, encoding="utf-8")
    return changed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    if not SOURCE_ROOT.exists():
        print(f"Source folder introuvable: {SOURCE_ROOT}", file=sys.stderr)
        return 1

    objects_dir = SOURCE_ROOT / "objects"
    flows_dir = SOURCE_ROOT / "flows"

    targets: list[tuple[str, list[Path]]] = [
        ("Custom objects", _iter_custom_object_files(objects_dir)),
        ("Custom fields", _iter_custom_field_files(objects_dir)),
        ("Validation rules (custom objects)", _iter_validation_rule_files(objects_dir)),
        ("Record types (custom objects)", _iter_record_type_files(objects_dir)),
        ("Flows", _iter_flow_files(flows_dir)),
        ("Apex sources", _iter_apex_files(SOURCE_ROOT)),
    ]

    tag_iterator = cycle(AI_TAGS)
    summary: dict[str, dict[str, int]] = {}

    for category, files in targets:
        per_tag: dict[str, int] = {tag: 0 for tag in AI_TAGS}
        skipped = 0
        for file_path in files:
            tag = next(tag_iterator)
            if file_path.suffix in {".cls", ".trigger"}:
                changed = _tag_apex_file(file_path, tag)
            else:
                changed = _tag_xml_file(file_path, tag)
            if changed:
                per_tag[tag] += 1
            else:
                skipped += 1
        summary[category] = {
            "total_files": len(files),
            "modified": sum(per_tag.values()),
            "skipped": skipped,
            **per_tag,
        }

    print(f"Source: {SOURCE_ROOT}\n")
    for category, stats in summary.items():
        modified = stats["modified"]
        total = stats["total_files"]
        per_tag_view = ", ".join(
            f"{tag}={stats[tag]}" for tag in AI_TAGS if tag in stats
        )
        print(
            f"- {category}: {modified}/{total} fichier(s) modifie(s) "
            f"(deja taggue(s): {stats['skipped']}) | {per_tag_view}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
