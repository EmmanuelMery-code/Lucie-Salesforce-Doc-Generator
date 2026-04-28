"""Orchestrate metadata parsing, analysis, and report generation.

The :class:`SalesforceDocumentationGenerator` glues the parsers, analyzers
and writers together. It takes user configuration (output flags, language,
weights, exclusion files) and returns a fully populated
:class:`GenerationResult` so callers can introspect what was produced
without poking at a stringly-typed dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.analyzer.engine import AnalyzerEngine, AnalyzerReport
from src.analyzer.rule_catalog import RuleCatalog
from src.core.ai_usage import (
    AIUsageEntry,
    AIUsageStats,
    compute_ai_usage_stats,
    scan_ai_usage,
)
from src.core.customization_metrics import (
    AdoptionStats,
    DataModelCustomisationStats,
    PostureCapabilityConfig,
    compute_adoption_stats,
    compute_data_model_stats,
)
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import MetadataSnapshot, PmdViolation
from src.core.pmd_service import PmdService
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.html_writer import HtmlReportWriter
from src.reporting.word_writer import WordReportWriter
from src.reviewers.heuristics import review_apex_artifact, review_flow

LogCallback = Callable[[str], None]


@dataclass
class GenerationResult:
    """Structured payload returned by :meth:`SalesforceDocumentationGenerator.generate`.

    Every field is optional because the user can disable individual outputs
    (Excel, HTML, Word). Callers should check for ``None`` / empty mappings
    before reading.
    """

    snapshot: MetadataSnapshot | None = None
    analyzer_report: AnalyzerReport | None = None
    permission_excel: Path | None = None
    profile_excel: Path | None = None
    inventory_excel: Path | None = None
    data_dictionary_excels: list[Path] = field(default_factory=list)
    pmd_excel: Path | None = None
    data_dictionary_word: Path | None = None
    summary_word: Path | None = None
    index: Path | None = None
    ai_usage_page: Path | None = None
    ai_usage_entries: list[AIUsageEntry] = field(default_factory=list)
    ai_usage_stats: AIUsageStats | None = None
    data_model_stats: DataModelCustomisationStats | None = None
    adoption_stats: AdoptionStats | None = None
    customisation_page: Path | None = None
    adoption_page: Path | None = None
    object_pages: dict = field(default_factory=dict)
    apex_pages: dict = field(default_factory=dict)
    flow_pages: dict = field(default_factory=dict)
    omni_pages: dict = field(default_factory=dict)
    excel_preview_pages: dict = field(default_factory=dict)

    # The UI historically consumed this object via ``result["index"]``-style
    # subscripts. The two helpers below keep that contract working without
    # forcing every existing call site to migrate at once.
    def __getitem__(self, item: str):
        return getattr(self, item)

    def get(self, item: str, default=None):
        return getattr(self, item, default)


class SalesforceDocumentationGenerator:
    """High-level entry point that produces every report from a metadata folder."""

    def __init__(
        self,
        source_dir: str | Path,
        output_dir: str | Path,
        exclusion_config_path: str | Path | None = None,
        pmd_enabled: bool = False,
        pmd_ruleset_path: str | Path | None = None,
        generate_excels: bool = True,
        generate_html: bool = True,
        generate_data_dictionary_word: bool = True,
        generate_summary_word: bool = True,
        scoring_weights: dict[str, int] | None = None,
        adopt_adapt_weights: dict[str, int] | None = None,
        scoring_thresholds: tuple[int, int, int] | None = None,
        adopt_adapt_thresholds: tuple[int, int, int] | None = None,
        analyzer_rules_path: str | Path | None = None,
        ai_usage_tags: list[str] | tuple[str, ...] | None = None,
        posture_config: list[PostureCapabilityConfig] | None = None,
        index_card_visibility: IndexCardVisibility | None = None,
        language: str = "fr",
        log_callback: LogCallback | None = None,
    ) -> None:
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.exclusion_config_path = (
            Path(exclusion_config_path).resolve() if exclusion_config_path else None
        )
        self.pmd_enabled = pmd_enabled
        self.pmd_ruleset_path = (
            Path(pmd_ruleset_path).resolve() if pmd_ruleset_path else None
        )
        self.generate_excels = generate_excels
        self.generate_html = generate_html
        self.generate_data_dictionary_word = generate_data_dictionary_word
        self.generate_summary_word = generate_summary_word
        self.scoring_weights = scoring_weights
        self.adopt_adapt_weights = adopt_adapt_weights
        self.scoring_thresholds = scoring_thresholds
        self.adopt_adapt_thresholds = adopt_adapt_thresholds
        self.analyzer_rules_path = (
            Path(analyzer_rules_path).resolve() if analyzer_rules_path else None
        )
        self.ai_usage_tags: list[str] = [
            tag.strip()
            for tag in (ai_usage_tags or [])
            if isinstance(tag, str) and tag.strip()
        ]
        self.posture_config: list[PostureCapabilityConfig] = list(posture_config or [])
        self.index_card_visibility: IndexCardVisibility = (
            index_card_visibility
            if index_card_visibility is not None
            else IndexCardVisibility()
        )
        # Language drives the localisation of the Word documents we generate
        # (data dictionary + summary). Falls back to French if the value is
        # not one of the supported codes.
        self.language = language if language in {"fr", "en"} else "fr"
        self.log: LogCallback = log_callback or (lambda message: None)

    # ------------------------------------------------------------------
    # Safe wrappers
    # ------------------------------------------------------------------

    def _safe_run(self, label: str, producer: Callable[[], object]) -> object | None:
        """Run ``producer`` and surface any failure via the log callback.

        Used to isolate Excel/Word writer failures so a single broken
        artefact does not abort the whole generation.
        """

        try:
            return producer()
        except Exception as exc:
            self.log(f"Echec generation {label}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _generate_excels(
        self,
        snapshot: MetadataSnapshot,
        excel_writer: ExcelReportWriter,
        excel_dir: Path,
        result: GenerationResult,
    ) -> None:
        self.log("Generation des classeurs Excel de documentation.")
        result.permission_excel = self._safe_run(
            "permission_sets.xlsx",
            lambda: excel_writer.write_security_workbook(
                snapshot.permission_sets,
                excel_dir / "permission_sets.xlsx",
                "Classeur Permission Sets",
            ),
        )
        result.profile_excel = self._safe_run(
            "profiles.xlsx",
            lambda: excel_writer.write_security_workbook(
                snapshot.profiles,
                excel_dir / "profiles.xlsx",
                "Classeur Profiles",
            ),
        )
        result.inventory_excel = self._safe_run(
            "metadata_inventory.xlsx",
            lambda: excel_writer.write_inventory_workbook(
                snapshot.inventory,
                excel_dir / "metadata_inventory.xlsx",
            ),
        )
        result.data_dictionary_excels = (
            self._safe_run(
                "data_dictionary.xlsx",
                lambda: excel_writer.write_data_dictionary_workbooks(
                    snapshot.objects, excel_dir
                ),
            )
            or []
        )

    def _run_pmd(
        self,
        snapshot: MetadataSnapshot,
        excel_writer: ExcelReportWriter,
        excel_dir: Path,
        result: GenerationResult,
        pmd_by_artifact: dict[str, list[PmdViolation]],
    ) -> None:
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
            result.pmd_excel = self._safe_run(
                "pmd_violations.xlsx",
                lambda: excel_writer.write_pmd_workbook(
                    pmd_by_artifact,
                    excel_dir / "pmd_violations.xlsx",
                ),
            )

    def _generate_word(
        self,
        snapshot: MetadataSnapshot,
        analyzer_report: AnalyzerReport,
        result: GenerationResult,
    ) -> None:
        if not (self.generate_data_dictionary_word or self.generate_summary_word):
            self.log("Generation des documents Word desactivee.")
            return

        word_dir = self.output_dir / "word"
        word_writer = WordReportWriter(language=self.language, log_callback=self.log)

        if self.generate_data_dictionary_word:
            result.data_dictionary_word = self._safe_run(
                "data_dictionary.docx",
                lambda: word_writer.write_data_dictionary_document(
                    snapshot, word_dir / "data_dictionary.docx"
                ),
            )
        else:
            self.log("Generation du Data Dictionary Word desactivee.")

        if self.generate_summary_word:
            result.summary_word = self._safe_run(
                "summary.docx",
                lambda: word_writer.write_summary_document(
                    snapshot, analyzer_report, word_dir / "summary.docx"
                ),
            )
        else:
            self.log("Generation du resume Word desactivee.")

    def _generate_html(
        self,
        snapshot: MetadataSnapshot,
        analyzer_report: AnalyzerReport,
        apex_reviews: dict,
        flow_reviews: dict,
        pmd_by_artifact: dict[str, list[PmdViolation]],
        result: GenerationResult,
    ) -> None:
        html_writer = HtmlReportWriter(self.output_dir, log_callback=self.log)
        html_writer.write_assets()

        result.object_pages = html_writer.write_object_pages(
            snapshot, analyzer_report=analyzer_report
        )
        result.apex_pages = html_writer.write_apex_pages(
            snapshot,
            apex_reviews,
            pmd_by_artifact,
            analyzer_report=analyzer_report,
        )
        result.flow_pages = html_writer.write_flow_pages(
            snapshot,
            flow_reviews,
            result.object_pages,
            result.apex_pages,
            analyzer_report=analyzer_report,
        )
        result.omni_pages = html_writer.write_omni_pages(
            snapshot, analyzer_report=analyzer_report
        )
        result.excel_preview_pages = html_writer.write_excel_preview_pages()
        result.ai_usage_page = html_writer.write_ai_usage_page(
            result.ai_usage_entries,
            tags=self.ai_usage_tags,
            stats=result.ai_usage_stats,
        )
        result.customisation_page = html_writer.write_customisation_page(
            snapshot, result.data_model_stats
        )
        result.adoption_page = html_writer.write_adoption_page(
            snapshot, result.adoption_stats
        )
        result.index = html_writer.write_index(
            snapshot,
            result.object_pages,
            result.apex_pages,
            result.flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_by_artifact,
            omni_pages=result.omni_pages,
            analyzer_report=analyzer_report,
            ai_usage_entries=result.ai_usage_entries,
            ai_usage_page=result.ai_usage_page,
            ai_usage_stats=result.ai_usage_stats,
            data_model_stats=result.data_model_stats,
            adoption_stats=result.adoption_stats,
            customisation_page=result.customisation_page,
            adoption_page=result.adoption_page,
            card_visibility=self.index_card_visibility,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self) -> GenerationResult:
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
        if self.scoring_thresholds:
            snapshot.metrics.scoring_thresholds = tuple(self.scoring_thresholds)
        if self.adopt_adapt_thresholds:
            snapshot.metrics.adopt_adapt_thresholds = tuple(self.adopt_adapt_thresholds)
        self.log("Lecture des metadata terminee.")

        result = GenerationResult(snapshot=snapshot)

        excel_writer = ExcelReportWriter(log_callback=self.log)
        excel_dir = self.output_dir / "excel"

        if self.generate_excels:
            self._generate_excels(snapshot, excel_writer, excel_dir, result)
        else:
            self.log("Generation des Excels desactivee dans la configuration.")

        if not self.generate_html:
            self.log("Generation HTML desactivee dans la configuration.")

        apex_reviews = {
            artifact.name: review_apex_artifact(artifact)
            for artifact in snapshot.apex_artifacts
        }
        flow_reviews = {flow.name: review_flow(flow) for flow in snapshot.flows}
        pmd_by_artifact: dict[str, list[PmdViolation]] = {
            artifact.name: [] for artifact in snapshot.apex_artifacts
        }

        if self.pmd_enabled:
            self._run_pmd(
                snapshot, excel_writer, excel_dir, result, pmd_by_artifact
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
        result.analyzer_report = analyzer_report
        self.log(
            f"Analyseur : {len(analyzer_report.all_findings())} finding(s) detecte(s)."
        )

        if self.ai_usage_tags:
            result.ai_usage_entries = scan_ai_usage(snapshot, self.ai_usage_tags)
            self.log(
                "Usage IA : "
                f"{len(result.ai_usage_entries)} occurrence(s) de tag detectee(s) "
                f"(tags suivis : {', '.join(self.ai_usage_tags)})."
            )
        else:
            result.ai_usage_entries = []
            self.log("Usage IA : aucun tag configure, evaluation par defaut (0 tagge).")

        result.ai_usage_stats = compute_ai_usage_stats(
            snapshot, result.ai_usage_entries
        )
        stats = result.ai_usage_stats
        self.log(
            "Univers personnalisation/code/lowcode : "
            f"{stats.total} element(s), "
            f"avec tag IA = {stats.with_tag_count} ({stats.percent_with_tag:.1f} %), "
            f"sans tag IA = {stats.without_tag_count} ({stats.percent_without_tag:.1f} %)."
        )

        result.data_model_stats = compute_data_model_stats(snapshot)
        dm_stats = result.data_model_stats
        self.log(
            "Empreinte data model : "
            f"objets custom = {dm_stats.custom_objects}/{dm_stats.total_objects} "
            f"({dm_stats.percent_custom_objects:.1f} %), "
            f"champs custom = {dm_stats.custom_fields}/{dm_stats.total_fields} "
            f"({dm_stats.percent_custom_fields:.1f} %), "
            f"global custom = {dm_stats.percent_custom_global:.1f} %."
        )

        result.adoption_stats = compute_adoption_stats(
            snapshot, self.posture_config or None
        )
        adoption = result.adoption_stats
        self.log(
            "Posture Adopt vs Adapt : "
            f"adoption = {adoption.percent_adoption:.1f} % "
            f"({adoption.adopt_count}/{adoption.total_count} capacites), "
            f"adaptation = {adoption.percent_adaptation:.1f} % "
            f"(low {adoption.adapt_low_count}, high {adoption.adapt_high_count})."
        )

        self._generate_word(snapshot, analyzer_report, result)

        if self.generate_html:
            self._generate_html(
                snapshot,
                analyzer_report,
                apex_reviews,
                flow_reviews,
                pmd_by_artifact,
                result,
            )

        self.log("Generation terminee.")
        return result
