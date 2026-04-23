from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FieldInfo:
    api_name: str
    label: str = ""
    data_type: str = ""
    description: str = ""
    required: bool = False
    custom: bool = False
    reference_to: list[str] = field(default_factory=list)
    relationship_name: str = ""


@dataclass(slots=True)
class RecordTypeInfo:
    full_name: str
    label: str = ""
    description: str = ""
    active: bool = False


@dataclass(slots=True)
class ValidationRuleInfo:
    full_name: str
    active: bool = False
    description: str = ""
    error_display_field: str = ""


@dataclass(slots=True)
class RelationshipInfo:
    field_name: str
    relationship_type: str
    targets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ObjectInfo:
    api_name: str
    label: str = ""
    plural_label: str = ""
    description: str = ""
    deployment_status: str = ""
    sharing_model: str = ""
    visibility: str = ""
    custom: bool = False
    fields: list[FieldInfo] = field(default_factory=list)
    record_types: list[RecordTypeInfo] = field(default_factory=list)
    validation_rules: list[ValidationRuleInfo] = field(default_factory=list)
    relationships: list[RelationshipInfo] = field(default_factory=list)
    source_path: Path | None = None


@dataclass(slots=True)
class ObjectPermission:
    object_name: str
    allow_read: bool = False
    allow_create: bool = False
    allow_edit: bool = False
    allow_delete: bool = False
    view_all_records: bool = False
    modify_all_records: bool = False


@dataclass(slots=True)
class FieldPermission:
    field_name: str
    readable: bool = False
    editable: bool = False


@dataclass(slots=True)
class UserPermission:
    name: str
    enabled: bool = False


@dataclass(slots=True)
class VisibilityItem:
    name: str
    visible: str = ""
    default: str = ""


@dataclass(slots=True)
class NamedAccess:
    name: str
    enabled: bool = False


@dataclass(slots=True)
class RecordTypeVisibility:
    record_type: str
    visible: bool = False
    default: bool = False


@dataclass(slots=True)
class SecurityArtifact:
    name: str
    kind: str
    label: str = ""
    description: str = ""
    source_path: Path | None = None
    object_permissions: list[ObjectPermission] = field(default_factory=list)
    field_permissions: list[FieldPermission] = field(default_factory=list)
    user_permissions: list[UserPermission] = field(default_factory=list)
    application_visibilities: list[VisibilityItem] = field(default_factory=list)
    tab_visibilities: list[VisibilityItem] = field(default_factory=list)
    class_accesses: list[NamedAccess] = field(default_factory=list)
    flow_accesses: list[NamedAccess] = field(default_factory=list)
    page_accesses: list[NamedAccess] = field(default_factory=list)
    custom_permissions: list[NamedAccess] = field(default_factory=list)
    record_type_visibilities: list[RecordTypeVisibility] = field(default_factory=list)


@dataclass(slots=True)
class ApexArtifact:
    name: str
    kind: str
    body: str
    source_path: Path
    api_version: str = ""
    status: str = ""
    line_count: int = 0
    method_count: int = 0
    soql_count: int = 0
    sosl_count: int = 0
    dml_count: int = 0
    comment_line_count: int = 0
    system_debug_count: int = 0
    has_try_catch: bool = False
    sharing_declaration: str = ""
    is_test: bool = False
    query_in_loop: bool = False
    dml_in_loop: bool = False


@dataclass(slots=True)
class FlowElementInfo:
    element_type: str
    name: str
    label: str = ""
    description: str = ""
    target: str = ""


