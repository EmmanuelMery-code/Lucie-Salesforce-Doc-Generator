"""Smoke test for the customisation/adoption metrics on the badPattern snapshot.

Run with::

    python -m process._smoke_customisation_metrics

The script parses the ``badPattern/retrieveAfter`` snapshot, computes both
:class:`DataModelCustomisationStats` and :class:`AdoptionStats`, and
prints a human-readable summary so we can sanity-check the values
without launching the full Tk UI / HTML pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.customization_metrics import (
    CAPABILITY_CATALOG,
    compute_adoption_stats,
    compute_data_model_stats,
)
from src.parsers.salesforce_parser import SalesforceMetadataParser

SNAPSHOT = ROOT / "Bad Pattern20260425" / "retrieveAfter"


def main() -> int:
    if not SNAPSHOT.exists():
        print(f"Snapshot introuvable : {SNAPSHOT}", file=sys.stderr)
        return 1

    parser = SalesforceMetadataParser(SNAPSHOT)
    snapshot = parser.parse()

    dm = compute_data_model_stats(snapshot)
    print("=== Empreinte data model ===")
    print(
        f"Objets   : {dm.custom_objects} custom / {dm.standard_objects} standard "
        f"(% custom = {dm.percent_custom_objects:.1f} %)"
    )
    print(
        f"Champs   : {dm.custom_fields} custom / {dm.standard_fields} standard "
        f"(% custom = {dm.percent_custom_fields:.1f} %)"
    )
    print(
        f"Global   : custom = {dm.percent_custom_global:.1f} %, "
        f"standard = {dm.percent_standard_global:.1f} %"
    )

    adoption = compute_adoption_stats(snapshot)
    print()
    print("=== Posture Adopt vs Adapt ===")
    print(
        f"Adoption    : {adoption.percent_adoption:.1f} % "
        f"({adoption.adopt_count}/{adoption.total_count} capacites, "
        f"poids {adoption.adopt_weight}/{adoption.total_weight})"
    )
    print(
        f"Adaptation  : {adoption.percent_adaptation:.1f} % "
        f"(low {adoption.adapt_low_count} / high {adoption.adapt_high_count})"
    )
    print()
    print("Capacites :")
    by_id = {a.capability_id: a for a in adoption.assessments}
    for definition in CAPABILITY_CATALOG:
        a = by_id.get(definition.capability_id)
        if a is None:
            continue
        print(f"  - {a.label} (poids {a.weight}) : {a.level.value}")
        for ev in a.evidence:
            print(f"      . {ev}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
