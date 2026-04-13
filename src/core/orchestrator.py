from __future__ import annotations

from pathlib import Path

from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.html_writer import HtmlReportWriter
from src.reviewers.heuristics import review_apex_artifact, review_flow


class SalesforceDocumentationGenerator:
    def __init__(
        self,
        source_dir: str | Path,
        output_dir: str | Path,
        exclusion_config_path: str | Path | None = None,
        log_callback=None,
    ) -> None:
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.exclusion_config_path = (
            Path(exclusion_config_path).resolve() if exclusion_config_path else None
        )
        self.log = log_callback or (lambda message: None)

    def generate(self) -> dict[str, object]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log("Debut de l'analyse Salesforce.")

        parser = SalesforceMetadataParser(
            self.source_dir,
            exclusion_config_path=self.exclusion_config_path,
            log_callback=self.log,
        )
        snapshot = parser.parse()
        self.log("Lecture des metadata terminee.")

        excel_writer = ExcelReportWriter(log_callback=self.log)
        excel_dir = self.output_dir / "excel"
        permission_excel = excel_writer.write_security_workbook(
            snapshot.permission_sets,
            excel_dir / "permission_sets.xlsx",
            "Classeur Permission Sets",
        )
        profile_excel = excel_writer.write_security_workbook(
            snapshot.profiles,
            excel_dir / "profiles.xlsx",
            "Classeur Profiles",
        )
        inventory_excel = excel_writer.write_inventory_workbook(
            snapshot.inventory,
            excel_dir / "metadata_inventory.xlsx",
        )

        html_writer = HtmlReportWriter(self.output_dir, log_callback=self.log)
        html_writer.write_assets()

        apex_reviews = {artifact.name: review_apex_artifact(artifact) for artifact in snapshot.apex_artifacts}
        flow_reviews = {flow.name: review_flow(flow) for flow in snapshot.flows}

        object_pages = html_writer.write_object_pages(snapshot)
        apex_pages = html_writer.write_apex_pages(snapshot, apex_reviews)
        flow_pages = html_writer.write_flow_pages(snapshot, flow_reviews, object_pages, apex_pages)
        index_path = html_writer.write_index(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            apex_reviews,
            flow_reviews,
        )

        self.log("Generation terminee.")
        return {
            "snapshot": snapshot,
            "permission_excel": permission_excel,
            "profile_excel": profile_excel,
            "inventory_excel": inventory_excel,
            "index": index_path,
            "object_pages": object_pages,
            "apex_pages": apex_pages,
            "flow_pages": flow_pages,
        }