@dataclass(slots=True)
class FlowInfo:
    name: str
    label: str = ""
    description: str = ""
    process_type: str = ""
    status: str = ""
    api_version: str = ""
    trigger_type: str = ""
    start_object: str = ""
    source_path: Path | None = None
    element_counts: dict[str, int] = field(default_factory=dict)
    described_elements: int = 0
    undocumented_elements: int = 0
    total_elements: int = 0
    variable_total: int = 0
    variable_input: int = 0
    variable_output: int = 0
    max_width: int = 1
    min_height: int = 0
    max_height: int = 0
    max_depth: int = 0
    elements: list[FlowElementInfo] = field(default_factory=list)

    @property
    def complexity_score(self) -> int:
        decision_count = self.element_counts.get("decisions", 0)
        loop_count = self.element_counts.get("loops", 0)
        subflow_count = self.element_counts.get("subflows", 0)
        data_ops = sum(
            self.element_counts.get(name, 0)
            for name in ("recordCreates", "recordUpdates", "recordDeletes", "recordLookups")
        )
        return (
            self.total_elements
            + decision_count * 3
            + loop_count * 4
            + subflow_count * 2
            + data_ops * 2
            + self.max_depth * 4
            + max(0, self.max_width - 1) * 2
            + self.undocumented_elements
        )

    @property
    def complexity_level(self) -> str:
        score = self.complexity_score
        if score < 20:
            return "Simple"
        if score < 45:
            return "Moyen"
        if score < 80:
            return "Complexe"
        return "Tres complexe"


@dataclass(slots=True)
class ReviewResult:
    summary: str
    positives: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    metrics: list[tuple[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class PmdViolation:
    file_path: Path
    rule: str
    ruleset: str = ""
    priority: str = ""
    begin_line: int = 0
    end_line: int = 0
    message: str = ""


DEFAULT_SCORING_WEIGHTS: dict[str, int] = {
    "custom_objects": 8,
    "custom_fields": 1,
    "record_types": 2,
    "validation_rules": 2,
    "layouts": 1,
    "custom_tabs": 3,
    "custom_apps": 4,
    "flows": 3,
    "apex_classes": 3,
    "apex_triggers": 3,
    "omni_scripts": 4,
    "omni_integration_procedures": 4,
    "omni_ui_cards": 3,
    "omni_data_transforms": 2,
}


@dataclass(slots=True)
class CustomizationMetrics:
    custom_objects: int = 0
    custom_fields: int = 0
    record_types: int = 0
    validation_rules: int = 0
    layouts: int = 0
    custom_tabs: int = 0
    custom_apps: int = 0
    flows: int = 0
    apex_classes: int = 0
    apex_triggers: int = 0
    omni_scripts: int = 0
    omni_integration_procedures: int = 0
    omni_ui_cards: int = 0
    omni_data_transforms: int = 0
    weights: dict[str, int] | None = None

    def _weight(self, key: str) -> int:
        if self.weights is not None:
            value = self.weights.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                return int(value.strip())
        return DEFAULT_SCORING_WEIGHTS[key]

    @property
    def score(self) -> int:
        return (
            self.custom_objects * self._weight("custom_objects")
            + self.custom_fields * self._weight("custom_fields")
            + self.record_types * self._weight("record_types")
            + self.validation_rules * self._weight("validation_rules")
            + self.layouts * self._weight("layouts")
            + self.custom_tabs * self._weight("custom_tabs")
            + self.custom_apps * self._weight("custom_apps")
            + self.flows * self._weight("flows")
            + self.apex_classes * self._weight("apex_classes")
            + self.apex_triggers * self._weight("apex_triggers")
            + self.omni_scripts * self._weight("omni_scripts")
            + self.omni_integration_procedures * self._weight("omni_integration_procedures")
            + self.omni_ui_cards * self._weight("omni_ui_cards")
            + self.omni_data_transforms * self._weight("omni_data_transforms")
        )

    @property
    def level(self) -> str:
        if self.score < 50:
            return "Faible"
        if self.score < 150:
            return "Moyen"
        if self.score < 350:
            return "Eleve"
        return "Tres eleve"


@dataclass(slots=True)
class MetadataSnapshot:
    source_dir: Path
    package_roots: list[Path]
    objects: list[ObjectInfo] = field(default_factory=list)
    profiles: list[SecurityArtifact] = field(default_factory=list)
    permission_sets: list[SecurityArtifact] = field(default_factory=list)
    apex_artifacts: list[ApexArtifact] = field(default_factory=list)
    flows: list[FlowInfo] = field(default_factory=list)
    metrics: CustomizationMetrics = field(default_factory=CustomizationMetrics)
    inventory: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
