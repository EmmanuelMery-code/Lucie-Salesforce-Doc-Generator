"""Renderer for the methodology explanation page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.customization_metrics import (
    CAPABILITY_CATALOG,
    CAPABILITY_LEVEL_ORDER,
    CapabilityLevel,
    PostureCapabilityConfig,
)
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import (
    href_relative,
    index_back_link,
    render_page,
)


LogCallback = Callable[[str], None]


def render_methodology_page(
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    posture_config: list[PostureCapabilityConfig] | None = None,
) -> str:
    """Render the methodology explanation page."""

    back_link = index_back_link(current_path, output_dir)

    # Section IA
    ia_section = """
    <div class="section">
        <h2>Usage IA</h2>
        <p>L'indicateur <strong>Usage IA</strong> mesure la proportion d'éléments de métadonnées qui ont été annotés avec des tags spécifiques (par défaut <code>@IAgenerated</code>, <code>@IAassisted</code>). Cela permet de suivre l'adoption des outils d'intelligence artificielle dans le cycle de développement.</p>
        <ul>
            <li><strong>Périmètre de scan :</strong> L'outil parcourt les descriptions des objets, champs, record types, règles de validation, flows, profils et permission sets. Pour le code Apex (classes et triggers), il analyse les commentaires source.</li>
            <li><strong>Calcul :</strong> Le pourcentage est calculé sur l'univers de personnalisation (objets/champs customs, Apex, Flows, etc.). Un élément est considéré comme "IA" s'il contient au moins un des tags configurés.</li>
        </ul>
    </div>
    """

    # Section Data Model
    dm_section = """
    <div class="section">
        <h2>Empreinte data model</h2>
        <p>Cette mesure quantifie l'extension du modèle de données standard de Salesforce.</p>
        <ul>
            <li><strong>Objets :</strong> Compare le nombre d'objets personnalisés (finissant par <code>__c</code>) au nombre d'objets standards présents dans le périmètre d'analyse.</li>
            <li><strong>Champs :</strong> Compare le nombre de champs personnalisés (sur tous les objets) au nombre de champs standards.</li>
            <li><strong>Ratio Global :</strong> Chaque objet et chaque champ compte pour une "unité". Le ratio global est la somme des éléments customs divisée par le total des éléments analysés.</li>
        </ul>
    </div>
    """

    # Section Posture Adopt vs Adapt
    posture_intro = """
    <div class="section">
        <h2>Posture Adopt vs Adapt</h2>
        <p>Cette analyse évalue si l'organisation privilégie l'utilisation des fonctionnalités natives (<strong>Adopt</strong>) ou si elle a fortement personnalisé la plateforme (<strong>Adapt</strong>).</p>
        
        <h3>Mécanisme de calcul</h3>
        <p>L'analyse repose sur un catalogue de capacités (Modèle de données, Sécurité, Automatisation, etc.). Pour chaque capacité :</p>
        <ol>
            <li>Un <strong>Niveau</strong> est déterminé (soit par détection automatique, soit forcé manuellement).</li>
            <li>Un <strong>Poids</strong> est appliqué (par défaut de 1 à 3 selon l'importance architecturale).</li>
            <li>Le score final est le ratio du poids des capacités classées en <em>Adoption</em> sur le poids total.</li>
        </ol>
        
        <h4>Signification des Niveaux</h4>
        <table>
            <thead>
                <tr><th>Niveau</th><th>Catégorie</th><th>Description</th></tr>
            </thead>
            <tbody>
                <tr><td><strong>Adopt (OOTB)</strong></td><td>Adoption</td><td>Utilisation telle quelle des fonctions standards.</td></tr>
                <tr><td><strong>Adopt déclaratif</strong></td><td>Adoption</td><td>Utilisation de fonctions standards via les outils de configuration.</td></tr>
                <tr><td><strong>Adapt (déclaratif)</strong></td><td>Adaptation</td><td>Extension via des outils sans code (Flows, VR, etc.).</td></tr>
                <tr><td><strong>Adapt (code)</strong></td><td>Adaptation</td><td>Extension lourde via du code (Apex, LWC, OmniStudio).</td></tr>
            </tbody>
        </table>
    </div>
    """

    # Detail of Auto-detection
    auto_detection_details = """
    <div class="section">
        <h3>Interprétation du mode "Auto (detection)"</h3>
        <p>Lorsque le niveau est réglé sur <em>Auto</em>, l'outil utilise des heuristiques pour classer la capacité :</p>
        <ul>
            <li><strong>Modèle de données :</strong> <em>Adapt (déclaratif)</em> si peu d'objets customs, <em>Adapt (code)</em> si plus de 3 objets customs.</li>
            <li><strong>Sécurité :</strong> <em>Adapt (code)</em> si des profils personnalisés sont détectés, <em>Adapt (déclaratif)</em> si seuls des Permission Sets sont utilisés.</li>
            <li><strong>Automatisation :</strong> <em>Adapt (code)</em> si des Triggers Apex existent, <em>Adapt (déclaratif)</em> si seuls des Flows sont présents.</li>
            <li><strong>Validation :</strong> <em>Adapt (code)</em> si <code>addError</code> est utilisé dans des triggers, <em>Adapt (déclaratif)</em> pour les Validation Rules standards.</li>
            <li><strong>UI / Layout :</strong> <em>Adapt (code)</em> si des composants LWC sont présents, <em>Adapt (déclaratif)</em> pour les FlexiPages.</li>
            <li><strong>Intégration :</strong> <em>Adapt (code)</em> si des appels HTTP ou du code asynchrone sont détectés dans Apex.</li>
            <li><strong>OmniStudio :</strong> <em>Adapt (code)</em> pour les OmniScripts/IP, <em>Adapt (déclaratif)</em> pour les DataRaptors/FlexCards.</li>
        </ul>
    </div>
    """

    # Current Configuration Table
    config_rows = []
    if posture_config:
        for entry in posture_config:
            level_str = entry.level.value if entry.level else "Auto (détection)"
            config_rows.append(
                f"<tr><td>{html_value(entry.label)}</td><td>{entry.weight}</td><td>{html_value(level_str)}</td><td>{'Oui' if entry.custom else 'Non'}</td></tr>"
            )
    else:
        # Fallback to defaults if no config provided
        for definition in CAPABILITY_CATALOG:
            config_rows.append(
                f"<tr><td>{html_value(definition.label)}</td><td>{definition.weight}</td><td>Auto (détection)</td><td>Non</td></tr>"
            )

    config_table = f"""
    <div class="section">
        <h3>Paramètres appliqués pour cette génération</h3>
        <table>
            <thead>
                <tr><th>Capacité</th><th>Poids</th><th>Niveau configuré</th><th>Personnalisée</th></tr>
            </thead>
            <tbody>
                {''.join(config_rows)}
            </tbody>
        </table>
    </div>
    """

    body = f"""
    {back_link}
    <h1>Méthodologie de calcul</h1>
    <p>Cette page détaille les règles et les paramètres utilisés pour produire les indicateurs de synthèse de cette documentation.</p>
    {ia_section}
    {dm_section}
    {posture_intro}
    {auto_detection_details}
    {config_table}
    """

    return render_page("Méthodologie", body, current_path, assets_dir, include_mermaid=False)


def write_methodology_page(
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    posture_config: list[PostureCapabilityConfig] | None = None,
) -> Path:
    """Write methodology.html and return its path."""
    path = output_dir / "methodology.html"
    write_text(path, render_methodology_page(path, output_dir, assets_dir, posture_config))
    log(f"Page Méthodologie générée : {path}")
    return path
