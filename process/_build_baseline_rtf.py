"""One-shot helper used to emit the FR RTF document explaining how to set up
a baseline org and follow the evolution of releases with Lucie.

Run: python process/_build_baseline_rtf.py

Output:
    process/baseline_evolution_fr.rtf

The script can safely be deleted once the RTF is produced; it is
re-executable to refresh it after edits.
"""
from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# RTF helpers (kept locally so the script stays self-contained)
# ---------------------------------------------------------------------------

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
    "{\\*\\generator Lucie Baseline Doc;}\\viewkind4\\uc1\n"
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


def table(headers: list[str], rows: list[list[str]], widths: list[int] | None = None) -> str:
    """Render a simple RTF table.

    `widths` is a list of right-edge cell positions in twips. If omitted, the
    columns are evenly distributed within ~9000 twips (A4 with margins).
    """
    column_count = len(headers)
    if widths is None:
        total = 9000
        step = total // column_count
        widths = [step * (i + 1) for i in range(column_count)]

    def render_row(cells: list[str], bold: bool) -> str:
        out = ["\\trowd\\trgaph108\\trleft0"]
        for right in widths:
            out.append(f"\\cellx{right}")
        prefix = "\\b " if bold else ""
        suffix = "\\b0 " if bold else ""
        for cell in cells:
            out.append(
                "\\pard\\intbl\\sa0\\sl240\\slmult1\\fs20 "
                + prefix
                + rtf_escape(cell)
                + suffix
                + "\\cell"
            )
        out.append("\\row\n")
        return "".join(out)

    parts = [render_row(headers, bold=True)]
    for row in rows:
        padded = list(row) + [""] * (column_count - len(row))
        parts.append(render_row(padded, bold=False))
    parts.append("\\pard\\sa120\\sl276\\slmult1\\fs22 \\par\n")
    return "".join(parts)


def build_document(parts: list[str]) -> str:
    return HEADER + "".join(parts) + FOOTER


# ---------------------------------------------------------------------------
# French content
# ---------------------------------------------------------------------------

