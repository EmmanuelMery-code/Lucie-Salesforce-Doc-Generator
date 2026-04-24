from __future__ import annotations

import re

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ApexArtifact


SALESFORCE_ID_RE = re.compile(r"['\"]([0-9a-zA-Z]{15}|[0-9a-zA-Z]{18})['\"]")
RESERVED_METHOD_NAMES = {
    "if", "for", "while", "do", "switch", "return", "new", "throw",
    "catch", "try", "else", "super", "this",
}
RECURSION_GUARD_HINTS = (
    "static",
    "set<id>",
    "set<string>",
    "recursionguard",
    "alreadyprocessed",
    "bypass",
    "recursion",
    "isfirstrun",
)
TRIGGER_DECLARATION_RE = re.compile(
    r"(?is)\btrigger\s+\w+\s+on\s+\w+\s*\(([^)]+)\)\s*\{"
)
TRIGGER_AFTER_EVENT_RE = re.compile(
    r"(?i)\bafter\s+(?:insert|update|undelete)\b"
)
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

    # APEX-REL-002 : method self-recursion without visible guard
    rule = catalog.get("APEX-REL-002")
    if rule and rule.enabled and not artifact.is_test:
        recursive_methods = _detect_self_recursive_methods(artifact.body)
        if recursive_methods:
            sample = ", ".join(sorted(recursive_methods)[:5])
            details = [f"Methode(s) concernee(s) : {sample}."]
            if len(recursive_methods) > 5:
                details.append(
                    f"+ {len(recursive_methods) - 5} autre(s) methode(s) avec auto-appel."
                )
            details.append(
                "Aucune garde de reentrance evidente (Set<Id>/flag static) detectee dans la classe."
            )
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=(
                        f"{len(recursive_methods)} methode(s) s'invoquent elles-memes "
                        "sans mecanisme visible de garde d'arret."
                    ),
                    details=details,
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

    # TRIG-REL-001 : after insert/update trigger rewriting Trigger.new (recursion risk)
    rule = catalog.get("TRIG-REL-001")
    if rule and rule.enabled:
        detection = _detect_trigger_after_save_recursion(artifact.body)
        if detection is not None:
            events, dml_sample = detection
            details = [
                "Evenements declares : " + ", ".join(sorted(events)) + ".",
                "Operation detectee : " + dml_sample + ".",
                "Aucune garde de reentrance (Set<Id> static / classe TriggerHandler) trouvee dans le trigger.",
            ]
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexTrigger",
                    target_name=artifact.name,
                    message=(
                        "Le trigger modifie ses propres enregistrements declencheurs "
                        "dans un contexte after-save : risque de boucle infinie."
                    ),
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


def _strip_comments_and_strings(body: str) -> str:
    """Supprime les commentaires // et /* */ ainsi que les chaines litterales, en conservant les positions (remplacees par des espaces)."""
    out = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        nxt = body[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and body[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "/" and nxt == "*":
            out.append("  ")
            i += 2
            while i < n and not (body[i] == "*" and i + 1 < n and body[i + 1] == "/"):
                out.append(" " if body[i] != "\n" else "\n")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
        elif ch in ('"', "'"):
            quote = ch
            out.append(" ")
            i += 1
            while i < n and body[i] != quote:
                if body[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append(" " if body[i] != "\n" else "\n")
                    i += 1
            if i < n:
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


METHOD_HEADER_RE = re.compile(
    r"(?m)"
    r"^[ \t]*"
    r"(?:(?:public|private|protected|global)\s+)?"
    r"(?:(?:static|virtual|abstract|override|webservice|final|transient)\s+)*"
    r"(?:[\w<>\[\],\. ]+?)\s+"
    r"(\w+)\s*\([^;{}]*?\)\s*"
    r"\{"
)


def _extract_method_bodies(clean_body: str) -> list[tuple[str, str]]:
    """Retourne [(nom_methode, corps_complet)] en parcourant le code (commentaires deja retires)."""
    results: list[tuple[str, str]] = []
    for match in METHOD_HEADER_RE.finditer(clean_body):
        name = match.group(1)
        if name.lower() in RESERVED_METHOD_NAMES:
            continue
        brace_start = match.end() - 1
        depth = 0
        idx = brace_start
        end = brace_start
        while idx < len(clean_body):
            ch = clean_body[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break
            idx += 1
        if end > brace_start:
            results.append((name, clean_body[brace_start:end]))
    return results


def _detect_self_recursive_methods(body: str) -> list[str]:
    """Retourne la liste des noms de methodes qui s'invoquent elles-memes depuis leur propre corps.

    La detection est volontairement conservatrice :
      - on ne reporte que si aucune garde de reentrance evidente n'apparait dans la classe ;
      - on ignore les methodes dont le nom est un mot reserve / courant.
    """
    clean = _strip_comments_and_strings(body)
    lowered = clean.lower()
    if any(hint in lowered for hint in RECURSION_GUARD_HINTS):
        return []

    recursive: set[str] = set()
    for name, method_body in _extract_method_bodies(clean):
        if len(name) < 3:
            continue
        call_re = re.compile(rf"\b{re.escape(name)}\s*\(")
        if call_re.search(method_body):
            recursive.add(name)
    return sorted(recursive)


def _detect_trigger_after_save_recursion(body: str) -> tuple[set[str], str] | None:
    """Detecte un trigger after-save qui modifie ses propres enregistrements declencheurs.

    Retourne :
      - None si le pattern n'est pas detecte ;
      - (events, dml_sample) si le risque existe, ou events est l'ensemble "after insert/update/undelete"
        declare et dml_sample est l'extrait textuel du DML incrimine.
    """
    clean = _strip_comments_and_strings(body)

    header = TRIGGER_DECLARATION_RE.search(clean)
    if not header:
        return None
    events_raw = header.group(1)
    after_events = {
        f"after {m.group(0).split()[-1].lower()}"
        for m in TRIGGER_AFTER_EVENT_RE.finditer(events_raw)
    }
    if not after_events:
        return None

    if any(hint in clean.lower() for hint in RECURSION_GUARD_HINTS):
        return None

    direct_dml_re = re.compile(
        r"(?i)\b(?:insert|update|upsert|delete|undelete)\s+Trigger\s*\.\s*(?:new|newMap)\b"
    )
    direct_dml_values_re = re.compile(
        r"(?i)\b(?:insert|update|upsert|delete|undelete)\s+Trigger\s*\.\s*newMap\s*\.\s*values\s*\(\s*\)"
    )
    database_dml_re = re.compile(
        r"(?i)\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete)\s*\(\s*"
        r"Trigger\s*\.\s*(?:new|newMap\s*\.\s*values\s*\(\s*\))"
    )
    for pat in (direct_dml_values_re, direct_dml_re, database_dml_re):
        match = pat.search(clean)
        if match:
            return after_events, _shorten(match.group(0))

    assign_re = re.compile(
        r"(?i)\b([A-Za-z_]\w*)\s*=\s*Trigger\s*\.\s*(?:new|newMap\s*\.\s*values\s*\(\s*\))"
    )
    aliases = {m.group(1) for m in assign_re.finditer(clean)}
    for alias in aliases:
        alias_direct = re.compile(
            rf"(?i)\b(?:insert|update|upsert|delete|undelete)\s+{re.escape(alias)}\b"
        )
        alias_db = re.compile(
            rf"(?i)\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete)\s*\(\s*{re.escape(alias)}\b"
        )
        for pat in (alias_direct, alias_db):
            match = pat.search(clean)
            if match:
                return after_events, _shorten(match.group(0))
    return None


def _shorten(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "..."
