"""Scan a :class:`MetadataSnapshot` for AI usage tags.

The "AI usage" indicator counts metadata elements that mention one of the
configured tag values (e.g. ``@IAgenerated``, ``@IAassisted``) in their
description (objects, fields, validation rules, record types, flows, flow
elements, profiles, permission sets) or in source comments (Apex classes
and triggers).

The scanner is intentionally pure: it takes a snapshot plus the list of
tag strings and returns a list of :class:`AIUsageEntry` objects. Rendering
and persistence are handled elsewhere so this module stays trivial to
unit-test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.core.models import MetadataSnapshot


@dataclass(slots=True)
class AIUsageEntry:
    """One element flagged as AI-assisted.

    ``element_type`` is a short, human-readable category (``"Field"``,
    ``"ApexClass"``...) that the detail page renders as-is. ``element_name``
    points to the unique identifier of the element (e.g. ``"Account.Foo__c"``
    for fields). ``tag`` is the matched tag value, kept exactly as it was
    written in the metadata so users can spot typos. ``source`` and
    ``line_number`` help the reader open the right file. ``excerpt`` is the
    full line where the tag was found, trimmed of leading/trailing
    whitespace.
    """

    element_type: str
    element_name: str
    tag: str
    source: str = ""
    line_number: int | None = None
    excerpt: str = ""
    location: str = ""


@dataclass(slots=True, frozen=True)
class CustomElement:
    """A single element belonging to the customisation/code/low-code universe.

    The "AI usage" indicator compares the population of customised elements
    of an org (custom objects, custom fields, validation rules, record
    types, flows, Apex classes/triggers) against the subset that carries an
    AI tag. Each element is identified by the same ``(element_type,
    element_name)`` tuple used by :class:`AIUsageEntry`, which lets us join
    the two collections without ambiguity.
    """

    element_type: str
    element_name: str
    source: str = ""


@dataclass(slots=True)
class AIUsageStats:
    """Aggregate AI-usage figures for the index card and detail page.

    Keeping the lists (rather than just counts) lets the detail page render
    the elements without a tag explicitly, which is what reviewers usually
    want: a checklist of items still to flag or document. ``percent_*``
    helpers return values in the ``[0.0, 100.0]`` range and gracefully
    degrade to ``0.0`` when the universe is empty so callers never have to
    guard against division by zero.
    """

    universe: list[CustomElement] = field(default_factory=list)
    with_tag: list[CustomElement] = field(default_factory=list)
    without_tag: list[CustomElement] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.universe)

    @property
    def with_tag_count(self) -> int:
        return len(self.with_tag)

    @property
    def without_tag_count(self) -> int:
        return len(self.without_tag)

    @property
    def percent_with_tag(self) -> float:
        return (self.with_tag_count / self.total * 100.0) if self.total else 0.0

    @property
    def percent_without_tag(self) -> float:
        return (self.without_tag_count / self.total * 100.0) if self.total else 0.0


# ---------------------------------------------------------------------------
# Tag matching helpers
# ---------------------------------------------------------------------------


def _match_tags(text: str, tags: list[str]) -> list[tuple[int, str, str]]:
    """Return ``(line_number, matched_tag, line_text)`` triples found in ``text``.

    Matching is case-insensitive and operates line by line; a single line may
    yield several entries when it carries more than one configured tag. The
    matched tag is the value as configured (preserving the user-chosen case)
    so the report stays consistent across descriptions written with mixed
    capitalisation.
    """

    if not text or not tags:
        return []

    matches: list[tuple[int, str, str]] = []
    lowered_tags = [(tag, tag.casefold()) for tag in tags if tag]
    for index, line in enumerate(text.splitlines(), start=1):
        haystack = line.casefold()
        for tag, lowered in lowered_tags:
            if lowered and lowered in haystack:
                matches.append((index, tag, line.strip()))
    return matches


def _extract_apex_comments(body: str) -> list[tuple[int, str]]:
    """Return ``(line_number, comment_text)`` for every Apex comment line.

    Tracks block-comment state across lines so multi-line ``/* ... */``
    blocks are correctly captured, including javadoc-style ``/** ... */``
    markers used for headers. Single-line ``//`` comments (full-line or
    trailing) are also captured. Strings are not pre-stripped: tags inside
    string literals would not normally collide with the configured markers
    (which start with ``@``).
    """

    if not body:
        return []

    comments: list[tuple[int, str]] = []
    in_block = False
    for index, line in enumerate(body.splitlines(), start=1):
        cursor = 0
        n = len(line)
        buffer: list[str] = []
        while cursor < n:
            ch = line[cursor]
            nxt = line[cursor + 1] if cursor + 1 < n else ""
            if in_block:
                end = line.find("*/", cursor)
                if end == -1:
                    buffer.append(line[cursor:])
                    cursor = n
                else:
                    buffer.append(line[cursor:end])
                    cursor = end + 2
                    in_block = False
            elif ch == "/" and nxt == "/":
                buffer.append(line[cursor + 2 :])
                cursor = n
            elif ch == "/" and nxt == "*":
                in_block = True
                cursor += 2
            elif ch in ('"', "'"):
                quote = ch
                cursor += 1
                while cursor < n:
                    if line[cursor] == "\\" and cursor + 1 < n:
                        cursor += 2
                    elif line[cursor] == quote:
                        cursor += 1
                        break
                    else:
                        cursor += 1
            else:
                cursor += 1
        comment_text = " ".join(part.strip() for part in buffer if part.strip())
        if comment_text:
            comments.append((index, comment_text))
    return comments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_ai_usage(
    snapshot: MetadataSnapshot,
    tags: list[str] | tuple[str, ...] | None,
) -> list[AIUsageEntry]:
    """Walk the metadata snapshot and return every AI-tagged element.

    Returned entries are sorted by element type then element name to keep
    the rendered table stable across runs (and easier to diff across
    releases).
    """

    if not tags:
        return []

    tag_list = [t for t in tags if isinstance(t, str) and t.strip()]
    if not tag_list:
        return []

    entries: list[AIUsageEntry] = []

    def _emit_from_text(
        element_type: str,
        element_name: str,
        text: str,
        source_path: Path | None,
        location: str = "",
    ) -> None:
        for line_number, tag, line_text in _match_tags(text, tag_list):
            entries.append(
                AIUsageEntry(
                    element_type=element_type,
                    element_name=element_name,
                    tag=tag,
                    source=str(source_path) if source_path else "",
                    line_number=line_number,
                    excerpt=line_text,
                    location=location or "description",
                )
            )

    for obj in snapshot.objects:
        _emit_from_text(
            "Object",
            obj.api_name,
            obj.description,
            obj.source_path,
            "object description",
        )
        for field_info in obj.fields:
            _emit_from_text(
                "Field",
                f"{obj.api_name}.{field_info.api_name}",
                field_info.description,
                obj.source_path,
                "field description",
            )
        for record_type in obj.record_types:
            _emit_from_text(
                "RecordType",
                f"{obj.api_name}.{record_type.full_name}",
                record_type.description,
                obj.source_path,
                "record type description",
            )
        for validation_rule in obj.validation_rules:
            _emit_from_text(
                "ValidationRule",
                f"{obj.api_name}.{validation_rule.full_name}",
                validation_rule.description,
                obj.source_path,
                "validation rule description",
            )

    for flow in snapshot.flows:
        _emit_from_text(
            "Flow",
            flow.name,
            flow.description,
            flow.source_path,
            "flow description",
        )
        for element in flow.elements:
            _emit_from_text(
                "FlowElement",
                f"{flow.name}.{element.name or element.label or element.element_type}",
                element.description,
                flow.source_path,
                f"flow element {element.element_type}",
            )

    for profile in snapshot.profiles:
        _emit_from_text(
            "Profile",
            profile.name,
            profile.description,
            profile.source_path,
            "profile description",
        )

    for permission_set in snapshot.permission_sets:
        _emit_from_text(
            "PermissionSet",
            permission_set.name,
            permission_set.description,
            permission_set.source_path,
            "permission set description",
        )

    for artifact in snapshot.apex_artifacts:
        element_type = "ApexTrigger" if artifact.kind == "trigger" else "ApexClass"
        for line_number, comment_text in _extract_apex_comments(artifact.body):
            for line_idx, tag, line_text in _match_tags(comment_text, tag_list):
                # ``_match_tags`` may split a multi-segment comment back into
                # several lines; in our case ``comment_text`` is already a
                # single logical line so ``line_idx`` is always 1 and we keep
                # the original ``line_number`` from the source body.
                _ = line_idx
                entries.append(
                    AIUsageEntry(
                        element_type=element_type,
                        element_name=artifact.name,
                        tag=tag,
                        source=str(artifact.source_path),
                        line_number=line_number,
                        excerpt=line_text,
                        location="apex comment",
                    )
                )

    entries.sort(
        key=lambda entry: (
            entry.element_type.casefold(),
            entry.element_name.casefold(),
            entry.line_number or 0,
            entry.tag.casefold(),
        )
    )
    return entries


def count_unique_elements(entries: list[AIUsageEntry]) -> int:
    """Count the number of distinct (element_type, element_name) pairs.

    The index card displays this aggregated value: a single field with two
    tags should count once, not twice.
    """

    return len({(entry.element_type, entry.element_name) for entry in entries})


# ---------------------------------------------------------------------------
# Customisation universe (with / without AI tag)
# ---------------------------------------------------------------------------


# Element types reported in :class:`AIUsageStats`. Profiles, permission sets
# and flow elements are *scanned* by :func:`scan_ai_usage` (so the detail page
# still surfaces tags found there) but they are not part of the
# customisation/code/low-code population the user asked us to evaluate, hence
# they do not appear in the universe.
_UNIVERSE_TYPES: tuple[str, ...] = (
    "Object",
    "Field",
    "RecordType",
    "ValidationRule",
    "Flow",
    "ApexClass",
    "ApexTrigger",
)


def _is_custom_field(field_info, parent_object) -> bool:
    """Return ``True`` for custom fields under standard or custom objects.

    Salesforce marks custom fields with the ``__c`` suffix; we honour the
    parser-provided ``custom`` flag first and fall back to the suffix
    convention so namespaced or managed-package fields are still detected
    when the parser left the flag unset.
    """

    if getattr(field_info, "custom", False):
        return True
    api_name = getattr(field_info, "api_name", "") or ""
    return api_name.endswith("__c")


def enumerate_customization_universe(
    snapshot: MetadataSnapshot,
) -> list[CustomElement]:
    """Return every custom/code/low-code element of the snapshot.

    Includes:

    * Custom objects (``__c``).
    * Custom fields under any object (standard or custom).
    * Record types declared on custom objects (record types on standard
      objects are out-of-scope: they are configuration of a standard
      Salesforce surface, not customisation we own).
    * Validation rules (always considered customisation).
    * Every flow.
    * Every Apex class and trigger.
    """

    universe: list[CustomElement] = []

    for obj in snapshot.objects:
        obj_source = str(obj.source_path) if obj.source_path else ""

        if obj.custom:
            universe.append(
                CustomElement(
                    element_type="Object",
                    element_name=obj.api_name,
                    source=obj_source,
                )
            )

        for field_info in obj.fields:
            if _is_custom_field(field_info, obj):
                universe.append(
                    CustomElement(
                        element_type="Field",
                        element_name=f"{obj.api_name}.{field_info.api_name}",
                        source=obj_source,
                    )
                )

        if obj.custom:
            for record_type in obj.record_types:
                universe.append(
                    CustomElement(
                        element_type="RecordType",
                        element_name=f"{obj.api_name}.{record_type.full_name}",
                        source=obj_source,
                    )
                )

        for validation_rule in obj.validation_rules:
            universe.append(
                CustomElement(
                    element_type="ValidationRule",
                    element_name=f"{obj.api_name}.{validation_rule.full_name}",
                    source=obj_source,
                )
            )

    for flow in snapshot.flows:
        universe.append(
            CustomElement(
                element_type="Flow",
                element_name=flow.name,
                source=str(flow.source_path) if flow.source_path else "",
            )
        )

    for artifact in snapshot.apex_artifacts:
        element_type = "ApexTrigger" if artifact.kind == "trigger" else "ApexClass"
        universe.append(
            CustomElement(
                element_type=element_type,
                element_name=artifact.name,
                source=str(artifact.source_path) if artifact.source_path else "",
            )
        )

    universe.sort(
        key=lambda item: (item.element_type.casefold(), item.element_name.casefold())
    )
    return universe


def compute_ai_usage_stats(
    snapshot: MetadataSnapshot,
    entries: list[AIUsageEntry],
) -> AIUsageStats:
    """Combine the snapshot universe with detected AI entries.

    A custom Flow is also considered "with tag" when one of its inner
    elements (a ``FlowElement`` entry such as a decision or assignment)
    carries the tag, so a partially generated flow does not slip into the
    "without tag" bucket.
    """

    universe = enumerate_customization_universe(snapshot)
    tagged_keys = {(entry.element_type, entry.element_name) for entry in entries}

    flow_names_with_tagged_children = {
        entry.element_name.split(".", 1)[0]
        for entry in entries
        if entry.element_type == "FlowElement" and "." in entry.element_name
    }

    def _is_tagged(element: CustomElement) -> bool:
        if (element.element_type, element.element_name) in tagged_keys:
            return True
        if (
            element.element_type == "Flow"
            and element.element_name in flow_names_with_tagged_children
        ):
            return True
        return False

    with_tag = [item for item in universe if _is_tagged(item)]
    without_tag = [item for item in universe if not _is_tagged(item)]

    return AIUsageStats(universe=universe, with_tag=with_tag, without_tag=without_tag)
