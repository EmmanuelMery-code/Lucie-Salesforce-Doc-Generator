"""One-shot helper used to emit the FR/EN RTF guides next to the drawio
diagrams. Kept simple on purpose: structured content -> RTF tokens.

Run: python process/_build_rtf.py

Outputs:
    process/guide_utilisation_fr.rtf
    process/usage_guide_en.rtf

The script can safely be deleted once the RTF files are produced; it is
re-executable to refresh them after edits.
"""
from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# RTF helpers
# ---------------------------------------------------------------------------

# Map of common non-ASCII characters used in the documents to their cp1252
# escape representation. Anything missing falls back to the unicode escape
# form (\uNNNN?) so the writer stays robust if extra characters slip in.
CP1252_MAP = {
    "\u00e0": "\\'e0", "\u00e2": "\\'e2", "\u00e4": "\\'e4",
    "\u00e7": "\\'e7",
    "\u00e8": "\\'e8", "\u00e9": "\\'e9", "\u00ea": "\\'ea", "\u00eb": "\\'eb",
    "\u00ee": "\\'ee", "\u00ef": "\\'ef",
    "\u00f4": "\\'f4", "\u00f6": "\\'f6",
    "\u00f9": "\\'f9", "\u00fb": "\\'fb", "\u00fc": "\\'fc",
    "\u00ff": "\\'ff",
    "\u00c0": "\\'c0", "\u00c2": "\\'c2",
    "\u00c7": "\\'c7",
    "\u00c8": "\\'c8", "\u00c9": "\\'c9", "\u00ca": "\\'ca",
    "\u00ce": "\\'ce", "\u00cf": "\\'cf",
    "\u00d4": "\\'d4",
    "\u00d9": "\\'d9", "\u00db": "\\'db",
    "\u00b0": "\\'b0",
    "\u00ab": "\\'ab", "\u00bb": "\\'bb",
    "\u20ac": "\\'80",
}


def rtf_escape(text: str) -> str:
    out: list[str] = []
    for char in text:
        if char in ("\\", "{", "}"):
            out.append("\\" + char)
        elif char in CP1252_MAP:
            out.append(CP1252_MAP[char])
        elif ord(char) < 128:
            out.append(char)
        else:
            out.append(f"\\u{ord(char)}?")
    return "".join(out)


HEADER = (
    "{\\rtf1\\ansi\\ansicpg1252\\deff0\\nouicompat\\deflang1036\n"
    "{\\fonttbl{\\f0\\fnil\\fcharset0 Calibri;}{\\f1\\fnil\\fcharset0 Consolas;}}\n"
    "{\\colortbl ;\\red0\\green0\\blue0;\\red0\\green70\\blue140;\\red80\\green80\\blue80;\\red200\\green80\\blue40;}\n"
    "{\\*\\generator Lucie Process Doc;}\\viewkind4\\uc1\n"
    "\\paperw11906\\paperh16838\\margl1134\\margr1134\\margt1134\\margb1134\n"
    "\\pard\\sa120\\sl276\\slmult1\\f0\\fs22 "
)
FOOTER = "}\n"


def h1(text: str) -> str:
    return (
        "\\pard\\sb240\\sa120\\keepn\\f0\\fs40\\b\\cf2 "
        + rtf_escape(text)
        + "\\b0\\cf1\\fs22\\par\n"
    )


def h2(text: str) -> str:
    return (
        "\\pard\\sb200\\sa100\\keepn\\f0\\fs30\\b\\cf2 "
        + rtf_escape(text)
        + "\\b0\\cf1\\fs22\\par\n"
    )


def h3(text: str) -> str:
    return (
        "\\pard\\sb160\\sa80\\keepn\\f0\\fs26\\b "
        + rtf_escape(text)
        + "\\b0\\fs22\\par\n"
    )


def paragraph(text: str) -> str:
    return "\\pard\\sa120\\sl276\\slmult1\\fs22 " + rtf_escape(text) + "\\par\n"


def quote(text: str) -> str:
    return (
        "\\pard\\sa120\\sl276\\slmult1\\li567\\ri567\\i\\cf3\\fs22 "
        + rtf_escape(text)
        + "\\i0\\cf1\\par\n"
    )


def bullets(items: list[str]) -> str:
    chunks = []
    for item in items:
        chunks.append(
            "\\pard\\fi-360\\li720\\sa80\\sl276\\slmult1\\fs22 "
            "\\bullet\\tab "
            + rtf_escape(item)
            + "\\par\n"
        )
    return "".join(chunks)


def numbered(items: list[str]) -> str:
    chunks = []
    for index, item in enumerate(items, start=1):
        chunks.append(
            "\\pard\\fi-360\\li720\\sa80\\sl276\\slmult1\\fs22 "
            f"{index}.\\tab "
            + rtf_escape(item)
            + "\\par\n"
        )
    return "".join(chunks)


def code_block(lines: list[str]) -> str:
    chunks = ["\\pard\\sa60\\sl240\\slmult1\\li360\\f1\\fs20\\cf4 "]
    for line in lines:
        chunks.append(rtf_escape(line) + "\\line ")
    chunks.append("\\f0\\fs22\\cf1\\par\n")
    return "".join(chunks)


