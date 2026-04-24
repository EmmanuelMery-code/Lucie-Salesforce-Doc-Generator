from __future__ import annotations

import re

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ApexArtifact


SALESFORCE_ID_RE = re.compile(r"['\"]([0-9a-zA-Z]{15}|[0-9a-zA-Z]{18})['\"]")
PROD_ID_PREFIXES = {
    "001",
    "003",
    "005",
    "006",
    "00D",
    "00E",
    "00Q",
    "00T",
    "00U",
    "500",
    "800",
    "701",
    "801",
    "a0",
    "a1",
    "a2",
    "a3",
    "a4",
    "a5",
    "a6",
    "a7",
    "a8",
    "a9",
}


def analyze_apex_artifact(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    if artifact.kind == "trigger":
        return _analyze_trigger(artifact, catalog)
    return _analyze_class(artifact, catalog)


# ------------------------------------------------------------------ classes


def _analyze_class(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # APEX-SEC-001 : sharing declaration
    if not artifact.is_test:
        rule = catalog.get("APEX-SEC-001")
        if rule and rule.enabled and not artifact.sharing_declaration:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message="Aucune declaration 'with sharing' / 'without sharing' / 'inherited sharing' detectee.",
                    details=[
                        "Par defaut la classe herite du contexte appelant, ce qui peut contourner les partages.",
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-SEC-002 : hardcoded Id
    rule = catalog.get("APEX-SEC-002")
    if rule and rule.enabled:
        hardcoded = _find_hardcoded_ids(artifact.body)
        if hardcoded:
            sample = ", ".join(sorted(hardcoded)[:5])
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=f"{len(hardcoded)} identifiant(s) Salesforce ecrit(s) en dur detecte(s).",
                    details=[f"Exemples: {sample}"],
                    source_path=artifact.source_path,
                )
            )

    # APEX-REL-001 : try/catch around DML/SOQL
    rule = catalog.get("APEX-REL-001")
    if rule and rule.enabled and not artifact.is_test:
        if (artifact.dml_count > 0 or artifact.soql_count > 0) and not artifact.has_try_catch:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message="Acces aux donnees sans gestion d'exception (aucun bloc try/catch).",
                    details=[
                        f"SOQL = {artifact.soql_count}, DML = {artifact.dml_count}.",
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-PERF-001 : SOQL in loop
    rule = catalog.get("APEX-PERF-001")
    if rule and rule.enabled and artifact.query_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message="Une requete SOQL apparait potentiellement dans une boucle.",
                source_path=artifact.source_path,
            )
        )

    # APEX-PERF-002 : DML in loop
    rule = catalog.get("APEX-PERF-002")
    if rule and rule.enabled and artifact.dml_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message="Un DML apparait potentiellement dans une boucle.",
                source_path=artifact.source_path,
            )
        )

    # APEX-MAINT-001 : class length
    rule = catalog.get("APEX-MAINT-001")
    if rule and rule.enabled and artifact.line_count > 500:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=f"Classe de {artifact.line_count} lignes (seuil recommande : 500).",
                source_path=artifact.source_path,
            )
        )

    # APEX-MAINT-002 : comment density
    rule = catalog.get("APEX-MAINT-002")
    if rule and rule.enabled and artifact.line_count > 80:
        ratio = artifact.comment_line_count / max(1, artifact.line_count)
        if ratio < 0.05:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=f"Densite de commentaires = {ratio:.1%} (recommande >= 5%).",
                    details=[
                        f"{artifact.comment_line_count} lignes commentees sur {artifact.line_count}."
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-MAINT-003 : too many System.debug
    rule = catalog.get("APEX-MAINT-003")
    if rule and rule.enabled and artifact.system_debug_count > 10:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=f"{artifact.system_debug_count} appels 'System.debug' presents dans la classe.",
                source_path=artifact.source_path,
            )
        )

    return findings


# ------------------------------------------------------------------ triggers


def _analyze_trigger(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # TRIG-MAINT-001 : business logic in trigger
    rule = catalog.get("TRIG-MAINT-001")
    if rule and rule.enabled:
        code_lines = _count_code_lines(artifact.body)
        has_dml_or_soql = artifact.dml_count > 0 or artifact.soql_count > 0
        if code_lines > 10 or has_dml_or_soql:
            details = [f"Lignes de code detectees : {code_lines}."]
            if has_dml_or_soql:
                details.append(f"SOQL = {artifact.soql_count}, DML = {artifact.dml_count}.")
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexTrigger",
                    target_name=artifact.name,
                    message="Le trigger porte de la logique metier (code substantiel ou operations de donnees).",
                    details=details,
                    source_path=artifact.source_path,
                )
            )

    # TRIG-PERF-001 : SOQL or DML in loop
    rule = catalog.get("TRIG-PERF-001")
    if rule and rule.enabled and (artifact.query_in_loop or artifact.dml_in_loop):
        parts = []
        if artifact.query_in_loop:
            parts.append("SOQL dans une boucle")
        if artifact.dml_in_loop:
            parts.append("DML dans une boucle")
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexTrigger",
                target_name=artifact.name,
                message="Operations de donnees potentiellement dans une boucle : " + ", ".join(parts) + ".",
                source_path=artifact.source_path,
            )
        )

    return findings


# ------------------------------------------------------------------ helpers


def _find_hardcoded_ids(body: str) -> set[str]:
    found: set[str] = set()
    for match in SALESFORCE_ID_RE.finditer(body):
        raw = match.group(1)
        prefix = raw[:3]
        if prefix in PROD_ID_PREFIXES:
            found.add(raw)
        elif prefix[:2] in {p for p in PROD_ID_PREFIXES if len(p) == 2}:
            found.add(raw)
    return found


def _count_code_lines(body: str) -> int:
    count = 0
    in_block_comment = False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped[2:]:
                in_block_comment = True
            continue
        if stripped.startswith("//"):
            continue
        count += 1
    return count
