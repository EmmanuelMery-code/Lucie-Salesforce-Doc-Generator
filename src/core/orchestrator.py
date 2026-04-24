from __future__ import annotations

from pathlib import Path

from src.analyzer.engine import AnalyzerEngine
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import PmdViolation
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.core.pmd_service import PmdService
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.html_writer import HtmlReportWriter
from src.reviewers.heuristics import review_apex_artifact, review_flow


class SalesforceDocumentationGenerator:
    def __init__(
        self,
        source_dir: str | Path,
        output_dir: str | Path,
        exclusion_config_path: str | Path | None = None,
        pmd_enabled: bool = False,
        pmd_ruleset_path: str | Path | None = None,
        generate_excels: bool = True,
        scoring_weights: dict[str, int] | None = None,
        adopt_adapt_weights: dict[str, int] | None = None,
        analyzer_rules_path: str | Path | None = None,
        log_callback=None,
    ) -> None:
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.exclusion_config_path = (
            Path(exclusion_config_path).resolve() if exclusion_config_path else None
        )
        self.pmd_enabled = pmd_enabled
        self.pmd_ruleset_path = Path(pmd_ruleset_path).resolve() if pmd_ruleset_path else None
        self.generate_excels = generate_excels
        self.scoring_weights = scoring_weights
        self.adopt_adapt_weights = adopt_adapt_weights
        self.analyzer_rules_path = (
            Path(analyzer_rules_path).resolve() if analyzer_rules_path else None
        )
        self.log = log_callback or (lambda message: None)

    def _safe_excel(self, label: str, producer):
        try:
            return producer()
        except Exception as exc:
            self.log(f"Echec generation {label}: {exc}")
            return None

    def generate(self) -> dict[str, object]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log("Debut de l'analyse Salesforce.")

        parser = SalesforceMetadataParser(
            self.source_dir,
            exclusion_config_path=self.exclusion_config_path,
            log_callback=self.log,
        )
        snapshot = parser.parse()
        if self.scoring_weights:
            snapshot.metrics.weights = dict(self.scoring_weights)
        if self.adopt_adapt_weights:
            snapshot.metrics.adopt_adapt_weights = dict(self.adopt_adapt_weights)
        self.log("Lecture des metadata terminee.")

        excel_writer = ExcelReportWriter(log_callback=self.log)
        excel_dir = self.output_dir / "excel"

        permission_excel = None
        profile_excel = None
        inventory_excel = None
        data_dictionary_excels: list = []
        if self.generate_excels:
            self.log("Generation des classeurs Excel de documentation.")
            permission_excel = self._safe_excel(
                "permission_sets.xlsx",
                lambda: excel_writer.write_security_workbook(
                    snapshot.permission_sets,
                    excel_dir / "permission_sets.xlsx",
                    "Classeur Permission Sets",
                ),
            )
            profile_excel = self._safe_excel(
                "profiles.xlsx",
                lambda: excel_writer.write_security_workbook(
                    snapshot.profiles,
                    excel_dir / "profiles.xlsx",
                    "Classeur Profiles",
                ),
            )
            inventory_excel = self._safe_excel(
                "metadata_inventory.xlsx",
                lambda: excel_writer.write_inventory_workbook(
                    snapshot.inventory,
                    excel_dir / "metadata_inventory.xlsx",
                ),
            )
            data_dictionary_excels = self._safe_excel(
                "data_dictionary.xlsx",
                lambda: excel_writer.write_data_dictionary_workbooks(
                    snapshot.objects,
                    excel_dir,
                ),
            ) or []
        else:
            self.log("Generation des Excels desactivee dans la configuration.")

        html_writer = HtmlReportWriter(self.output_dir, log_callback=self.log)
        html_writer.write_assets()

        apex_reviews = {artifact.name: review_apex_artifact(artifact) for artifact in snapshot.apex_artifacts}
        flow_reviews = {flow.name: review_flow(flow) for flow in snapshot.flows}
        pmd_by_artifact: dict[str, list[PmdViolation]] = {
            artifact.name: [] for artifact in snapshot.apex_artifacts
        }
        pmd_excel = None
        if self.pmd_enabled:
            pmd_service = PmdService(self.source_dir, log_callback=self.log)
            pmd_result = pmd_service.analyze_apex(
                snapshot.apex_artifacts,
                ruleset_path=self.pmd_ruleset_path,
            )
            for violation in pmd_result.violations:
                for artifact in snapshot.apex_artifacts:
                    if artifact.source_path.resolve() == violation.file_path.resolve():
                        pmd_by_artifact.setdefault(artifact.name, []).append(violation)
                        break
            if self.generate_excels:
                pmd_excel = self._safe_excel(
                    "pmd_violations.xlsx",
                    lambda: excel_writer.write_pmd_workbook(
                        pmd_by_artifact,
                        excel_dir / "pmd_violations.xlsx",
                    ),
                )

        self.log("Chargement du catalogue de regles analyzer.")
        analyzer_catalog = RuleCatalog.load(self.analyzer_rules_path)
        enabled_count = len(analyzer_catalog.enabled)
        total_count = len(analyzer_catalog.all)
        self.log(
            f"Catalogue analyzer : {enabled_count}/{total_count} regles actives."
        )
        analyzer_engine = AnalyzerEngine(analyzer_catalog)
        analyzer_report = analyzer_engine.analyze_snapshot(snapshot)
        finding_total = len(analyzer_report.all_findings())
        self.log(f"Analyseur : {finding_total} finding(s) detecte(s).")

        object_pages = html_writer.write_object_pages(
            snapshot, analyzer_report=analyzer_report
        )
        apex_pages = html_writer.write_apex_pages(
            snapshot, apex_reviews, pmd_by_artifact, analyzer_report=analyzer_report
        )
        flow_pages = html_writer.write_flow_pages(
            snapshot,
            flow_reviews,
            object_pages,
            apex_pages,
            analyzer_report=analyzer_report,
        )
        omni_pages = html_writer.write_omni_pages(
            snapshot, analyzer_report=analyzer_report
        )
        excel_preview_pages = html_writer.write_excel_preview_pages()
        index_path = html_writer.write_index(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_by_artifact,
            omni_pages=omni_pages,
            analyzer_report=analyzer_report,
        )

        self.log("Generation terminee.")
        return {
            "snapshot": snapshot,
            "permission_excel": permission_excel,
            "profile_excel": profile_excel,
            "inventory_excel": inventory_excel,
            "data_dictionary_excels": data_dictionary_excels,
            "pmd_excel": pmd_excel,
            "index": index_path,
            "object_pages": object_pages,
            "apex_pages": apex_pages,
            "flow_pages": flow_pages,
            "omni_pages": omni_pages,
            "excel_preview_pages": excel_preview_pages,
            "analyzer_report": analyzer_report,
        }