def page_break() -> str:
    return "\\page\n"


def placeholder(text: str) -> str:
    return (
        "\\pard\\sa160\\sb160\\li360\\ri360\\b\\cf4\\fs24 "
        + rtf_escape(text)
        + "\\b0\\cf1\\fs22\\par\n"
    )


def build_document(parts: list[str]) -> str:
    return HEADER + "".join(parts) + FOOTER


# ---------------------------------------------------------------------------
# French content
# ---------------------------------------------------------------------------

def french_document() -> str:
    parts: list[str] = []

    parts.append(h1("Lucie : Salesforce Doc Generator"))
    parts.append(h1("Guide d'utilisation pour Squads, Tech Leads et Design Review"))
    parts.append(
        paragraph(
            "Ce document explique pas \u00e0 pas comment les Squads, les Tech "
            "Leads et le Design Review s'appuient sur Lucie pour produire, "
            "partager et exploiter une documentation Salesforce de qualit\u00e9. "
            "Il met l'accent sur les b\u00e9n\u00e9fices apport\u00e9s par "
            "l'outil et sur l'aspect collaboratif au sein de l'\u00e9quipe."
        )
    )
    parts.append(page_break())

    # ---------- 1. Vue d'ensemble
    parts.append(h1("1. Vue d'ensemble"))
    parts.append(
        paragraph(
            "Lucie est un outil interne qui analyse une org Salesforce et "
            "produit en sortie : une documentation HTML compl\u00e8te (objets, "
            "Apex, Flows, OmniStudio, permissions), des classeurs Excel "
            "d\u00e9taill\u00e9s (data dictionary, profils, permission sets, "
            "inventaire, violations PMD) et deux documents Word (un "
            "dictionnaire de donn\u00e9es et un r\u00e9sum\u00e9 contenant des "
            "conseils pri\u00f4ris\u00e9s)."
        )
    )
    parts.append(paragraph("Trois publics utilisent Lucie :"))
    parts.append(
        bullets(
            [
                "Les Squads : pour explorer rapidement la m\u00e9tadonn\u00e9e, "
                "pr\u00e9parer une story ou v\u00e9rifier l'impact d'une "
                "livraison.",
                "Les Tech Leads : pour piloter la qualit\u00e9 technique, "
                "suivre l'\u00e9volution d'une org sprint apr\u00e8s sprint et "
                "alimenter les revues transverses.",
                "Le Design Review : pour disposer d'un support standardis\u00e9 "
                "permettant d'arbitrer et de pri\u00f4riser les actions \u00e0 "
                "mener.",
            ]
        )
    )
    parts.append(
        paragraph(
            "La documentation produite est centralis\u00e9e dans un "
            "r\u00e9pertoire commun afin que tout le monde travaille sur la "
            "m\u00eame base de connaissances."
        )
    )

    # ---------- 2. Avantages cl\u00e9s
    parts.append(h1("2. Avantages cl\u00e9s"))
    parts.append(
        bullets(
            [
                "Documentation automatique standardis\u00e9e : plus besoin de "
                "maintenir manuellement le data dictionary, les pages "
                "Apex/Flow ou la liste des permission sets.",
                "Conseils pri\u00f4ris\u00e9s : le r\u00e9sum\u00e9 Word liste "
                "les actions \u00e0 mener, tri\u00e9es par s\u00e9v\u00e9rit\u00e9 "
                "puis par nombre d'occurrences. Les actions les plus "
                "impactantes apparaissent en premier.",
                "Score Adopt vs Adapt : un indicateur synth\u00e9tique "
                "permettant de comparer le niveau de personnalisation entre "
                "orgs ou dans le temps.",
                "D\u00e9tection d'anti-patterns : r\u00e8gles d'analyse "
                "statique inspir\u00e9es de PMD, du Salesforce "
                "Well-Architected Framework et des Architect Decision Guides.",
                "Multilingue : g\u00e9n\u00e9ration en fran\u00e7ais ou en "
                "anglais selon la langue de l'interface.",
                "Assistant IA int\u00e9gr\u00e9 : possibilit\u00e9 de "
                "dialoguer avec Claude ou Gemini sur l'org analys\u00e9e.",
                "Collaboration native : configuration partageable (poids, "
                "r\u00e8gles, exclusions), r\u00e9pertoire de sortie commun, "
                "format adapt\u00e9 aux comptes rendus de r\u00e9union.",
            ]
        )
    )

    # ---------- 3. Pr\u00e9paration et configuration commune
    parts.append(h1("3. Pr\u00e9paration et configuration commune"))
    parts.append(
        paragraph(
            "Avant de distribuer Lucie aux Squads, le pilote technique met en "
            "place une configuration de r\u00e9f\u00e9rence partag\u00e9e."
        )
    )

    parts.append(h2("3.1 Installation"))
    parts.append(
        numbered(
            [
                "Cloner le d\u00e9p\u00f4t.",
                "Installer les d\u00e9pendances : pip install -r requirements.txt.",
                "(Optionnel) Installer Salesforce CLI (sf) et PMD pour les "
                "fonctions int\u00e9gr\u00e9es.",
                "Lancer l'application : python app.py.",
            ]
        )
    )

    parts.append(h2("3.2 Configuration partag\u00e9e"))
    parts.append(paragraph("Dans l'\u00e9cran de configuration, l'\u00e9quipe s'accorde sur :"))
    parts.append(
        bullets(
            [
                "Le dossier de sortie commun (chemin r\u00e9seau, OneDrive ou "
                "SharePoint partag\u00e9 par toutes les Squads).",
                "Le fichier d'exclusions (exclusion.xlsx) versionn\u00e9 et "
                "utilis\u00e9 par toutes les Squads pour homog\u00e9n\u00e9iser "
                "les r\u00e9sultats.",
                "Le ruleset PMD (optionnel), versionn\u00e9 dans le m\u00eame "
                "d\u00e9p\u00f4t.",
                "Les r\u00e8gles d'analyse statique (rules.xml) : valider la "
                "liste des r\u00e8gles activ\u00e9es via l'onglet "
                "\u00ab R\u00e8gles d'analyse \u00bb.",
                "Les poids de scoring et Adopt vs Adapt : standards, sinon les "
                "scores ne sont plus comparables d'une Squad \u00e0 l'autre.",
                "La langue de l'interface (FR ou EN) qui d\u00e9finit la "
                "langue des documents Word produits.",
                "Les options \u00ab G\u00e9n\u00e9rer le Data Dictionary "
                "Word \u00bb et \u00ab G\u00e9n\u00e9rer le r\u00e9sum\u00e9 "
                "Word \u00bb : coch\u00e9es par d\u00e9faut, \u00e0 laisser "
                "actives pour le partage avec le Design Review.",
                "Les cl\u00e9s API IA (Claude, Gemini) : individuelles, \u00e0 "
                "laisser dans la configuration personnelle de chaque "
                "utilisateur.",
            ]
        )
    )
    parts.append(
        quote(
            "Astuce : versionner exclusion.xlsx, rules.xml et le ruleset PMD "
            "dans un d\u00e9p\u00f4t Git commun garantit l'homog\u00e9n\u00e9it\u00e9 "
            "des analyses entre toutes les Squads."
        )
    )

    parts.append(page_break())

    # ---------- 4. Squads
    parts.append(h1("4. Mode op\u00e9ratoire pour les Squads"))
    parts.append(
        paragraph(
            "Chaque Squad utilise Lucie pour ses besoins du quotidien : "
            "exploration de l'org, pr\u00e9paration d'une story, audit avant "
            "livraison."
        )
    )

    parts.append(h2("4.1 Lancement classique"))
    parts.append(
        numbered(
            [
                "Ouvrir Lucie via la commande python app.py.",
                "S\u00e9lectionner le dossier source (r\u00e9sultat d'un "
                "retrieve Salesforce ou clone du repo de la Squad).",
                "S\u00e9lectionner le dossier de sortie commun, dans un "
                "sous-dossier propre \u00e0 la Squad et dat\u00e9 (ex. "
                "\\\\share\\lucie\\squad-alpha\\2026-04-25).",
                "Charger l'org Salesforce : via Web login + alias puis "
                "G\u00e9n\u00e9rer manifest et Faire retrieve, ou directement "
                "via le bouton Manifest + Retrieve + Doc qui encha\u00eene "
                "tout en une fois.",
                "Cliquer sur G\u00e9n\u00e9rer la documentation.",
                "Ouvrir l'index HTML et explorer la documentation g\u00e9n\u00e9r\u00e9e.",
            ]
        )
    )

    parts.append(h2("4.2 Cas d'usage recommand\u00e9s"))
    parts.append(
        bullets(
            [
                "Onboarding d'un nouvel arrivant : la documentation HTML "
                "offre une cartographie imm\u00e9diate de l'org (objets, "
                "flows, classes Apex, permissions).",
                "Pr\u00e9paration d'une story : ouvrir le data dictionary "
                "Word ou la page de l'objet impact\u00e9 pour identifier les "
                "champs, record types et r\u00e8gles d\u00e9j\u00e0 en place.",
                "Audit avant livraison : g\u00e9n\u00e9rer la doc avant la "
                "livraison et comparer le r\u00e9sum\u00e9 Word avec la "
                "g\u00e9n\u00e9ration pr\u00e9c\u00e9dente pour rep\u00e9rer "
                "les nouveaux findings.",
                "V\u00e9rification rapide : utiliser l'assistant IA (onglet "
                "Discussion) pour poser des questions sur l'org sans devoir "
                "naviguer dans le code.",
            ]
        )
    )

    parts.append(h2("4.3 Conseils Squad"))
    parts.append(
        bullets(
            [
                "Lancer la g\u00e9n\u00e9ration avant chaque sprint review "
                "pour disposer d'un point de r\u00e9f\u00e9rence stable.",
                "Stocker la documentation dans le r\u00e9pertoire commun : "
                "les autres Squads et le Design Review s'appuieront dessus.",
                "R\u00e9agir rapidement aux findings Critical et Major du "
                "r\u00e9sum\u00e9 Word ; ce sont eux qui remontent le plus "
                "vite en Design Review.",
            ]
        )
    )

    placeholder1 = (
        "[PLACEHOLDER DIAGRAMME 1 : Workflow Squad - "
        "ins\u00e9rer ici l'export PNG ou PDF du fichier "
        "squad_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder1))

    parts.append(page_break())

    # ---------- 5. Tech Leads
    parts.append(h1("5. Mode op\u00e9ratoire pour les Tech Leads"))
    parts.append(
        paragraph(
            "Le Tech Lead pilote la qualit\u00e9 technique de sa Squad et "
            "alimente les revues transverses anim\u00e9es par le manager."
        )
    )

    parts.append(h2("5.1 Responsabilit\u00e9s outillage"))
    parts.append(
        bullets(
            [
                "Maintenir la configuration commune (r\u00e8gles d'analyse, "
                "fichier d'exclusions, poids de scoring).",
                "S'assurer que la Squad g\u00e9n\u00e8re la documentation au "
                "moins une fois par sprint.",
                "V\u00e9rifier les findings remont\u00e9s et organiser leur "
                "traitement avec la Squad.",
                "Remonter au manager les sujets qui d\u00e9passent le "
                "p\u00e9rim\u00e8tre de la Squad et m\u00e9ritent un Design "
                "Review.",
            ]
        )
    )

    parts.append(h2("5.2 Workflow type sur un sprint"))
    parts.append(
        numbered(
            [
                "En d\u00e9but de sprint : r\u00e9cup\u00e9rer la derni\u00e8re "
                "g\u00e9n\u00e9ration stock\u00e9e dans le r\u00e9pertoire "
                "commun pour servir de point de r\u00e9f\u00e9rence.",
                "Pendant le sprint : lancer une analyse interm\u00e9diaire "
                "lors d'une refonte importante (nouvel objet, refactor "
                "Apex, migration Flow).",
                "En fin de sprint : g\u00e9n\u00e9rer la documentation "
                "compl\u00e8te et l'archiver dans le r\u00e9pertoire commun "
                "(sous-dossier dat\u00e9).",
                "Pr\u00e9parer la r\u00e9tro / sprint review : extraire les "
                "3 \u00e0 5 actions les plus prioritaires du r\u00e9sum\u00e9 "
                "Word.",
                "Pr\u00e9parer le Design Review : faire remonter au manager "
                "les findings transverses et les sujets d'arbitrage.",
            ]
        )
    )

    parts.append(h2("5.3 Indicateurs \u00e0 suivre"))
    parts.append(
        bullets(
            [
                "\u00c9volution du score de personnalisation sprint apr\u00e8s "
                "sprint.",
                "\u00c9volution du score Adopt vs Adapt.",
                "Volume de findings par s\u00e9v\u00e9rit\u00e9 (Critical, "
                "Major, Minor, Info).",
                "Top 5 des r\u00e8gles d\u00e9clench\u00e9es, visible dans le "
                "chapitre Conseils du r\u00e9sum\u00e9 Word.",
                "Nombre d'objets et de champs documentaires r\u00e9ellement "
                "exploit\u00e9s (data dictionary).",
            ]
        )
    )

    parts.append(page_break())

    # ---------- 6. Design Review
    parts.append(h1("6. Utilisation en Design Review"))
    parts.append(
        paragraph(
            "Le Design Review combine les sorties produites par chaque Squad "
            "afin de prendre des d\u00e9cisions d'architecture coordonn\u00e9es. "
            "C'est le moment o\u00f9 le r\u00e9sum\u00e9 Word et son chapitre "
            "Conseils prennent toute leur valeur."
        )
    )

    parts.append(h2("6.1 Avant la r\u00e9union"))
    parts.append(
        numbered(
            [
                "Le manager (animateur du Design Review) rassemble dans le "
                "r\u00e9pertoire commun les summary.docx de chaque Squad, les "
                "data_dictionary.docx correspondants et l'index HTML pour "
                "les d\u00e9tails techniques.",
                "Lecture pr\u00e9liminaire du chapitre Conseils de chaque "
                "r\u00e9sum\u00e9.",
                "S\u00e9lection des actions \u00e0 d\u00e9battre, en priorit\u00e9 "
                "celles class\u00e9es Critical et Major.",
                "Pr\u00e9paration de l'ordre du jour \u00e0 partir de cette "
                "s\u00e9lection.",
            ]
        )
    )

    parts.append(h2("6.2 Pendant la r\u00e9union"))
    parts.append(
        numbered(
            [
                "Pr\u00e9senter le r\u00e9sum\u00e9 Word : page de garde, "
                "vue d'ensemble, m\u00e9triques de personnalisation, puis "
                "chapitre Conseils.",
                "Pour chaque action prioritaire, discuter du constat avec "
                "la Squad concern\u00e9e.",
                "D\u00e9cider l'action : corriger maintenant, exception "
                "document\u00e9e ou report avec deadline.",
                "D\u00e9signer la Squad responsable et le porteur de l'action.",
                "Si n\u00e9cessaire, ouvrir le data dictionary Word ou la "
                "documentation HTML pour v\u00e9rifier un d\u00e9tail technique.",
                "Capturer chaque d\u00e9cision dans le compte rendu en citant "
                "l'identifiant de la r\u00e8gle (par exemple APEX-SEC-001).",
            ]
        )
    )

    parts.append(h2("6.3 Apr\u00e8s la r\u00e9union"))
    parts.append(
        bullets(
            [
                "Stocker le compte rendu \u00e0 c\u00f4t\u00e9 de la "
                "documentation analys\u00e9e dans le r\u00e9pertoire commun.",
                "Le compte rendu fait r\u00e9f\u00e9rence aux findings du "
                "r\u00e9sum\u00e9 Word, ce qui rend les d\u00e9cisions "
                "rejouables.",
                "Au Design Review suivant, v\u00e9rifier la d\u00e9croissance "
                "du nombre d'occurrences pour chaque finding trait\u00e9 et "
                "f\u00e9liciter les Squads qui ont avanc\u00e9.",
            ]
        )
    )

    placeholder2 = (
        "[PLACEHOLDER DIAGRAMME 2 : Workflow Design Review - "
        "ins\u00e9rer ici l'export PNG ou PDF du fichier "
        "design_review_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder2))

    parts.append(page_break())

    # ---------- 7. Aspect collaboratif
    parts.append(h1("7. Aspect collaboratif et r\u00e9pertoire commun"))
    parts.append(
        paragraph(
            "L'outil prend tout son sens lorsqu'il est partag\u00e9 et que "
            "tous les acteurs travaillent depuis le m\u00eame r\u00e9pertoire "
            "de r\u00e9f\u00e9rence."
        )
    )

    parts.append(h2("7.1 Arborescence type"))
    parts.append(
        code_block(
            [
                "\\\\share\\lucie\\",
                "+-- _config\\",
                "|   +-- exclusion.xlsx",
                "|   +-- rules.xml",
                "|   +-- pmd_ruleset.xml",
                "+-- squad-alpha\\",
                "|   +-- 2026-04-11\\",
                "|   |   +-- index.html",
                "|   |   +-- excel\\...",
                "|   |   +-- word\\data_dictionary.docx",
                "|   |   +-- word\\summary.docx",
                "|   +-- 2026-04-25\\",
                "+-- squad-beta\\",
                "+-- design-review\\",
                "    +-- 2026-04-15-CR.docx",
                "    +-- 2026-04-29-CR.docx",
            ]
        )
    )

    parts.append(h2("7.2 B\u00e9n\u00e9fices collaboratifs"))
    parts.append(
        bullets(
            [
                "Vision unique : tout le monde regarde les m\u00eames "
                "donn\u00e9es et les m\u00eames r\u00e8gles.",
                "Capitalisation : l'historique des g\u00e9n\u00e9rations sert "
                "de m\u00e9moire collective de l'org.",
                "Comparaison : les Tech Leads peuvent comparer leur Squad aux "
                "autres sur des bases \u00e9quivalentes.",
                "D\u00e9cision trac\u00e9e : le compte rendu de Design Review "
                "fait r\u00e9f\u00e9rence aux identifiants de r\u00e8gles, "
                "rendant les arbitrages rejouables.",
                "Communication facilit\u00e9e : les documents Word sont "
                "diffusables aux parties prenantes non techniques (Product "
                "Owners, Architectes, Sponsors).",
            ]
        )
    )

    placeholder3 = (
        "[PLACEHOLDER DIAGRAMME 3 : Vue collaborative - "
        "ins\u00e9rer ici l'export PNG ou PDF du fichier "
        "collaboration_overview.drawio.]"
    )
    parts.append(placeholder(placeholder3))

    parts.append(h1("8. Bonnes pratiques"))
    parts.append(
        bullets(
            [
                "Mettre \u00e0 jour la doc apr\u00e8s chaque \u00e9volution "
                "majeure (nouveau module, refonte d'objet, batch important).",
                "Versionner la configuration commune (exclusion.xlsx, "
                "rules.xml, pmd_ruleset.xml).",
                "Nommer les sous-r\u00e9pertoires de g\u00e9n\u00e9ration avec "
                "une date ISO YYYY-MM-DD pour faciliter le tri.",
                "Limiter l'usage du fichier d'exclusion : il doit refl\u00e9ter "
                "des choix d'architecture, pas masquer des probl\u00e8mes.",
                "Discuter en amont des poids de scoring : un score n'a de "
                "valeur que compar\u00e9 \u00e0 un r\u00e9f\u00e9rentiel "
                "partag\u00e9.",
                "Stocker le compte rendu de Design Review \u00e0 c\u00f4t\u00e9 "
                "de la documentation analys\u00e9e pour la tra\u00e7abilit\u00e9.",
                "Refaire un cycle complet (g\u00e9n\u00e9ration + Design "
                "Review + correction) au moins une fois par release.",
            ]
        )
    )

    parts.append(h1("9. Annexes - sch\u00e9mas associ\u00e9s"))
    parts.append(
        paragraph(
            "Trois diagrammes drawio sont fournis dans ce r\u00e9pertoire et "
            "sont \u00e0 ins\u00e9rer aux emplacements signal\u00e9s par les "
            "blocs PLACEHOLDER ci-dessus :"
        )
    )
    parts.append(
        bullets(
            [
                "squad_workflow.drawio : workflow d'une Squad sur un sprint.",
                "design_review_workflow.drawio : d\u00e9roul\u00e9 d'un Design "
                "Review.",
                "collaboration_overview.drawio : vue d'ensemble de la "
                "collaboration entre Squads, Tech Leads et Design Review.",
            ]
        )
    )
    parts.append(
        paragraph(
            "Pour les ouvrir : utilisez https://app.diagrams.net ou "
            "l'extension Visual Studio Code Draw.io Integration. Exportez "
            "ensuite en PNG ou PDF puis remplacez les blocs PLACEHOLDER de "
            "ce document par l'image correspondante."
        )
    )

    return build_document(parts)


# ---------------------------------------------------------------------------
# English content
# ---------------------------------------------------------------------------

def english_document() -> str:
    parts: list[str] = []

    parts.append(h1("Lucie: Salesforce Doc Generator"))
    parts.append(h1("Usage guide for Squads, Tech Leads and the Design Review"))
    parts.append(
        paragraph(
            "This document explains step-by-step how Squads, Tech Leads and "
            "the Design Review use Lucie to produce, share and leverage a "
            "high-quality Salesforce documentation. It emphasises the "
            "benefits brought by the tool and the collaborative aspect "
            "across the team."
        )
    )
    parts.append(page_break())

    parts.append(h1("1. Overview"))
    parts.append(
        paragraph(
            "Lucie is an internal tool that analyses a Salesforce org and "
            "produces: a complete HTML documentation (objects, Apex, Flows, "
            "OmniStudio, permissions), detailed Excel workbooks (data "
            "dictionary, profiles, permission sets, inventory, PMD "
            "violations) and two Word documents (a data dictionary and a "
            "summary holding prioritised advice)."
        )
    )
    parts.append(paragraph("Three audiences use Lucie:"))
    parts.append(
        bullets(
            [
                "Squads: to quickly explore the metadata, prepare a story or "
                "validate the impact of a delivery.",
                "Tech Leads: to drive technical quality, follow the org "
                "evolution sprint after sprint and feed cross-cutting "
                "reviews.",
                "Design Review: to rely on a standardised support to arbitrate "
                "and prioritise the actions to take.",
            ]
        )
    )
    parts.append(
        paragraph(
            "The generated documentation is centralised in a shared folder "
            "so everyone works on the same body of knowledge."
        )
    )

    parts.append(h1("2. Key benefits"))
    parts.append(
        bullets(
            [
                "Automated, standardised documentation: no more manual "
                "maintenance of the data dictionary, the Apex/Flow pages or "
                "the permission set list.",
                "Prioritised advice: the Word summary lists actions sorted by "
                "severity then by occurrence count. The most impactful items "
                "appear first.",
                "Adopt vs Adapt score: a synthetic indicator to compare the "
                "level of customisation across orgs or over time.",
                "Anti-pattern detection: static analysis rules inspired by "
                "PMD, the Salesforce Well-Architected Framework and the "
                "Architect Decision Guides.",
                "Multilingual: generation in French or English depending on "
                "the UI language.",
                "Built-in AI assistant: discuss the analysed org with Claude "
                "or Gemini.",
                "Native collaboration: shareable configuration (weights, "
                "rules, exclusions), shared output folder, format suited to "
                "meeting minutes.",
            ]
        )
    )

    parts.append(h1("3. Setup and shared configuration"))
    parts.append(
        paragraph(
            "Before rolling Lucie out to the Squads, the technical owner "
            "sets up a shared reference configuration."
        )
    )

    parts.append(h2("3.1 Installation"))
    parts.append(
        numbered(
            [
                "Clone the repository.",
                "Install dependencies: pip install -r requirements.txt.",
                "(Optional) Install Salesforce CLI (sf) and PMD for the "
                "built-in features.",
                "Run the application: python app.py.",
            ]
        )
    )

    parts.append(h2("3.2 Shared configuration"))
    parts.append(paragraph("In the configuration screen, the team agrees on:"))
    parts.append(
        bullets(
            [
                "The shared output folder (network share, OneDrive or "
                "SharePoint accessible to every Squad).",
                "The exclusion file (exclusion.xlsx), versioned and used by "
                "every Squad to homogenise results.",
                "The PMD ruleset (optional), versioned in the same shared "
                "repository.",
                "The static analysis rules (rules.xml): validate the enabled "
                "rules through the \"Analysis rules\" tab.",
                "Scoring weights and Adopt vs Adapt weights: standardised, "
                "otherwise scores stop being comparable across Squads.",
                "The interface language (FR or EN), which drives the language "
                "of the generated Word documents.",
                "The \"Generate the Data Dictionary Word document\" and "
                "\"Generate the summary Word document\" toggles: ticked by "
                "default, leave them on so Design Review has its inputs.",
                "AI API keys (Claude, Gemini): personal, kept in each user's "
                "individual configuration.",
            ]
        )
    )
    parts.append(
        quote(
            "Tip: versioning exclusion.xlsx, rules.xml and the PMD ruleset "
            "in a shared Git repository ensures consistent analyses across "
            "all Squads."
        )
    )

    parts.append(page_break())

    parts.append(h1("4. How Squads use the tool"))
    parts.append(
        paragraph(
            "Each Squad uses Lucie for everyday needs: exploring the org, "
            "preparing a story, auditing before a release."
        )
    )

    parts.append(h2("4.1 Standard run"))
    parts.append(
        numbered(
            [
                "Open Lucie via python app.py.",
                "Pick the source folder (Salesforce retrieve output or clone "
                "of the Squad repo).",
                "Pick the shared output folder, in a Squad-specific dated "
                "subfolder (e.g. \\\\share\\lucie\\squad-alpha\\2026-04-25).",
                "Load the Salesforce org: either via Web login + alias then "
                "Generate manifest and Run retrieve, or directly via the "
                "Manifest + Retrieve + Doc button which chains everything.",
                "Click Generate documentation.",
                "Open the HTML index and explore the generated docs.",
            ]
        )
    )

    parts.append(h2("4.2 Recommended use cases"))
    parts.append(
        bullets(
            [
                "Onboarding a new joiner: the HTML documentation provides an "
                "instant map of the org (objects, flows, Apex classes, "
                "permissions).",
                "Preparing a story: open the data dictionary Word document or "
                "the page of the impacted object to identify existing fields, "
                "record types and rules.",
                "Pre-release audit: generate the docs before delivery and "
                "compare the Word summary with the previous run to spot new "
                "findings.",
                "Quick check: ask the AI assistant (Discussion tab) about the "
                "org instead of digging through code.",
            ]
        )
    )

    parts.append(h2("4.3 Squad guidelines"))
    parts.append(
        bullets(
            [
                "Run the generation before each sprint review to have a "
                "stable baseline.",
                "Store the documentation in the shared folder: other Squads "
                "and Design Review will rely on it.",
                "React quickly to the Critical and Major findings of the "
                "Word summary; they are the first to surface in Design "
                "Review.",
            ]
        )
    )

    placeholder1 = (
        "[DIAGRAM PLACEHOLDER 1: Squad workflow - "
        "insert here the PNG or PDF export of squad_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder1))

    parts.append(page_break())

    parts.append(h1("5. How Tech Leads use the tool"))
    parts.append(
        paragraph(
            "The Tech Lead drives the technical quality of their Squad and "
            "feeds the cross-cutting reviews led by the manager."
        )
    )

    parts.append(h2("5.1 Tooling responsibilities"))
    parts.append(
        bullets(
            [
                "Maintain the shared configuration (analysis rules, exclusion "
                "file, scoring weights).",
                "Make sure the Squad generates the documentation at least "
                "once per sprint.",
                "Review the findings raised and organise their treatment "
                "with the Squad.",
                "Surface to the manager the topics that go beyond the Squad "
                "boundaries and deserve a Design Review.",
            ]
        )
    )

    parts.append(h2("5.2 Typical sprint workflow"))
    parts.append(
        numbered(
            [
                "Beginning of sprint: pull the latest generation stored in "
                "the shared folder as a reference baseline.",
                "During the sprint: launch an intermediate analysis on a "
                "major refactor (new object, Apex refactor, Flow migration).",
                "End of sprint: generate the full documentation and archive "
                "it in the shared folder (dated subfolder).",
                "Prepare the retrospective / sprint review: pull the 3 to 5 "
                "highest-priority actions from the Word summary.",
                "Prepare the Design Review: surface to the manager the "
                "cross-cutting findings and arbitration topics.",
            ]
        )
    )

    parts.append(h2("5.3 Indicators to watch"))
    parts.append(
        bullets(
            [
                "Customisation score evolution sprint after sprint.",
                "Adopt vs Adapt score evolution.",
                "Findings volume per severity (Critical, Major, Minor, Info).",
                "Top 5 triggered rules, visible in the Advice chapter of the "
                "Word summary.",
                "Number of objects and fields actually documented (data "
                "dictionary).",
            ]
        )
    )

    parts.append(page_break())

    parts.append(h1("6. Use in Design Review"))
    parts.append(
        paragraph(
            "The Design Review combines outputs produced by every Squad to "
            "take coordinated architecture decisions. This is where the "
            "Word summary and its Advice chapter shine."
        )
    )

    parts.append(h2("6.1 Before the meeting"))
    parts.append(
        numbered(
            [
                "The manager (Design Review host) gathers from the shared "
                "folder the summary.docx of every Squad, the matching "
                "data_dictionary.docx and the HTML index for technical "
                "details.",
                "Preliminary read of the Advice chapter of every summary.",
                "Selection of actions to debate, prioritising Critical and "
                "Major ones.",
                "Building the agenda from that selection.",
            ]
        )
    )

    parts.append(h2("6.2 During the meeting"))
    parts.append(
        numbered(
            [
                "Walk through the Word summary: cover page, overview, "
                "customisation metrics, then Advice chapter.",
                "For each priority action, discuss the finding with the "
                "concerned Squad.",
                "Decide the action: fix now, documented exception or "
                "deferred with deadline.",
                "Assign the responsible Squad and action owner.",
                "If needed, open the data dictionary Word document or HTML "
                "documentation to double-check a technical detail.",
                "Capture each decision in the meeting minutes by quoting the "
                "rule identifier (for example APEX-SEC-001).",
            ]
        )
    )

    parts.append(h2("6.3 After the meeting"))
    parts.append(
        bullets(
            [
                "Store the meeting minutes next to the analysed documentation "
                "in the shared folder.",
                "Minutes refer to findings from the Word summary, which makes "
                "decisions replayable.",
                "At the next Design Review, verify the decrease in occurrence "
                "count for every treated finding and acknowledge the Squads "
                "that progressed.",
            ]
        )
    )

    placeholder2 = (
        "[DIAGRAM PLACEHOLDER 2: Design Review workflow - "
        "insert here the PNG or PDF export of design_review_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder2))

    parts.append(page_break())

    parts.append(h1("7. Collaborative aspect and shared folder"))
    parts.append(
        paragraph(
            "The tool delivers its full value when shared and when every "
            "actor works from the same reference folder."
        )
    )

    parts.append(h2("7.1 Suggested layout"))
    parts.append(
        code_block(
            [
                "\\\\share\\lucie\\",
                "+-- _config\\",
                "|   +-- exclusion.xlsx",
                "|   +-- rules.xml",
                "|   +-- pmd_ruleset.xml",
                "+-- squad-alpha\\",
                "|   +-- 2026-04-11\\",
                "|   |   +-- index.html",
                "|   |   +-- excel\\...",
                "|   |   +-- word\\data_dictionary.docx",
                "|   |   +-- word\\summary.docx",
                "|   +-- 2026-04-25\\",
                "+-- squad-beta\\",
                "+-- design-review\\",
                "    +-- 2026-04-15-minutes.docx",
                "    +-- 2026-04-29-minutes.docx",
            ]
        )
    )

    parts.append(h2("7.2 Collaborative benefits"))
    parts.append(
        bullets(
            [
                "Single view: everyone reads the same data and the same "
                "rules.",
                "Capitalisation: the generation history works as the "
                "collective memory of the org.",
                "Comparison: Tech Leads can compare their Squad with others "
                "on the same basis.",
                "Traceable decisions: Design Review minutes refer to rule "
                "identifiers, making arbitrations replayable.",
                "Easier communication: the Word documents can be shared with "
                "non-technical stakeholders (Product Owners, Architects, "
                "Sponsors).",
            ]
        )
    )

    placeholder3 = (
        "[DIAGRAM PLACEHOLDER 3: Collaborative view - "
        "insert here the PNG or PDF export of collaboration_overview.drawio.]"
    )
    parts.append(placeholder(placeholder3))

    parts.append(h1("8. Best practices"))
    parts.append(
        bullets(
            [
                "Refresh the docs after each major change (new module, "
                "object refactor, important batch).",
                "Version the shared configuration (exclusion.xlsx, "
                "rules.xml, pmd_ruleset.xml).",
                "Name the generation subfolders with an ISO date YYYY-MM-DD "
                "to ease sorting.",
                "Limit the use of the exclusion file: it must reflect "
                "architecture decisions, not hide problems.",
                "Agree on scoring weights upfront: a score is only "
                "meaningful against a shared reference.",
                "Store Design Review minutes alongside the analysed "
                "documentation for traceability.",
                "Run a full cycle (generation + Design Review + fix) at "
                "least once per release.",
            ]
        )
    )

    parts.append(h1("9. Appendices - associated diagrams"))
    parts.append(
        paragraph(
            "Three drawio diagrams ship in this folder. Insert them where "
            "the PLACEHOLDER blocks appear above:"
        )
    )
    parts.append(
        bullets(
            [
                "squad_workflow.drawio: Squad workflow over a sprint.",
                "design_review_workflow.drawio: Design Review flow.",
                "collaboration_overview.drawio: high-level view of the "
                "collaboration between Squads, Tech Leads and Design Review.",
            ]
        )
    )
    parts.append(
        paragraph(
            "How to open them: use https://app.diagrams.net or the "
            "Draw.io Integration extension for Visual Studio Code. Export "
            "as PNG or PDF and replace the PLACEHOLDER blocks with the "
            "matching image."
        )
    )

    return build_document(parts)


def main() -> None:
    here = Path(__file__).resolve().parent
    fr_path = here / "guide_utilisation_fr.rtf"
    en_path = here / "usage_guide_en.rtf"
    fr_path.write_text(french_document(), encoding="cp1252", errors="replace")
    en_path.write_text(english_document(), encoding="cp1252", errors="replace")
    print("Wrote", fr_path)
    print("Wrote", en_path)


if __name__ == "__main__":
    main()
