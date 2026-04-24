from __future__ import annotations

from src.analyzer.apex_analyzer import analyze_apex_artifact
from src.analyzer.flow_analyzer import analyze_flow
from src.analyzer.models import Finding, SEVERITY_ORDER
from src.analyzer.object_analyzer import analyze_object, analyze_validation_rule
from src.analyzer.omni_analyzer import analyze_data_transform
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import (
    ApexArtifact,
    FlowInfo,
    MetadataSnapshot,
    ObjectInfo,
    ValidationRuleInfo,
)


class AnalyzerEngine:
    """Orchestrateur de l'analyse statique ; retourne un ensemble de findings par artefact."""

    def __init__(self, catalog: RuleCatalog | None = None) -> None:
        self.catalog = catalog or RuleCatalog.load()

    # ------------------------------------------------------------------ per-artifact API

    def analyze_apex(self, artifact: ApexArtifact) -> list[Finding]:
        return _sorted(analyze_apex_artifact(artifact, self.catalog))

    def analyze_flow(self, flow: FlowInfo) -> list[Finding]:
        return _sorted(analyze_flow(flow, self.catalog))

    def analyze_object(self, obj: ObjectInfo) -> list[Finding]:
        return _sorted(analyze_object(obj, self.catalog))

    def analyze_validation_rule(
        self, vr: ValidationRuleInfo, object_name: str
    ) -> list[Finding]:
        return _sorted(analyze_validation_rule(vr, object_name, self.catalog))

    def analyze_data_transform(
        self, name: str, xml_content: str
    ) -> list[Finding]:
        return _sorted(analyze_data_transform(name, xml_content, self.catalog))

    # ------------------------------------------------------------------ snapshot-level API

    def analyze_snapshot(self, snapshot: MetadataSnapshot) -> "AnalyzerReport":
        apex_findings: dict[str, list[Finding]] = {}
        for artifact in snapshot.apex_artifacts:
            apex_findings[artifact.name] = self.analyze_apex(artifact)

        flow_findings: dict[str, list[Finding]] = {}
        for flow in snapshot.flows:
            flow_findings[flow.name] = self.analyze_flow(flow)

        object_findings: dict[str, list[Finding]] = {}
        validation_findings: dict[str, list[Finding]] = {}
        for obj in snapshot.objects:
            findings = self.analyze_object(obj)
            object_findings[obj.api_name] = findings
            for vr in obj.validation_rules:
                vr_key = f"{obj.api_name}.{vr.full_name}"
                validation_findings[vr_key] = self.analyze_validation_rule(vr, obj.api_name)

        omni_findings: dict[str, list[Finding]] = {}
        for row in snapshot.inventory.get("omnistudio", []):
            source = str(row.get("Source") or "")
            folder = str(row.get("Dossier") or "").lower()
            file_type = str(row.get("TypeFichier") or "").lower()
            is_dt = (
                "omnidatatransform" in folder
                or file_type.endswith(".rpt-meta.xml")
            )
            if not (is_dt and source):
                continue
            candidate = snapshot.source_dir / source
            if not candidate.exists() or not candidate.is_file():
                continue
            try:
                xml_text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            name = str(row.get("Nom") or candidate.stem)
            omni_findings[name] = self.analyze_data_transform(name, xml_text)

        return AnalyzerReport(
            apex=apex_findings,
            flows=flow_findings,
            objects=object_findings,
            validation_rules=validation_findings,
            data_transforms=omni_findings,
            rules_used=self.catalog.enabled,
        )


class AnalyzerReport:
    """Agrege les findings par type d'artefact et fournit des helpers de synthese."""

    def __init__(
        self,
        apex: dict[str, list[Finding]] | None = None,
        flows: dict[str, list[Finding]] | None = None,
        objects: dict[str, list[Finding]] | None = None,
        validation_rules: dict[str, list[Finding]] | None = None,
        data_transforms: dict[str, list[Finding]] | None = None,
        rules_used: list | None = None,
    ) -> None:
        self.apex = apex or {}
        self.flows = flows or {}
        self.objects = objects or {}
        self.validation_rules = validation_rules or {}
        self.data_transforms = data_transforms or {}
        self.rules_used = rules_used or []

    def all_findings(self) -> list[Finding]:
        collected: list[Finding] = []
        for group in (
            self.apex,
            self.flows,
            self.objects,
            self.validation_rules,
            self.data_transforms,
        ):
            for findings in group.values():
                collected.extend(findings)
        return collected

    def severity_counts(self) -> dict[str, int]:
        counts = {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
        for finding in self.all_findings():
            key = finding.rule.severity
            counts[key] = counts.get(key, 0) + 1
        return counts

    def rule_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.all_findings():
            counts[finding.rule.id] = counts.get(finding.rule.id, 0) + 1
        return counts

    def category_counts(self) -> dict[str, int]:
        counts = {"Trusted": 0, "Easy": 0, "Adaptable": 0}
        for finding in self.all_findings():
            counts[finding.rule.category] = counts.get(finding.rule.category, 0) + 1
        return counts


# ---------------------------------------------------------------------------- helpers


def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.rule.severity, 99), f.rule.id))
