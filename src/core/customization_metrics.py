"""Customisation and adoption metrics derived from a metadata snapshot.

The module exposes two complementary indicators that round out the
existing absolute scores (``CustomizationMetrics.score`` and
``CustomizationMetrics.adopt_adapt_score``):

* :class:`DataModelCustomisationStats` quantifies the *data model
  footprint* by comparing custom objects/fields to the standard ones
  present in the snapshot (approach A in the design discussion).
* :class:`AdoptionStats` evaluates the *Adopt vs Adapt posture* across a
  fixed catalogue of nine Salesforce capabilities (approach B). Each
  capability is rated ``Adopt`` (out-of-the-box), ``Adapt-Low``
  (declarative customisation) or ``Adapt-High`` (code customisation),
  and the catalogue is weighted so the most architecturally significant
  capabilities (data model, security, automation) drive the result.

Both structures expose ready-to-display percentages so the renderers do
not have to re-implement the maths or guard against a zero universe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.models import (
    ApexArtifact,
    MetadataSnapshot,
    ObjectInfo,
    SecurityArtifact,
)


# ---------------------------------------------------------------------------
# Data-model customisation (approach A)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DataModelCustomisationStats:
    """Counts of standard vs custom items in the snapshot data model.

    The denominator combines objects and fields because, on Salesforce, a
    "100 % custom" answer can come either from many custom objects or
    from many custom fields hanging off a standard object: showing the
    two breakdowns side by side avoids the misleading impression that
    one alone tells the whole story.
    """

    custom_objects: int = 0
    standard_objects: int = 0
    custom_fields: int = 0
    standard_fields: int = 0

    @property
    def total_objects(self) -> int:
        return self.custom_objects + self.standard_objects

    @property
    def total_fields(self) -> int:
        return self.custom_fields + self.standard_fields

    @property
    def percent_custom_objects(self) -> float:
        return (
            self.custom_objects / self.total_objects * 100.0
            if self.total_objects
            else 0.0
        )

    @property
    def percent_custom_fields(self) -> float:
        return (
            self.custom_fields / self.total_fields * 100.0
            if self.total_fields
            else 0.0
        )

    @property
    def percent_custom_global(self) -> float:
        """Global ratio = (custom_objects + custom_fields) / (total + total).

        Treats every object and every field as a single "data model unit".
        Objects therefore count more than they would in a simple field
        ratio, which feels right because adding a custom object is a
        much heavier customisation than adding one field.
        """

        custom = self.custom_objects + self.custom_fields
        total = self.total_objects + self.total_fields
        return custom / total * 100.0 if total else 0.0

    @property
    def percent_standard_global(self) -> float:
        return 100.0 - self.percent_custom_global if self.total_objects + self.total_fields else 0.0


def compute_data_model_stats(snapshot: MetadataSnapshot) -> DataModelCustomisationStats:
    """Aggregate the snapshot's objects and fields into custom/standard counts."""

    stats = DataModelCustomisationStats()
    for obj in snapshot.objects:
        if obj.custom:
            stats.custom_objects += 1
        else:
            stats.standard_objects += 1
        for fld in obj.fields:
            if fld.custom:
                stats.custom_fields += 1
            else:
                stats.standard_fields += 1
    return stats


# ---------------------------------------------------------------------------
# Adoption posture (approach B) - capability catalogue
# ---------------------------------------------------------------------------


class CapabilityLevel(str, Enum):
    """Maturity of a capability on the Adopt-Adapt axis.

    Stored as ``str`` so the enum values serialise naturally to JSON and
    compare directly against the labels rendered on the report.

    Two levels count as *adoption* (``ADOPT`` for out-of-the-box usage and
    ``ADOPT_DECLARATIVE`` for standard Salesforce features used through
    declarative tooling), while ``ADAPT_LOW`` / ``ADAPT_HIGH`` count as
    *adaptation*.
    """

    ADOPT = "Adopt (OOTB)"
    ADOPT_DECLARATIVE = "Adopt declaratif"
    ADAPT_LOW = "Adapt (declaratif)"
    ADAPT_HIGH = "Adapt (code)"


