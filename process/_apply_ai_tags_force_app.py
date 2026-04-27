"""Inject AI usage tags into the BadPattern *deployable* source folder.

Targets ``Bad Pattern20260425/force-app/main/default`` (the SFDX
``packageDirectories`` entry) so the resulting tags can be deployed back
to the org with alias ``badPattern``.

The tags ``@IAgenerated``, ``@IAassisted`` and ``@MadeInClaude`` are
distributed round-robin and added either inside ``<description>``
elements (XML metadata) or inside a Javadoc-style header (Apex
sources). The script is idempotent and skips files that already carry
one of the configured tags.

Per the user requirement, custom objects, custom fields and flows whose
``<label>`` starts with ``my personal`` (case-insensitive) are never
touched. Other element types (record types, validation rules, Apex)
are not subject to that exclusion.
"""

from __future__ import annotations

import re
import sys
from itertools import cycle
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "Bad Pattern20260425" / "force-app" / "main" / "default"

AI_TAGS: tuple[str, ...] = ("@IAgenerated", "@IAassisted", "@MadeInClaude")

DESCRIPTION_TEMPLATES: dict[str, str] = {
    "@IAgenerated": "Genere avec assistance IA. {tag}",
    "@IAassisted": "Revise avec assistance IA. {tag}",
    "@MadeInClaude": "Concu avec Claude. {tag}",
}

EXCLUDED_LABEL_PREFIX = "my personal"


def _has_any_tag(text: str) -> bool:
    lowered = text.casefold()
    return any(tag.casefold() in lowered for tag in AI_TAGS)


def _build_description(tag: str) -> str:
    template = DESCRIPTION_TEMPLATES.get(tag, "{tag}")
    return template.format(tag=tag)


def _read_root_label(xml: str) -> str | None:
    """Return the first top-level ``<label>`` value (Object/Field/Flow root)."""

    match = re.search(r"<label>([^<]*)</label>", xml)
    if match is None:
        return None
    return match.group(1).strip()


def _is_excluded_by_label(xml: str) -> bool:
    label = _read_root_label(xml)
    if label is None:
        return False
    return label.casefold().startswith(EXCLUDED_LABEL_PREFIX.casefold())


def _insert_description(
    xml: str,
    description: str,
    *,
    after_tags: tuple[str, ...] = ("fullName", "active", "apiVersion"),
    before_tags: tuple[str, ...] = ("label",),
    indent: str = "    ",
) -> tuple[str, bool]:
    description_pattern = re.compile(
        r"<description>(?P<body>.*?)</description>", re.DOTALL
    )
    existing = description_pattern.search(xml)
    if existing is not None:
        body = existing.group("body")
        if _has_any_tag(body):
            return xml, False
        new_body = body.rstrip()
        if not new_body:
            new_body = description
        else:
            new_body = f"{new_body} {description}"
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


def _iter_custom_object_files(objects_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in objects_dir.glob("*__c/*.object-meta.xml")
        if path.is_file()
    )


def _iter_custom_field_files(objects_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in objects_dir.rglob("fields/*__c.field-meta.xml")
        if path.is_file()
    )


def _iter_validation_rule_files(objects_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in objects_dir.glob(
            "*__c/validationRules/*.validationRule-meta.xml"
        )
        if path.is_file()
    )


def _iter_record_type_files(objects_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in objects_dir.glob("*__c/recordTypes/*.recordType-meta.xml")
        if path.is_file()
    )


def _iter_flow_files(flows_dir: Path) -> list[Path]:
    if not flows_dir.exists():
        return []
    return sorted(flows_dir.glob("*.flow-meta.xml"))


def _iter_apex_files(default_dir: Path) -> list[Path]:
    classes = sorted(default_dir.glob("classes/*.cls"))
    triggers = sorted(default_dir.glob("triggers/*.trigger"))
    return classes + triggers


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
    if not text.startswith("/**"):
        new_text = APEX_HEADER_TEMPLATE.format(description=description, tag=tag) + text
    else:
        new_text = re.sub(
            r"^/\*\*",
            f"/**\n * Tag: {tag}",
            text,
            count=1,
        )
    path.write_text(new_text, encoding="utf-8")
    return True


def _tag_xml_file(
    path: Path,
    tag: str,
    *,
    enforce_label_exclusion: bool,
) -> tuple[bool, bool]:
    """Return ``(changed, excluded)`` after attempting to tag ``path``."""

    text = path.read_text(encoding="utf-8")
    if enforce_label_exclusion and _is_excluded_by_label(text):
        return False, True
    if _has_any_tag(text):
        return False, False
    description = _build_description(tag)
    new_text, changed = _insert_description(text, description)
    if changed:
        path.write_text(new_text, encoding="utf-8")
    return changed, False


def main() -> int:
    if not SOURCE_ROOT.exists():
        print(f"Source folder introuvable: {SOURCE_ROOT}", file=sys.stderr)
        return 1

    objects_dir = SOURCE_ROOT / "objects"
    flows_dir = SOURCE_ROOT / "flows"

    targets: list[tuple[str, list[Path], bool]] = [
        ("Custom objects", _iter_custom_object_files(objects_dir), True),
        ("Custom fields", _iter_custom_field_files(objects_dir), True),
        (
            "Validation rules (custom objects)",
            _iter_validation_rule_files(objects_dir),
            False,
        ),
        (
            "Record types (custom objects)",
            _iter_record_type_files(objects_dir),
            False,
        ),
        ("Flows", _iter_flow_files(flows_dir), True),
        ("Apex sources", _iter_apex_files(SOURCE_ROOT), False),
    ]

    tag_iterator = cycle(AI_TAGS)
    summary: dict[str, dict[str, int]] = {}

    for category, files, enforce_exclusion in targets:
        per_tag: dict[str, int] = {tag: 0 for tag in AI_TAGS}
        skipped = 0
        excluded = 0
        for file_path in files:
            tag = next(tag_iterator)
            if file_path.suffix in {".cls", ".trigger"}:
                changed = _tag_apex_file(file_path, tag)
                was_excluded = False
            else:
                changed, was_excluded = _tag_xml_file(
                    file_path,
                    tag,
                    enforce_label_exclusion=enforce_exclusion,
                )
            if changed:
                per_tag[tag] += 1
            elif was_excluded:
                excluded += 1
            else:
                skipped += 1
        summary[category] = {
            "total_files": len(files),
            "modified": sum(per_tag.values()),
            "skipped": skipped,
            "excluded": excluded,
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
            f"(deja taggue(s): {stats['skipped']}, exclus 'my personal': "
            f"{stats['excluded']}) | {per_tag_view}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
