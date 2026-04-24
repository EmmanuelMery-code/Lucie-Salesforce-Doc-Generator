from __future__ import annotations

import re

from src.analyzer.apex_analyzer import (
    _strip_comments_and_strings,
    analyze_apex_artifact,
)
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


IDENTIFIER_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")


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

        for name, extra in _detect_apex_call_cycles(
            snapshot.apex_artifacts, self.catalog
        ).items():
            apex_findings.setdefault(name, []).extend(extra)
            apex_findings[name] = _sorted(apex_findings[name])

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


# ---------------------------------------------------------------------------- call-graph / cycles


def _detect_apex_call_cycles(
    artifacts: list[ApexArtifact], catalog: RuleCatalog
) -> dict[str, list[Finding]]:
    """Detecte les cycles d'appels entre classes Apex (APEX-REL-003).

    La detection construit un graphe d'appels (ClassName -> {ClassName appelee}) base sur
    les identifiants en PascalCase mentionnes dans le code (apres retrait des commentaires
    et chaines litterales) puis applique l'algorithme de Tarjan pour extraire les SCCs.
    Les composantes de taille >= 2, ou les auto-boucles, remontent comme findings.
    """
    rule = catalog.get("APEX-REL-003")
    if not rule or not rule.enabled:
        return {}

    classes = [a for a in artifacts if a.kind == "class"]
    class_names = {a.name for a in classes}
    if len(class_names) < 2:
        return {}

    graph: dict[str, set[str]] = {name: set() for name in class_names}
    for artifact in classes:
        stripped = _strip_comments_and_strings(artifact.body)
        mentioned = {m for m in IDENTIFIER_RE.findall(stripped) if m in class_names}
        mentioned.discard(artifact.name)
        graph[artifact.name] = mentioned

    cycles = _find_cycles(graph)
    if not cycles:
        return {}

    findings_by_class: dict[str, list[Finding]] = {}
    for cycle in cycles:
        cycle_sorted = sorted(cycle)
        cycle_label = " -> ".join(cycle_sorted + [cycle_sorted[0]])
        details = [
            f"Classes participant au cycle : {', '.join(cycle_sorted)}.",
            f"Chaine simplifiee : {cycle_label}.",
        ]
        for cls in cycle_sorted:
            artifact = next((a for a in classes if a.name == cls), None)
            others = [c for c in cycle_sorted if c != cls]
            message = (
                "Classe impliquee dans un cycle d'appels avec "
                + (", ".join(others) if others else "elle-meme")
                + "."
            )
            finding = Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=cls,
                message=message,
                details=list(details),
                source_path=artifact.source_path if artifact else None,
            )
            findings_by_class.setdefault(cls, []).append(finding)
    return findings_by_class


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Retourne les composantes fortement connexes >= 2 noeuds (ou auto-boucles) via Tarjan."""
    index_counter = [0]
    stack: list[str] = []
    on_stack: dict[str, bool] = {}
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        for neighbour in graph.get(node, set()):
            if neighbour not in graph:
                continue
            if neighbour not in index:
                strongconnect(neighbour)
                lowlink[node] = min(lowlink[node], lowlink[neighbour])
            elif on_stack.get(neighbour):
                lowlink[node] = min(lowlink[node], index[neighbour])

        if lowlink[node] == index[node]:
            component: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == node:
                    break
            if len(component) >= 2:
                sccs.append(component)
            elif node in graph.get(node, set()):
                sccs.append(component)

    for node in list(graph.keys()):
        if node not in index:
            strongconnect(node)
    return sccs
