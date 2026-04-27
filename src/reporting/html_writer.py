"""Public facade over the ``src.reporting.html`` package.

The orchestrator instantiates :class:`HtmlReportWriter` and calls a handful
of ``write_*`` methods. Historically all of the rendering logic lived in
this module (~2,100 lines mixing CSS, JS runtimes, Mermaid helpers,
dependency analysis and per-page renderers). It has now been split into
the focused modules under ``src.reporting.html``; this file simply
forwards the public API so existing callers keep working unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.ai_usage import AIUsageEntry, AIUsageStats
from src.core.models import (
    MetadataSnapshot,
    PmdViolation,
    ReviewResult,
)

from src.reporting.html import assets
from src.reporting.html.renderers import (
    ai_usage as ai_usage_renderer,
    apex as apex_renderer,
    excel_preview as excel_preview_renderer,
    flows as flows_renderer,
    index as index_renderer,
    objects as objects_renderer,
    omni as omni_renderer,
)


LogCallback = Callable[[str], None]


class HtmlReportWriter:
    """Write the static HTML documentation site.

    The class owns the shared output directory layout (``assets/``,
    ``objects/``, ``apex/``, ``flows/``, ``omni/``) and exposes a small
    set of ``write_*`` methods that emit one HTML page per
    object/class/trigger/flow/Omni component plus the home page. Every
    method delegates to a focused renderer module under
    ``src.reporting.html``; this class only wires paths and log callback
    together.
    """

    def __init__(
        self,
        output_dir: str | Path,
        log_callback: LogCallback | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.log: LogCallback = log_callback or (lambda message: None)
        self.assets_dir = self.output_dir / "assets"
        self.objects_dir = self.output_dir / "objects"
        self.apex_dir = self.output_dir / "apex"
        self.flows_dir = self.output_dir / "flows"
        self.omni_dir = self.output_dir / "omni"

    def write_assets(self) -> None:
        assets.write_assets(self.assets_dir)

    def write_object_pages(
        self,
        snapshot: MetadataSnapshot,
        *,
        analyzer_report=None,
    ) -> dict[str, Path]:
        return objects_renderer.write_object_pages(
            snapshot,
            self.objects_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_apex_pages(
        self,
        snapshot: MetadataSnapshot,
        reviews: dict[str, ReviewResult],
        pmd_results: dict[str, list[PmdViolation]],
        *,
        analyzer_report=None,
    ) -> dict[str, Path]:
        return apex_renderer.write_apex_pages(
            snapshot,
            reviews,
            pmd_results,
            self.apex_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_flow_pages(
        self,
        snapshot: MetadataSnapshot,
        reviews: dict[str, ReviewResult],
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        *,
        analyzer_report=None,
    ) -> dict[str, Path]:
        return flows_renderer.write_flow_pages(
            snapshot,
            reviews,
            object_pages,
            apex_pages,
            self.flows_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_omni_pages(
        self,
        snapshot: MetadataSnapshot,
        *,
        analyzer_report=None,
    ) -> dict[str, list[dict[str, object]]]:
        return omni_renderer.write_omni_pages(
            snapshot,
            self.omni_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_excel_preview_pages(self) -> dict[Path, Path]:
        return excel_preview_renderer.write_excel_preview_pages(
            self.output_dir,
            self.assets_dir,
            self.log,
        )

    def write_ai_usage_page(
        self,
        entries: list[AIUsageEntry],
        *,
        tags: list[str] | None = None,
        stats: AIUsageStats | None = None,
    ) -> Path:
        return ai_usage_renderer.write_ai_usage_page(
            entries,
            self.output_dir,
            self.assets_dir,
            self.log,
            tags=tags,
            stats=stats,
        )

    def write_index(
        self,
        snapshot: MetadataSnapshot,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
        apex_reviews: dict[str, ReviewResult],
        flow_reviews: dict[str, ReviewResult],
        pmd_results: dict[str, list[PmdViolation]],
        omni_pages: dict[str, list[dict[str, object]]] | None = None,
        *,
        analyzer_report=None,
        ai_usage_entries: list[AIUsageEntry] | None = None,
        ai_usage_page: Path | None = None,
        ai_usage_stats: AIUsageStats | None = None,
    ) -> Path:
        return index_renderer.write_index(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_results,
            self.output_dir,
            self.assets_dir,
            self.log,
            omni_pages=omni_pages,
            analyzer_report=analyzer_report,
            ai_usage_entries=ai_usage_entries,
            ai_usage_page=ai_usage_page,
            ai_usage_stats=ai_usage_stats,
        )