# All level identifiers exposed to the configuration UI. Order matters: it
# is the order used to render dropdowns and to scan for "auto" detection.
CAPABILITY_LEVEL_ORDER: tuple[CapabilityLevel, ...] = (
    CapabilityLevel.ADOPT,
    CapabilityLevel.ADOPT_DECLARATIVE,
    CapabilityLevel.ADAPT_LOW,
    CapabilityLevel.ADAPT_HIGH,
)


_ADOPTION_LEVELS: frozenset[CapabilityLevel] = frozenset(
    {CapabilityLevel.ADOPT, CapabilityLevel.ADOPT_DECLARATIVE}
)


def _is_adoption(level: CapabilityLevel) -> bool:
    return level in _ADOPTION_LEVELS


@dataclass(slots=True, frozen=True)
class CapabilityDefinition:
    """Static metadata describing one capability to evaluate.

    The catalogue (see :data:`CAPABILITY_CATALOG`) is intentionally kept
    in code rather than in configuration: the detection rules call
    arbitrary snapshot attributes and have to be coupled to the parser
    schema, so a JSON/YAML representation would not be expressive enough
    without becoming a mini-DSL.
    """

    capability_id: str
    label: str
    weight: int


@dataclass(slots=True)
class CapabilityAssessment:
    """Result of evaluating one capability against the snapshot."""

    capability_id: str
    label: str
    weight: int
    level: CapabilityLevel
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AdoptionStats:
    """Aggregate adoption posture across all evaluated capabilities."""

    assessments: list[CapabilityAssessment] = field(default_factory=list)

    @property
    def total_weight(self) -> int:
        return sum(a.weight for a in self.assessments)

    def _weight_for(self, level: CapabilityLevel) -> int:
        return sum(a.weight for a in self.assessments if a.level is level)

    @property
    def adopt_ootb_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADOPT)

    @property
    def adopt_declarative_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADOPT_DECLARATIVE)

    @property
    def adopt_weight(self) -> int:
        # Aggregate weight of the two "adoption" levels (OOTB + declarative).
        # Existing renderers and tests rely on this name representing the
        # full adoption side of the scale.
        return self.adopt_ootb_weight + self.adopt_declarative_weight

    @property
    def adapt_low_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADAPT_LOW)

    @property
    def adapt_high_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADAPT_HIGH)

    @property
    def adapt_weight(self) -> int:
        return self.adapt_low_weight + self.adapt_high_weight

    def _count_for(self, level: CapabilityLevel) -> int:
        return sum(1 for a in self.assessments if a.level is level)

    @property
    def adopt_ootb_count(self) -> int:
        return self._count_for(CapabilityLevel.ADOPT)

    @property
    def adopt_declarative_count(self) -> int:
        return self._count_for(CapabilityLevel.ADOPT_DECLARATIVE)

    @property
    def adopt_count(self) -> int:
        # Total number of capabilities classified as adoption (OOTB or
        # declarative). Kept for backwards compatibility with the renderers.
        return self.adopt_ootb_count + self.adopt_declarative_count

    @property
    def adapt_low_count(self) -> int:
        return self._count_for(CapabilityLevel.ADAPT_LOW)

    @property
    def adapt_high_count(self) -> int:
        return self._count_for(CapabilityLevel.ADAPT_HIGH)

    @property
    def adapt_count(self) -> int:
        return self.adapt_low_count + self.adapt_high_count

    @property
    def total_count(self) -> int:
        return len(self.assessments)

    @property
    def percent_adoption(self) -> float:
        return (
            self.adopt_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adaptation(self) -> float:
        return 100.0 - self.percent_adoption if self.total_weight else 0.0

    @property
    def percent_adopt_ootb(self) -> float:
        return (
            self.adopt_ootb_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adopt_declarative(self) -> float:
        return (
            self.adopt_declarative_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adapt_low(self) -> float:
        return (
            self.adapt_low_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adapt_high(self) -> float:
        return (
            self.adapt_high_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )


# ---------------------------------------------------------------------------
# Catalogue and detection helpers
# ---------------------------------------------------------------------------


CAPABILITY_CATALOG: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition("data_model", "Modele de donnees", 3),
    CapabilityDefinition("security", "Securite", 3),
    CapabilityDefinition("automation", "Automatisation", 3),
    CapabilityDefinition("validation", "Validation metier", 2),
    CapabilityDefinition("ui_layout", "UI / Layout", 2),
    CapabilityDefinition("integration", "Integration", 2),
    CapabilityDefinition("reporting", "Reporting", 2),
    CapabilityDefinition("notifications", "Notifications & Email", 2),
    CapabilityDefinition("omnistudio", "OmniStudio", 1),
)


# ---------------------------------------------------------------------------
# Posture configuration - lets the user override weights/levels and add
# bespoke capabilities on top of CAPABILITY_CATALOG.
# ---------------------------------------------------------------------------


# Catalogue of metadata counters that can drive a custom user-defined
# capability. The label is what the configuration UI shows; the resolver
# returns the count for a given snapshot (so we can produce evidence
# automatically). Each entry is small and self-contained on purpose so
# callers can iterate the dict without importing other modules.
SNAPSHOT_METRIC_KEYS: dict[str, str] = {
    "custom_objects": "Objets custom",
    "custom_fields": "Champs custom",
    "record_types": "Record types",
    "validation_rules": "Regles de validation",
    "layouts": "Page layouts",
    "custom_tabs": "Onglets custom",
    "custom_apps": "Applications custom",
    "flows": "Flows",
    "apex_classes": "Classes Apex",
    "apex_triggers": "Triggers Apex",
    "omni_scripts": "OmniScripts",
    "omni_integration_procedures": "Integration Procedures Omni",
    "omni_ui_cards": "UI Cards / FlexCards",
    "omni_data_transforms": "Data Transforms Omni",
    "lwc_count": "Composants LWC",
    "flexipage_count": "FlexiPages (pages Lightning)",
}


def snapshot_metric_count(snapshot: MetadataSnapshot, key: str) -> int:
    """Return the integer count stored on ``snapshot.metrics`` for ``key``."""

    metrics = getattr(snapshot, "metrics", None)
    if metrics is None:
        return 0
    value = getattr(metrics, key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass(slots=True)
class PostureCapabilityConfig:
    """User-provided configuration overlay for a posture capability.

    The configuration screen edits a list of these entries: each one
    targets a builtin capability (matching ``CAPABILITY_CATALOG``) or a
    custom user-defined capability (``custom=True``).

    ``level`` controls the override:

    * ``None``  : use the heuristic assessor (only meaningful for builtin
      capabilities since custom ones have no assessor).
    * any :class:`CapabilityLevel` value: force that level regardless of
      the snapshot. The assessor still runs to gather evidence.

    For custom capabilities ``metadata_key`` points at one of
    :data:`SNAPSHOT_METRIC_KEYS`; the count is used to build an evidence
    line so the report stays auditable.
    """

    capability_id: str
    label: str
    weight: int
    level: CapabilityLevel | None = None
    custom: bool = False
    metadata_key: str = ""


# Standard Salesforce profiles that should never count as custom. The
# list covers the ones a typical Sales/Service/Platform retrieve will
# expose; anything outside the set is treated as a custom profile,
# which is a conservative-but-useful heuristic. Comparison is done
# case-insensitively.
_STANDARD_PROFILE_NAMES: frozenset[str] = frozenset(
    name.casefold()
    for name in (
        "Standard User",
        "System Administrator",
        "Read Only",
        "Solution Manager",
        "Marketing User",
        "Contract Manager",
        "Standard Platform User",
        "Force.com - App Subscription User",
        "Force.com - Free User",
        "Authenticated Website",
        "Chatter External User",
        "Chatter Free User",
        "Chatter Moderator User",
        "Cross Org Data Proxy User",
        "Customer Portal Manager Custom",
        "Customer Portal Manager Standard",
        "Customer Community User",
        "Customer Community Plus User",
        "Customer Community Login User",
        "Partner Community User",
        "Partner Community Login User",
        "External Apps Login User",
        "External Apps Plus User",
        "External Identity User",
        "Gold Partner User",
        "Silver Partner User",
        "High Volume Customer Portal",
        "High Volume Customer Portal User",
        "Identity User",
        "Minimum Access - Salesforce",
        "Salesforce API Only System Integrations",
        "Work.com Only User",
        "Analytics Cloud Integration User",
        "Analytics Cloud Security User",
    )
)


_APEX_CALLOUT_PATTERNS = re.compile(
    r"\b(?:HttpRequest\b|new\s+Http\s*\(|@future\s*\(\s*callout\s*=\s*true|"
    r"WebServiceCallout\b|Database\.executeBatch\b|Queueable\b|Crypto\.|"
    r"EncodingUtil\.)",
    re.IGNORECASE,
)

_APEX_VALIDATION_PATTERNS = re.compile(
    r"\.\s*addError\s*\(|SObjectException", re.IGNORECASE
)

_APEX_EMAIL_PATTERNS = re.compile(
    r"Messaging\.\s*(?:SingleEmailMessage|MassEmailMessage|sendEmail)",
    re.IGNORECASE,
)


def _is_custom_profile(profile: SecurityArtifact) -> bool:
    return profile.name.casefold() not in _STANDARD_PROFILE_NAMES


def _has_apex_pattern(
    artifacts: list[ApexArtifact], pattern: re.Pattern[str], *, kinds: set[str] | None = None
) -> tuple[bool, list[str]]:
    """Return ``(found, names)`` for artifacts matching ``pattern``.

    ``names`` lists the matching artifact names (capped at five so the
    UI evidence stays readable). When ``kinds`` is provided, only Apex
    artifacts of the listed kinds (e.g. ``{"trigger"}``) are scanned.
    """

    matches: list[str] = []
    for artifact in artifacts:
        if kinds is not None and artifact.kind not in kinds:
            continue
        if not artifact.body:
            continue
        if pattern.search(artifact.body):
            matches.append(artifact.name)
    return bool(matches), matches[:5]


def _format_evidence(label: str, items: list[str]) -> str:
    if not items:
        return label
    sample = ", ".join(items[:3])
    suffix = "..." if len(items) > 3 else ""
    return f"{label} : {sample}{suffix}"


# ---------------------------------------------------------------------------
# Detection per capability
# ---------------------------------------------------------------------------


def _assess_data_model(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    custom_objects = [obj for obj in snapshot.objects if obj.custom]
    custom_fields_total = sum(
        1 for obj in snapshot.objects for f in obj.fields if f.custom
    )

    evidence: list[str] = []
    if custom_objects:
        evidence.append(
            _format_evidence(
                f"{len(custom_objects)} objet(s) custom", [o.api_name for o in custom_objects]
            )
        )
    if custom_fields_total:
        evidence.append(f"{custom_fields_total} champ(s) custom au total")

    if not custom_objects and custom_fields_total == 0:
        return CapabilityLevel.ADOPT, ["Aucun objet ni champ custom detecte"]
    if len(custom_objects) <= 3:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADAPT_HIGH, evidence


def _assess_security(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    custom_profiles = [p for p in snapshot.profiles if _is_custom_profile(p)]
    permission_sets = snapshot.permission_sets

    evidence: list[str] = []
    if custom_profiles:
        evidence.append(
            _format_evidence(
                f"{len(custom_profiles)} profile(s) custom",
                [p.name for p in custom_profiles],
            )
        )
    if permission_sets:
        evidence.append(
            _format_evidence(
                f"{len(permission_sets)} permission set(s)",
                [p.name for p in permission_sets],
            )
        )

    if custom_profiles:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if permission_sets:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Profils standards uniquement, pas de permission set"]


def _assess_automation(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    triggers = [a for a in snapshot.apex_artifacts if a.kind == "trigger"]
    flows = snapshot.flows

    evidence: list[str] = []
    if flows:
        evidence.append(
            _format_evidence(f"{len(flows)} flow(s)", [f.name for f in flows])
        )
    if triggers:
        evidence.append(
            _format_evidence(
                f"{len(triggers)} trigger(s)", [t.name for t in triggers]
            )
        )

    if triggers:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if flows:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucun flow ni trigger Apex detecte"]


def _assess_validation(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    validation_rules = [
        (obj.api_name, vr.full_name)
        for obj in snapshot.objects
        for vr in obj.validation_rules
    ]
    has_apex_validation, apex_names = _has_apex_pattern(
        snapshot.apex_artifacts, _APEX_VALIDATION_PATTERNS, kinds={"trigger"}
    )

    evidence: list[str] = []
    if validation_rules:
        sample = [f"{a}.{b}" for a, b in validation_rules[:3]]
        suffix = "..." if len(validation_rules) > 3 else ""
        evidence.append(
            f"{len(validation_rules)} validation rule(s) : {', '.join(sample)}{suffix}"
        )
    if has_apex_validation:
        evidence.append(
            _format_evidence(
                f"{len(apex_names)} trigger(s) avec addError", apex_names
            )
        )

    if has_apex_validation:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if validation_rules:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucune validation rule ni trigger de validation"]


def _assess_ui_layout(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    metrics = snapshot.metrics
    flexipages: list[dict[str, Any]] = snapshot.inventory.get("lightning_pages", [])
    layouts: list[dict[str, Any]] = snapshot.inventory.get("layouts", [])

    evidence: list[str] = []
    if metrics.lwc_count:
        evidence.append(f"{metrics.lwc_count} LWC")
    if flexipages:
        names = [str(row.get("Label") or row.get("NomAPI") or "") for row in flexipages]
        evidence.append(_format_evidence(f"{len(flexipages)} FlexiPage(s)", names))
    if layouts:
        evidence.append(f"{len(layouts)} layout(s) deploye(s)")

    if metrics.lwc_count:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if flexipages:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, evidence or ["Layouts standards uniquement"]


def _assess_integration(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    has_callout, names = _has_apex_pattern(
        snapshot.apex_artifacts, _APEX_CALLOUT_PATTERNS
    )
    evidence: list[str] = []
    if has_callout:
        evidence.append(
            _format_evidence(
                f"{len(names)} classe(s)/trigger(s) avec callout ou async",
                names,
            )
        )

    # We currently do not parse Named Credentials / External Services. If a
    # future inventory category is added, the Adapt-Low branch can detect
    # the declarative case (Named Credentials without callout). Until
    # then we only distinguish Adopt vs Adapt-High.
    if has_callout:
        return CapabilityLevel.ADAPT_HIGH, evidence
    return CapabilityLevel.ADOPT, ["Aucun callout Apex detecte"]


def _assess_reporting(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    reports: list[dict[str, Any]] = snapshot.inventory.get("reports", [])
    dashboards: list[dict[str, Any]] = snapshot.inventory.get("dashboards", [])

    evidence: list[str] = []
    if reports:
        evidence.append(f"{len(reports)} report(s) custom")
    if dashboards:
        evidence.append(f"{len(dashboards)} dashboard(s) custom")

    if dashboards:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if reports:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucun report ni dashboard custom"]


def _assess_notifications(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    has_email_apex, names = _has_apex_pattern(
        snapshot.apex_artifacts, _APEX_EMAIL_PATTERNS
    )
    email_alerts: list[dict[str, Any]] = []
    for key in ("email_alerts", "workflow_email_alerts"):
        email_alerts.extend(snapshot.inventory.get(key, []))

    evidence: list[str] = []
    if has_email_apex:
        evidence.append(
            _format_evidence(
                f"{len(names)} classe(s) avec Messaging.sendEmail", names
            )
        )
    if email_alerts:
        evidence.append(f"{len(email_alerts)} email alert(s)/template(s) custom")

    if has_email_apex:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if email_alerts:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucune notification Apex/email alert detectee"]


def _assess_omnistudio(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    metrics = snapshot.metrics
    has_high = metrics.omni_scripts + metrics.omni_integration_procedures > 0
    has_low = metrics.omni_data_transforms + metrics.omni_ui_cards > 0

    evidence: list[str] = []
    if metrics.omni_scripts:
        evidence.append(f"{metrics.omni_scripts} OmniScript(s)")
    if metrics.omni_integration_procedures:
        evidence.append(
            f"{metrics.omni_integration_procedures} Integration Procedure(s)"
        )
    if metrics.omni_ui_cards:
        evidence.append(f"{metrics.omni_ui_cards} UI Card(s)")
    if metrics.omni_data_transforms:
        evidence.append(f"{metrics.omni_data_transforms} DataRaptor(s)/Transform(s)")

    if has_high:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if has_low:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Pas de composant OmniStudio detecte"]


_ASSESSORS = {
    "data_model": _assess_data_model,
    "security": _assess_security,
    "automation": _assess_automation,
    "validation": _assess_validation,
    "ui_layout": _assess_ui_layout,
    "integration": _assess_integration,
    "reporting": _assess_reporting,
    "notifications": _assess_notifications,
    "omnistudio": _assess_omnistudio,
}


def _evaluate_builtin(
    definition: CapabilityDefinition,
    snapshot: MetadataSnapshot,
    override: PostureCapabilityConfig | None,
) -> CapabilityAssessment | None:
    """Build the assessment for a builtin capability, applying overrides."""

    assessor = _ASSESSORS.get(definition.capability_id)
    detected_level: CapabilityLevel
    evidence: list[str]
    if assessor is None:
        detected_level = CapabilityLevel.ADOPT
        evidence = []
    else:
        detected_level, evidence = assessor(snapshot)

    weight = definition.weight
    level = detected_level
    if override is not None:
        weight = override.weight if override.weight > 0 else weight
        if override.level is not None:
            level = override.level
            if level is not detected_level:
                evidence = [
                    f"Niveau force par configuration ({level.value})",
                    *evidence,
                ]
    label = override.label if override is not None and override.label else definition.label
    return CapabilityAssessment(
        capability_id=definition.capability_id,
        label=label,
        weight=weight,
        level=level,
        evidence=evidence,
    )


def _evaluate_custom(
    config: PostureCapabilityConfig,
    snapshot: MetadataSnapshot,
) -> CapabilityAssessment:
    """Build the assessment for a user-defined capability."""

    level = config.level or CapabilityLevel.ADOPT
    evidence: list[str] = []
    if config.metadata_key:
        count = snapshot_metric_count(snapshot, config.metadata_key)
        label = SNAPSHOT_METRIC_KEYS.get(config.metadata_key, config.metadata_key)
        evidence.append(f"{label} : {count}")
    evidence.append(f"Capacite definie par l'utilisateur ({level.value})")
    return CapabilityAssessment(
        capability_id=config.capability_id,
        label=config.label or config.capability_id,
        weight=max(config.weight, 0),
        level=level,
        evidence=evidence,
    )


def compute_adoption_stats(
    snapshot: MetadataSnapshot,
    posture_config: list[PostureCapabilityConfig] | None = None,
) -> AdoptionStats:
    """Run each capability assessor against ``snapshot`` and return the stats.

    When ``posture_config`` is provided the iteration order, weights,
    levels and label of each capability come from the configuration. New
    user-defined capabilities (``custom=True``) are evaluated from a
    metadata counter so they can contribute to the percentage even though
    no heuristic assessor exists for them.
    """

    stats = AdoptionStats()

    if not posture_config:
        for definition in CAPABILITY_CATALOG:
            assessment = _evaluate_builtin(definition, snapshot, None)
            if assessment is not None:
                stats.assessments.append(assessment)
        return stats

    builtin_by_id = {d.capability_id: d for d in CAPABILITY_CATALOG}
    seen_ids: set[str] = set()
    for entry in posture_config:
        if entry.capability_id in seen_ids:
            continue
        seen_ids.add(entry.capability_id)
        if entry.custom:
            stats.assessments.append(_evaluate_custom(entry, snapshot))
            continue
        definition = builtin_by_id.get(entry.capability_id)
        if definition is None:
            # Stale config pointing at a removed builtin: skip silently
            # rather than break the report.
            continue
        assessment = _evaluate_builtin(definition, snapshot, entry)
        if assessment is not None:
            stats.assessments.append(assessment)

    # Append any builtin capability the configuration does not mention so
    # the catalogue stays exhaustive even after an upgrade introduces new
    # default capabilities.
    for definition in CAPABILITY_CATALOG:
        if definition.capability_id in seen_ids:
            continue
        assessment = _evaluate_builtin(definition, snapshot, None)
        if assessment is not None:
            stats.assessments.append(assessment)
    return stats


__all__ = [
    "AdoptionStats",
    "CAPABILITY_CATALOG",
    "CAPABILITY_LEVEL_ORDER",
    "CapabilityAssessment",
    "CapabilityDefinition",
    "CapabilityLevel",
    "DataModelCustomisationStats",
    "PostureCapabilityConfig",
    "SNAPSHOT_METRIC_KEYS",
    "compute_adoption_stats",
    "compute_data_model_stats",
    "snapshot_metric_count",
]
