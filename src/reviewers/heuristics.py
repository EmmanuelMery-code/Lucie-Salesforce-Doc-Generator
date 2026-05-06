from __future__ import annotations

from src.core.models import ApexArtifact, FlowInfo, ReviewResult


def review_apex_artifact(artifact: ApexArtifact) -> ReviewResult:
    positives: list[str] = []
    improvements: list[str] = []
    metrics = [
        ("Type", artifact.kind),
        ("Lignes", str(artifact.line_count)),
        ("Methodes", str(artifact.method_count)),
        ("SOQL", str(artifact.soql_count)),
        ("SOSL", str(artifact.sosl_count)),
        ("DML", str(artifact.dml_count)),
        ("Status", artifact.status or "Non renseigne"),
    ]

    if artifact.sharing_declaration:
        positives.append(f"Declaration de partage explicite detectee: {artifact.sharing_declaration}.")
    elif not artifact.is_test:
        improvements.append("Aucune declaration de partage explicite detectee.")

    if artifact.comment_line_count >= max(3, artifact.line_count // 20):
        positives.append("Le code contient un niveau de commentaire utile pour la comprehension.")
    else:
        improvements.append("Le niveau de commentaire est faible pour une lecture rapide.")

    if artifact.has_try_catch:
        positives.append("Une gestion d'exception est presente.")
    elif artifact.dml_count or artifact.soql_count:
        improvements.append("Ajouter une gestion d'exception autour des traitements critiques renforcerait la robustesse.")

    if not artifact.query_in_loop:
        positives.append("Aucun SOQL dans une boucle n'a ete detecte par l'analyse heuristique.")
    else:
        improvements.append("SOQL potentiellement execute dans une boucle.")

    if not artifact.dml_in_loop:
        positives.append("Aucun DML dans une boucle n'a ete detecte par l'analyse heuristique.")
    else:
        improvements.append("DML potentiellement execute dans une boucle.")

    if artifact.line_count > 400:
        improvements.append("La taille du composant est elevee; une decomposition en services ou helpers serait a envisager.")
    elif artifact.line_count < 200:
        positives.append("La taille du composant reste raisonnable.")

    if artifact.system_debug_count > 8:
        improvements.append("Le nombre de `System.debug` est important; nettoyer les traces non essentielles.")

    if artifact.is_test:
        positives.append("Le composant semble etre un artefact de test.")

    summary = (
        "Analyse heuristique statique du composant Apex."
        if artifact.kind == "class"
        else "Analyse heuristique statique du trigger."
    )
    return ReviewResult(summary=summary, positives=positives, improvements=improvements, metrics=metrics)


def review_flow(flow: FlowInfo) -> ReviewResult:
    positives: list[str] = []
    improvements: list[str] = []
    described_ratio = 0.0 if flow.total_elements == 0 else flow.described_elements / flow.total_elements
    data_operations = sum(
        flow.element_counts.get(name, 0)
        for name in ("recordCreates", "recordUpdates", "recordDeletes", "recordLookups")
    )
    metrics = [
        ("Type", flow.process_type or "Non renseigne"),
        ("Complexite", flow.complexity_level),
        ("Score de complexite", str(flow.complexity_score)),
        ("Elements", str(flow.total_elements)),
        ("Elements documentes", str(flow.described_elements)),
        ("Decisions", str(flow.element_counts.get("decisions", 0))),
        ("Formules", str(flow.element_counts.get("formulas", 0))),
        ("Operations de donnees", str(data_operations)),
        ("Variables total", str(flow.variable_total)),
        ("Variables input", str(flow.variable_input)),
        ("Variables output", str(flow.variable_output)),
        ("Profondeur", str(flow.max_depth)),
        ("Largeur max", str(flow.max_width)),
        ("Hauteur min", str(flow.min_height)),
        ("Hauteur max", str(flow.max_height)),
        ("Objet de depart", flow.start_object or "Non renseigne"),
    ]

    if flow.start_object:
        positives.append(f"Le flow est rattache a l'objet `{flow.start_object}`.")
    else:
        improvements.append("L'objet ou le contexte de depart n'est pas clairement identifiable.")

    if described_ratio >= 0.6:
        positives.append("La majorite des elements possedent une description.")
    else:
        improvements.append("Plusieurs elements n'ont pas de description, ce qui reduit la maintenabilite.")

    if flow.description:
        positives.append("Le flow possede une description globale.")
    else:
        improvements.append("Ajouter une description globale au flow aiderait la comprehension.")

    if flow.total_elements <= 12:
        positives.append("La taille du flow reste raisonnable.")
    elif flow.total_elements > 25:
        improvements.append("Le flow semble volumineux; envisager un decoupage en sous-flows.")

    if flow.complexity_level == "Simple":
        positives.append("Le score global de complexite est faible.")
    elif flow.complexity_level == "Moyen":
        positives.append("La complexite globale du flow reste maitrisee.")
    elif flow.complexity_level == "Complexe":
        improvements.append("Le score global place ce flow dans une zone complexe; surveiller sa maintenabilite.")
    else:
        improvements.append("Le score global indique un flow tres complexe; un decoupage fonctionnel est a envisager.")

    if flow.max_depth <= 2:
        positives.append("Le niveau d'imbrication structurelle reste contenu.")
    elif flow.max_depth >= 4:
        improvements.append("La profondeur du flow est elevee; verifier la lisibilite et le risque de complexite excessive.")

    if flow.max_width <= 3:
        positives.append("La largeur maximale du flow reste raisonnable.")
    elif flow.max_width >= 5:
        improvements.append("Le flow presente beaucoup de branches en parallele; verifier la clarte des chemins fonctionnels.")

    if flow.element_counts.get("decisions", 0) <= 3:
        positives.append("La logique de branchement parait relativement contenue.")
    elif flow.element_counts.get("decisions", 0) > 6:
        improvements.append("Le nombre de decisions est eleve, ce qui peut compliquer le debogage.")

    if data_operations <= 4:
        positives.append("Le volume d'operations de donnees reste modere.")
    else:
        improvements.append("Le flow enchaine plusieurs operations de donnees; verifier l'impact sur les performances et la lisibilite.")

    if flow.variable_total == 0:
        positives.append("Aucune variable de flow n'a ete detectee.")
    elif flow.variable_input + flow.variable_output > max(1, flow.variable_total // 2):
        positives.append("Le flow declare explicitement plusieurs variables d'entree ou de sortie.")
    else:
        improvements.append("Verifier si certaines entrees/sorties meritent d'etre formalisees par des variables de flow.")

    summary = "Analyse heuristique statique du flow Salesforce."
    return ReviewResult(summary=summary, positives=positives, improvements=improvements, metrics=metrics)