def french_document() -> str:
    parts: list[str] = []

    parts.append(h1(
        "Lucie : \u00e9tablir une base et suivre l'\u00e9volution des "
        "livraisons"
    ))
    parts.append(
        paragraph(
            "Ce document d\u00e9crit la d\u00e9marche \u00e0 mettre en place "
            "pour exploiter Lucie comme outil de mesure de la qualit\u00e9 "
            "d'une org Salesforce au fil des releases. Il pr\u00e9cise quels "
            "indicateurs sont produits, comment fixer une base de "
            "r\u00e9f\u00e9rence (org neutre ou snapshot T0), comment "
            "s'articule le processus de livraison et comment Lucie "
            "intervient \u00e0 chaque \u00e9tape pour mesurer les "
            "\u00e9volutions."
        )
    )
    parts.append(
        quote(
            "Principe directeur : un score n'a de valeur que rapport\u00e9 "
            "\u00e0 une r\u00e9f\u00e9rence stable. Sans baseline, les "
            "indicateurs de Lucie ne sont que des chiffres ; avec une "
            "baseline, ils deviennent une trajectoire."
        )
    )
    parts.append(page_break())

    # ---------- 1. Indicateurs suivis
    parts.append(h1("1. Indicateurs suivis par Lucie"))
    parts.append(
        paragraph(
            "Lucie expose quatre familles d'indicateurs compl\u00e9mentaires. "
            "Chacune r\u00e9pond \u00e0 une question diff\u00e9rente sur "
            "l'\u00e9tat de l'org."
        )
    )

    parts.append(h2("1.1 Score de personnalisation"))
    parts.append(
        paragraph(
            "Score quantitatif calcul\u00e9 \u00e0 partir des objets custom, "
            "champs custom, record types, validation rules, layouts, onglets, "
            "applications, flows, classes Apex, triggers et composants "
            "OmniStudio. Chaque \u00e9l\u00e9ment porte un poids "
            "param\u00e9trable et la somme positionne l'org sur les niveaux "
            "Faible / Moyen / \u00c9lev\u00e9 / Tr\u00e8s \u00e9lev\u00e9."
        )
    )
    parts.append(
        paragraph(
            "Question r\u00e9pondue : quelle est la masse de "
            "personnalisation accumul\u00e9e dans l'org ?"
        )
    )

    parts.append(h2("1.2 Score Adopt vs Adapt"))
    parts.append(
        paragraph(
            "Score sp\u00e9cifique inspir\u00e9 du principe Salesforce "
            "\u00ab Adopt before Adapt before Build \u00bb. Il pond\u00e8re "
            "principalement les composants qui s'\u00e9loignent du standard "
            "(Apex, Flows, OmniStudio, LWC, Flexipages, custom objects, "
            "custom fields). L'org est positionn\u00e9e sur un des "
            "niveaux : Adopt (Standard), Adapt (Low), Adapt (Medium), "
            "Adapt (High)."
        )
    )
    parts.append(
        paragraph(
            "Question r\u00e9pondue : \u00e0 quel point l'org "
            "s'\u00e9loigne-t-elle du standard Salesforce ?"
        )
    )

    parts.append(h2("1.3 Findings de l'analyzer interne"))
    parts.append(
        paragraph(
            "Lucie embarque un analyzer statique pilot\u00e9 par le "
            "catalogue rules.xml. Les r\u00e8gles couvrent Apex, triggers, "
            "Flows, objets, champs, validation rules et OmniStudio. Chaque "
            "finding porte une cat\u00e9gorie Well-Architected (Trusted, "
            "Easy, Adaptable) et une s\u00e9v\u00e9rit\u00e9 (Critical, "
            "Major, Minor, Info)."
        )
    )
    parts.append(
        paragraph(
            "Question r\u00e9pondue : quels anti-patterns architecturaux "
            "ou de maintenabilit\u00e9 sont d\u00e9tect\u00e9s sur la "
            "metadata ?"
        )
    )

    parts.append(h2("1.4 Violations PMD"))
    parts.append(
        paragraph(
            "Lucie peut s'interfacer avec PMD pour produire un rapport "
            "compl\u00e9mentaire sur les classes Apex (priorit\u00e9s "
            "PMD 1 \u00e0 5). Cette source compl\u00e8te l'analyzer en "
            "apportant des r\u00e8gles industrielles \u00e9prouv\u00e9es."
        )
    )
    parts.append(
        paragraph(
            "Question r\u00e9pondue : quel est l'\u00e9tat du code Apex "
            "vu par un outil de r\u00e9f\u00e9rence du march\u00e9 ?"
        )
    )

    parts.append(h2("1.5 M\u00e9triques de complexit\u00e9 d\u00e9taill\u00e9es"))
    parts.append(paragraph("En sus des scores, Lucie produit des m\u00e9triques fines :"))
    parts.append(
        bullets(
            [
                "Apex : nombre de lignes, m\u00e9thodes, SOQL, SOSL, DML, "
                "d\u00e9bug, pr\u00e9sence de SOQL ou DML en boucle, "
                "d\u00e9claration de partage, gestion d'exception.",
                "Flows : score de complexit\u00e9, niveau (Simple / Moyen / "
                "Complexe / Tr\u00e8s complexe), profondeur, largeur, "
                "nombre de d\u00e9cisions, d'op\u00e9rations de donn\u00e9es, "
                "de variables.",
                "Objets : nombre de champs, record types, validation rules, "
                "layouts.",
                "OmniStudio : OmniScripts, Integration Procedures, UI Cards, "
                "Data Transforms.",
            ]
        )
    )
    parts.append(
        quote(
            "Bonne pratique : surveiller en priorit\u00e9 le score Adopt vs "
            "Adapt et les findings Critical. Les m\u00e9triques fines "
            "permettent d'expliquer une variation des scores."
        )
    )

    parts.append(page_break())

    # ---------- 2. La base : org neutre / snapshot T0
    parts.append(h1("2. D\u00e9finir la base : l'org neutre ou snapshot T0"))

    parts.append(h2("2.1 Qu'est-ce qu'une base ?"))
    parts.append(
        paragraph(
            "La base est le point de r\u00e9f\u00e9rence \u00e0 partir "
            "duquel on mesure toutes les \u00e9volutions. C'est un \u00e9tat "
            "fig\u00e9 de la metadata, document\u00e9 par Lucie une fois "
            "pour toutes, et auquel toutes les g\u00e9n\u00e9rations "
            "ult\u00e9rieures seront compar\u00e9es."
        )
    )

    parts.append(h2("2.2 Trois fa\u00e7ons de fixer la base"))
    parts.append(
        bullets(
            [
                "Org Salesforce vierge (Developer Edition) : aucun composant "
                "m\u00e9tier. Utile pour quantifier la part \u00ab "
                "standard \u00bb d'une org et calibrer le seuil Adopt vs "
                "Adapt.",
                "Org m\u00e9tier fig\u00e9e \u00e0 un instant T (par exemple "
                "le d\u00e9but du programme ou la GA initiale) : c'est la "
                "baseline historique, recommand\u00e9e pour suivre la "
                "trajectoire long terme.",
                "Snapshot Git de la metadata correspondant \u00e0 la version "
                "livr\u00e9e pr\u00e9c\u00e9dente : utile pour mesurer "
                "release N versus release N-1.",
            ]
        )
    )
    parts.append(
        paragraph(
            "Recommandation : choisir UNE baseline historique (option 2 "
            "ou 3) et y rester jusqu'\u00e0 un \u00e9v\u00e9nement majeur "
            "(refonte fonctionnelle, changement de scope, montée de version "
            "majeure). En compl\u00e9ment, conserver la baseline org "
            "vierge (option 1) pour calibrer les seuils."
        )
    )

    parts.append(h2("2.3 Conditions \u00e0 respecter"))
    parts.append(
        bullets(
            [
                "P\u00e9rim\u00e8tre de retrieve identique \u00e0 celui qui "
                "sera utilis\u00e9 pour les releases : m\u00eame package.xml, "
                "m\u00eame ensemble de types m\u00e9tadonn\u00e9es.",
                "Configuration Lucie verrouill\u00e9e : rules.xml, "
                "exclusion.xlsx, poids de scoring, poids Adopt vs Adapt, "
                "seuils, ruleset PMD. Cette configuration est versionn\u00e9e "
                "et plac\u00e9e dans \\\\share\\lucie\\_config\\.",
                "Org / snapshot accessible \u00e0 tous les Tech Leads, au "
                "moins en lecture, ou archiv\u00e9 sous forme de dump "
                "metadata reproductible.",
                "Base produite par un seul op\u00e9rateur (le pilote "
                "outillage), valid\u00e9e en Design Review avant d'\u00eatre "
                "publi\u00e9e officiellement.",
            ]
        )
    )

    parts.append(h2("2.4 Capturer la base avec Lucie"))
    parts.append(
        numbered(
            [
                "V\u00e9rifier que la configuration commune _config/ est "
                "\u00e0 jour (rules.xml, exclusion.xlsx, ruleset PMD, poids).",
                "Faire un retrieve de la metadata de la base (org vierge, "
                "org fig\u00e9e ou checkout d'un tag Git).",
                "Ouvrir Lucie, s\u00e9lectionner ce dossier source.",
                "Choisir le dossier de sortie \\\\share\\lucie\\_baseline\\<date>\\.",
                "Activer les options G\u00e9n\u00e9rer le Data Dictionary "
                "Word et G\u00e9n\u00e9rer le r\u00e9sum\u00e9 Word.",
                "Lancer G\u00e9n\u00e9rer la documentation.",
                "V\u00e9rifier la coh\u00e9rence des indicateurs (rapport "
                "summary.docx) avant de publier.",
                "Verrouiller le dossier en lecture seule et r\u00e9diger un "
                "court README_baseline.md qui d\u00e9crit l'origine de la "
                "metadata, la date du retrieve et la version de la "
                "configuration utilis\u00e9e.",
            ]
        )
    )

    parts.append(h2("2.5 Indicateurs \u00e0 figer dans la base"))
    parts.append(
        paragraph(
            "Une fois la base captur\u00e9e, extraire et figer les "
            "indicateurs suivants (recommand\u00e9 : les recopier dans le "
            "compte rendu de baseline) :"
        )
    )
    parts.append(
        bullets(
            [
                "Score de personnalisation : valeur num\u00e9rique et "
                "niveau.",
                "Score Adopt vs Adapt : valeur num\u00e9rique et niveau.",
                "Findings analyzer : total, ventilation par s\u00e9v\u00e9rit\u00e9, "
                "ventilation par cat\u00e9gorie Trusted / Easy / Adaptable, "
                "top 10 r\u00e8gles d\u00e9clench\u00e9es.",
                "Violations PMD : total, ventilation par priorit\u00e9, "
                "top 10 r\u00e8gles.",
                "Apex : nombre de classes, de triggers, lignes totales, "
                "SOQL/DML totaux, classes avec query_in_loop ou "
                "dml_in_loop.",
                "Flows : nombre total, ventilation par niveau de "
                "complexit\u00e9, profondeur max moyenne, largeur max "
                "moyenne.",
                "Inventaire : objets custom, champs custom, record types, "
                "validation rules, OmniStudio.",
            ]
        )
    )

    parts.append(page_break())

    # ---------- 3. Processus de livraison
    parts.append(h1("3. Processus de livraison des releases"))

    parts.append(h2("3.1 Cycle release type"))
    parts.append(
        paragraph(
            "Le cycle de livraison s'articule g\u00e9n\u00e9ralement en "
            "quatre phases. Le tableau ci-dessous pr\u00e9cise le r\u00f4le "
            "de Lucie \u00e0 chaque phase."
        )
    )
    parts.append(
        table(
            headers=["Phase", "Activit\u00e9 m\u00e9tier", "Activit\u00e9 Lucie"],
            rows=[
                [
                    "Cadrage",
                    "Sprint planning de release, scope d\u00e9fini.",
                    "Relire les indicateurs de la baseline et de la "
                    "release N-1 pour identifier les risques connus.",
                ],
                [
                    "Build",
                    "Sprints, d\u00e9veloppements, revues de code.",
                    "G\u00e9n\u00e9ration hebdomadaire dans le dossier "
                    "Squad pour suivre la d\u00e9rive en continu.",
                ],
                [
                    "Stabilisation",
                    "Release Candidates (RC1, RC2, ...), recettes, "
                    "non-r\u00e9gression.",
                    "G\u00e9n\u00e9ration officielle \u00e0 chaque RC, "
                    "comparaison vs baseline et vs release N-1, revue "
                    "Design Review.",
                ],
                [
                    "GA et hypercare",
                    "Mise en production, monitoring, correctifs.",
                    "G\u00e9n\u00e9ration officielle juste apr\u00e8s la "
                    "GA, archivage en lecture seule, mise \u00e0 jour du "
                    "tableau de bord cumul\u00e9.",
                ],
            ],
            widths=[2200, 5400, 9000],
        )
    )

    parts.append(h2("3.2 R\u00f4les"))
    parts.append(
        bullets(
            [
                "Pilote outillage Lucie : maintient _config/, valide la "
                "baseline, garantit l'invariance des configurations entre "
                "deux releases.",
                "Tech Lead Squad : g\u00e9n\u00e8re la doc de sa Squad, "
                "alimente le tableau comparatif, anime la lecture des "
                "findings dans la Squad.",
                "Squad : traite les findings introduits dans la release, "
                "documente les exceptions, met \u00e0 jour les stories en "
                "cons\u00e9quence.",
                "Manager / Design Review : arbitre les \u00e9carts vs "
                "baseline, valide ou refuse les r\u00e9gressions, autorise "
                "le passage en GA.",
            ]
        )
    )

    parts.append(h2("3.3 Convention de branches et de retrieve"))
    parts.append(
        bullets(
            [
                "Convention de nommage : release/<YYYY.MM> ou "
                "release/<n>.<m>. \u00c0 chaque RC, un tag est pos\u00e9 sur "
                "la branche release.",
                "Au moment du tag GA : retrieve depuis la branche "
                "release tagu\u00e9e (ou depuis l'org de stabilisation), "
                "sortie dans \\\\share\\lucie\\releases\\<release-id>\\GA\\<date>\\.",
                "Toutes les g\u00e9n\u00e9rations Lucie d'une release "
                "sont stock\u00e9es dans le sous-dossier de la release "
                "(RC1, RC2, ..., GA).",
                "La configuration utilis\u00e9e (version de _config/) est "
                "trac\u00e9e dans le README de la release.",
            ]
        )
    )

    parts.append(page_break())

    # ---------- 4. Mesurer les \u00e9volutions
    parts.append(h1("4. Mesurer les \u00e9volutions \u00e0 chaque release"))

    parts.append(h2("4.1 G\u00e9n\u00e9ration officielle d'une release"))
    parts.append(
        numbered(
            [
                "Disposer du retrieve de la metadata correspondant \u00e0 "
                "la release (RC ou GA).",
                "V\u00e9rifier que la configuration utilis\u00e9e est "
                "EXACTEMENT celle de la baseline. Si ce n'est pas le cas : "
                "stop, traiter la diff\u00e9rence dans la section "
                "Gouvernance.",
                "Choisir le dossier de sortie "
                "\\\\share\\lucie\\releases\\<release-id>\\<RCx|GA>\\<date>\\.",
                "Lancer G\u00e9n\u00e9rer la documentation avec les m\u00eames "
                "options de scoring, exclusions, et r\u00e8gles d'analyse.",
                "Stocker le summary.docx, le data_dictionary.docx, l'index "
                "HTML et les Excel.",
                "Mettre \u00e0 jour le fichier de comparaison (cf 4.2).",
            ]
        )
    )

    parts.append(h2("4.2 Tableau comparatif standard"))
    parts.append(
        paragraph(
            "Pour chaque release, alimenter un fichier comparison.xlsx "
            "(ou comparison.md) avec au minimum les indicateurs suivants. "
            "C'est le livrable principal pour le Design Review."
        )
    )
    parts.append(
        table(
            headers=["Indicateur", "Baseline T0", "Release N-1", "Release N", "Delta vs T0", "Statut"],
            rows=[
                ["Score perso (valeur)", "120", "145", "152", "+32", "OK"],
                ["Score perso (niveau)", "Moyen", "Moyen", "Moyen", "stable", "OK"],
                ["Adopt vs Adapt (valeur)", "80", "95", "98", "+18", "Surveiller"],
                ["Adopt vs Adapt (niveau)", "Adapt Low", "Adapt Low", "Adapt Low", "stable", "OK"],
                ["Findings Critical", "0", "1", "0", "0", "OK"],
                ["Findings Major", "12", "14", "11", "-1", "OK"],
                ["Findings Minor", "23", "29", "31", "+8", "Surveiller"],
                ["Violations PMD P1", "0", "0", "1", "+1", "R\u00e9gression"],
                ["Apex query_in_loop", "0", "1", "0", "0", "OK"],
                ["Flows Tr\u00e8s complexes", "1", "2", "2", "+1", "Surveiller"],
            ],
            widths=[3200, 4400, 5600, 6800, 7800, 9000],
        )
    )
    parts.append(
        paragraph(
            "Le statut est calcul\u00e9 selon des seuils discut\u00e9s en "
            "Design Review. Trois \u00e9tats minimum : OK / Surveiller / "
            "R\u00e9gression."
        )
    )

    parts.append(h2("4.3 Crit\u00e8res de r\u00e9ussite et signaux d'alerte"))
    parts.append(h3("Crit\u00e8res de r\u00e9ussite (autorisent le passage en GA)"))
    parts.append(
        bullets(
            [
                "Aucun nouveau finding Critical introduit par la release.",
                "Aucune nouvelle violation PMD de priorit\u00e9 1.",
                "Score Adopt vs Adapt qui n'augmente que dans la limite "
                "autoris\u00e9e par les stories de la release.",
                "Aucune classe sans declaration de partage explicite "
                "introduite.",
                "Pas de nouvelle classe avec query_in_loop ou dml_in_loop.",
                "Pas de nouveau cycle d'appels Apex (r\u00e8gle "
                "APEX-REL-003).",
            ]
        )
    )
    parts.append(h3("Signaux d'alerte (\u00e0 escalader au manager)"))
    parts.append(
        bullets(
            [
                "Tout finding Critical introduit qui n'est pas corrig\u00e9 "
                "avant la GA.",
                "Hausse sup\u00e9rieure \u00e0 X % du score de "
                "personnalisation sans story d'\u00e9volution associ\u00e9e "
                "(seuil X \u00e0 d\u00e9finir avec le Design Review, par "
                "exemple 10 %).",
                "Passage du niveau Adopt vs Adapt \u00e0 un palier "
                "sup\u00e9rieur (Adopt -> Adapt Low, Adapt Low -> Adapt "
                "Medium...).",
                "Apparition d'un Flow Tr\u00e8s complexe non document\u00e9.",
                "Hausse importante du nombre de violations PMD de "
                "priorit\u00e9 1 ou 2.",
            ]
        )
    )

    parts.append(h2("4.4 Rituel de mesure"))
    parts.append(
        bullets(
            [
                "\u00c0 chaque RC : le Tech Lead g\u00e9n\u00e8re la doc, "
                "alimente le comparatif, partage au Design Review au moins "
                "48 h avant la r\u00e9union.",
                "Pendant le Design Review : revue des r\u00e9gressions et "
                "des points \u00ab Surveiller \u00bb. D\u00e9cisions "
                "trac\u00e9es dans le compte rendu en r\u00e9f\u00e9ren\u00e7ant "
                "l'identifiant de r\u00e8gle (par exemple APEX-SEC-001).",
                "\u00c0 la GA : g\u00e9n\u00e9ration officielle, archivage "
                "du dossier en lecture seule, mise \u00e0 jour du tableau "
                "de bord cumul\u00e9 _history/dashboard.xlsx.",
                "Hypercare : g\u00e9n\u00e9ration hebdomadaire pour "
                "d\u00e9tecter les correctifs intrusifs.",
            ]
        )
    )

    parts.append(page_break())

    # ---------- 5. Tableau de bord cumul\u00e9
    parts.append(h1("5. Tableau de bord d'\u00e9volution"))
    parts.append(
        paragraph(
            "Le tableau de bord cumul\u00e9 historise une ligne par "
            "release. Il sert au manager pour piloter la trajectoire de "
            "l'org dans la dur\u00e9e."
        )
    )
    parts.append(
        table(
            headers=["Release", "Date GA", "Score perso", "Adopt/Adapt", "Critical", "Major", "PMD P1"],
            rows=[
                ["Baseline T0", "2026-04-25", "120 (Moyen)", "80 (Adapt Low)", "0", "12", "0"],
                ["release/2026.05", "2026-05-26", "152 (Moyen)", "98 (Adapt Low)", "0", "11", "1"],
                ["release/2026.06", "2026-06-30", "164 (Moyen)", "108 (Adapt Low)", "0", "9", "0"],
                ["release/2026.07", "2026-07-28", "180 (Moyen)", "121 (Adapt Med)", "1", "10", "0"],
            ],
            widths=[2400, 3600, 5000, 6200, 7000, 7800, 9000],
        )
    )
    parts.append(
        bullets(
            [
                "Conserver les 8 \u00e0 10 derni\u00e8res releases visibles, "
                "archiver les autres.",
                "Tracer en plus une courbe du score perso et du score "
                "Adopt vs Adapt (Excel ou outil BI).",
                "Mettre en \u00e9vidence visuellement les passages de "
                "palier (Adopt -> Adapt Low...) car ils refl\u00e8tent un "
                "vrai changement de nature.",
                "Inclure le tableau dans le bilan de fin de programme ou "
                "de release majeure.",
            ]
        )
    )

    parts.append(page_break())

    # ---------- 6. Gouvernance
    parts.append(h1("6. Gouvernance et bonnes pratiques"))

    parts.append(h2("6.1 Invariance de la configuration"))
    parts.append(
        bullets(
            [
                "Ne pas modifier rules.xml, exclusion.xlsx, les poids de "
                "scoring ou le ruleset PMD entre deux releases sans "
                "rebaseliner.",
                "Si une r\u00e8gle est ajout\u00e9e, modifi\u00e9e ou "
                "d\u00e9sactiv\u00e9e : produire deux baselines "
                "(avant / apr\u00e8s) et les conserver toutes les deux pour "
                "garantir la tra\u00e7abilit\u00e9.",
                "La version de _config/ utilis\u00e9e est inscrite dans le "
                "README de chaque g\u00e9n\u00e9ration (commit hash ou date).",
            ]
        )
    )

    parts.append(h2("6.2 Tra\u00e7abilit\u00e9 des d\u00e9cisions"))
    parts.append(
        bullets(
            [
                "Toute exception (finding accept\u00e9) est consign\u00e9e "
                "dans decisions/<release-id>-decisions.md, en r\u00e9f\u00e9ren\u00e7ant "
                "l'identifiant de r\u00e8gle.",
                "Pas de modification de exclusion.xlsx pour masquer un "
                "probl\u00e8me sans validation Design Review formelle.",
                "Le compte rendu de Design Review est archiv\u00e9 dans "
                "design-review/<date>-CR.docx, \u00e0 c\u00f4t\u00e9 du "
                "dossier de la release.",
            ]
        )
    )

    parts.append(h2("6.3 Quand rebaseliner ?"))
    parts.append(
        bullets(
            [
                "Refonte fonctionnelle majeure (nouveau module, nouvelle "
                "ligne m\u00e9tier).",
                "Changement de scope du retrieve (nouveaux types "
                "metadata).",
                "\u00c9volution des r\u00e8gles d'analyse ou des poids de "
                "scoring valid\u00e9e par le Design Review.",
                "Changement d'org de r\u00e9f\u00e9rence (par exemple "
                "passage \u00e0 une nouvelle GA initiale apr\u00e8s un "
                "go-live majeur).",
            ]
        )
    )
    parts.append(
        quote(
            "R\u00e8gle d'or : on ne rebaseline JAMAIS pour faire "
            "dispara\u00eetre une r\u00e9gression. Une r\u00e9gression doit "
            "\u00eatre corrig\u00e9e ou explicitement accept\u00e9e en "
            "Design Review."
        )
    )

    parts.append(page_break())

    # ---------- 7. Annexes
    parts.append(h1("7. Annexes"))

    parts.append(h2("7.1 Arborescence type du r\u00e9pertoire commun"))
    parts.append(
        code_block(
            [
                "\\\\share\\lucie\\",
                "+-- _config\\",
                "|   +-- exclusion.xlsx",
                "|   +-- rules.xml",
                "|   +-- pmd_ruleset.xml",
                "|   +-- weights.json",
                "+-- _baseline\\",
                "|   +-- 2026-04-25\\",
                "|       +-- index.html",
                "|       +-- excel\\...",
                "|       +-- word\\summary.docx",
                "|       +-- word\\data_dictionary.docx",
                "|       +-- README_baseline.md",
                "+-- releases\\",
                "|   +-- release-2026.05\\",
                "|   |   +-- RC1\\2026-05-12\\...",
                "|   |   +-- RC2\\2026-05-19\\...",
                "|   |   +-- GA\\2026-05-26\\...",
                "|   |   +-- comparison.xlsx",
                "|   +-- release-2026.06\\",
                "+-- _history\\",
                "|   +-- dashboard.xlsx",
                "+-- decisions\\",
                "|   +-- release-2026.05-decisions.md",
                "+-- design-review\\",
                "    +-- 2026-05-12-CR.docx",
                "    +-- 2026-05-26-CR.docx",
            ]
        )
    )

    parts.append(h2("7.2 Cycle complet de mesure (vue synth\u00e9tique)"))
    parts.append(
        numbered(
            [
                "Pilote outillage : produit la baseline T0 et la publie.",
                "Tech Lead : g\u00e9n\u00e8re la doc \u00e0 chaque RC dans "
                "le dossier de la release.",
                "Tech Lead : alimente comparison.xlsx (T0, N-1, N).",
                "Manager : convoque le Design Review avec le summary.docx "
                "et le comparatif.",
                "Design Review : valide ou refuse les \u00e9carts vs "
                "baseline.",
                "Squad : corrige avant GA ou documente l'exception.",
                "GA : g\u00e9n\u00e9ration officielle archiv\u00e9e en "
                "lecture seule, dashboard cumul\u00e9 mis \u00e0 jour.",
                "Hypercare : g\u00e9n\u00e9rations hebdomadaires pour "
                "surveiller les correctifs.",
            ]
        )
    )

    parts.append(h2("7.3 Check-list rapide pour le Tech Lead"))
    parts.append(
        bullets(
            [
                "Configuration _config/ \u00e0 la m\u00eame version que la "
                "baseline ? oui / non",
                "Retrieve sur le bon p\u00e9rim\u00e8tre ? oui / non",
                "Sortie dans le bon sous-dossier de la release ? oui / non",
                "comparison.xlsx \u00e0 jour avec T0, N-1 et N ? oui / non",
                "Aucun nouveau Critical / nouveau PMD P1 ? oui / non",
                "Compte rendu Design Review pr\u00e9par\u00e9 avec les "
                "actions ? oui / non",
            ]
        )
    )

    return build_document(parts)


def main() -> None:
    here = Path(__file__).resolve().parent
    fr_path = here / "baseline_evolution_fr.rtf"
    fr_path.write_text(french_document(), encoding="cp1252", errors="replace")
    print("Wrote", fr_path)


if __name__ == "__main__":
    main()
