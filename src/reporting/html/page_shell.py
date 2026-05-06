"""Reusable HTML shell helpers shared by every page renderer.

Provides the page envelope (``<!DOCTYPE html>`` + head + body), the tabbed
section widget, and the URL helpers used to build relative links between
pages and anchors on the index.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.core.utils import html_value, safe_slug

from src.reporting.html.assets import MERMAID_RUNTIME_SCRIPT, TABS_SCRIPT


def href_relative(from_path: Path, to_path: Path) -> str:
    """Compute a forward-slash relative URL from ``from_path`` to ``to_path``."""

    return Path(os.path.relpath(to_path, from_path.parent)).as_posix()


def index_href(
    from_path: Path,
    output_dir: Path,
    tab_slug: str | None = None,
) -> str:
    """Return the URL of the documentation index, optionally with an anchor."""

    href = href_relative(from_path, output_dir / "index.html")
    if tab_slug:
        return f"{href}#index-panel-{tab_slug}"
    return href


def index_back_link(
    from_path: Path,
    output_dir: Path,
    tab_slug: str | None = None,
) -> str:
    """Render the standard "back to index" navigation link."""

    href = index_href(from_path, output_dir, tab_slug)
    return f"<div class=\"topnav\"><a href=\"{href}\">Retour a l'index</a></div>"


def tabbed_sections(group_id: str, sections: list[tuple[str, str]]) -> str:
    """Render a tabbed widget grouping ``sections`` (label, html) tuples.

    The tab slugs are derived from the labels and disambiguated when they
    collide so two sections with the same label still get unique anchors.
    """

    button_html: list[str] = []
    panel_html: list[str] = []
    used_slugs: set[str] = set()
    for index, (label, content) in enumerate(sections):
        base_slug = safe_slug(label) or f"tab-{index}"
        slug = base_slug
        suffix = 1
        while slug in used_slugs:
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        used_slugs.add(slug)
        tab_id = f"{group_id}-tab-{slug}"
        panel_id = f"{group_id}-panel-{slug}"
        active_class = " active" if index == 0 else ""
        button_html.append(
            f"<button class='tab-button{active_class}' type='button' data-tab-group='{group_id}' data-tab-target='{panel_id}' id='{tab_id}'>{html_value(label)}</button>"
        )
        panel_html.append(
            f"<div class='tab-panel{active_class}' id='{panel_id}' data-tab-panel='{group_id}'>{content}</div>"
        )
    return (
        "<div class='tabs'>"
        f"<div class='tab-buttons'>{''.join(button_html)}</div>"
        f"{''.join(panel_html)}"
        "</div>"
    )


_COMPLEXITY_BADGE_CLASSES: dict[str, str] = {
    "Simple": "complexity-simple",
    "Moyen": "complexity-medium",
    "Complexe": "complexity-complex",
    "Tres complexe": "complexity-very-complex",
}


def complexity_badge_class(level: str) -> str:
    """Return the CSS class for a flow complexity ``level`` badge."""

    return _COMPLEXITY_BADGE_CLASSES.get(level, "")


def list_or_empty(items: list[str], empty_text: str) -> str:
    """Render ``items`` as a ``<ul>`` or fall back to a friendly empty message."""

    if not items:
        return f"<p class='empty'>{html_value(empty_text)}</p>"
    return "<ul>" + "".join(f"<li>{html_value(item)}</li>" for item in items) + "</ul>"


def render_page(
    title: str,
    body: str,
    current_path: Path,
    assets_dir: Path,
    include_mermaid: bool = True,
) -> str:
    """Render the full HTML document wrapping ``body``."""

    style_href = href_relative(current_path, assets_dir / "style.css")
    if include_mermaid:
        mermaid_script = MERMAID_RUNTIME_SCRIPT
    else:
        mermaid_script = ""
    return f"""<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_value(title)}</title>
    <link rel="stylesheet" href="{style_href}">
    {mermaid_script}
  </head>
  <body>
    <div class="page">
      {body}
    </div>
    {TABS_SCRIPT}
  </body>
</html>
"""
