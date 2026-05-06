"""Render the per-AI-component (Agents, Prompts) documentation pages."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import AgentInfo, GenAiPromptInfo, MetadataSnapshot
from src.core.utils import html_value, safe_slug, write_text

from src.reporting.html.findings import (
    render_analyzer_tab,
    render_findings_summary,
)
from src.reporting.html.page_shell import (
    index_back_link,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


def render_agent_page(
    agent: AgentInfo,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    findings: list[Finding] | None = None,
) -> str:
    findings = findings or []
    analyzer_tab = render_analyzer_tab(findings)
    analyzer_inline_summary = render_findings_summary(findings)
    
    summary_html = (
        f"<p>{html_value(agent.description or 'Aucune description fournie.')}</p>"
        "<div class='section'><h3>Alertes analyseur</h3>"
        + analyzer_inline_summary
        + "</div>"
    )
    
    tabs = tabbed_sections(
        f"agent-{safe_slug(agent.name)}",
        [
            ("Resume", summary_html),
            ("Analyseur", analyzer_tab),
        ],
    )
    
    body = f"""
{index_back_link(current_path, output_dir, "agents")}
<h1>Agent : {html_value(agent.name)}</h1>
<span class="badge">Agentforce</span>
<div class="cards smallcards">
  <div class="card"><span>Label</span><span class="value" style="font-size: 1.2rem;">{html_value(agent.label)}</span></div>
</div>
{tabs}
"""
    return render_page(agent.name, body, current_path, assets_dir)


def render_prompt_page(
    prompt: GenAiPromptInfo,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    findings: list[Finding] | None = None,
) -> str:
    findings = findings or []
    analyzer_tab = render_analyzer_tab(findings)
    analyzer_inline_summary = render_findings_summary(findings)
    
    summary_html = (
        f"<p>{html_value(prompt.description or 'Aucune description fournie.')}</p>"
        "<div class='section'><h3>Alertes analyseur</h3>"
        + analyzer_inline_summary
        + "</div>"
    )
    
    tabs = tabbed_sections(
        f"prompt-{safe_slug(prompt.name)}",
        [
            ("Resume", summary_html),
            ("Analyseur", analyzer_tab),
        ],
    )
    
    body = f"""
{index_back_link(current_path, output_dir, "prompts")}
<h1>Prompt : {html_value(prompt.name)}</h1>
<span class="badge">Prompt Builder</span>
<div class="cards smallcards">
  <div class="card"><span>Label</span><span class="value" style="font-size: 1.2rem;">{html_value(prompt.label)}</span></div>
</div>
{tabs}
"""
    return render_page(prompt.name, body, current_path, assets_dir)


def write_ai_pages(
    snapshot: MetadataSnapshot,
    agents_dir: Path,
    prompts_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
) -> tuple[dict[str, Path], dict[str, Path]]:
    agent_findings = getattr(analyzer_report, "agents", {}) if analyzer_report else {}
    prompt_findings = getattr(analyzer_report, "prompts", {}) if analyzer_report else {}
    
    agent_pages: dict[str, Path] = {}
    for agent in snapshot.agents:
        path = agents_dir / f"{safe_slug(agent.name)}.html"
        agent_pages[agent.name] = path
        write_text(
            path,
            render_agent_page(
                agent,
                path,
                output_dir,
                assets_dir,
                agent_findings.get(agent.name, []),
            ),
        )
    
    prompt_pages: dict[str, Path] = {}
    for prompt in snapshot.gen_ai_prompts:
        path = prompts_dir / f"{safe_slug(prompt.name)}.html"
        prompt_pages[prompt.name] = path
        write_text(
            path,
            render_prompt_page(
                prompt,
                path,
                output_dir,
                assets_dir,
                prompt_findings.get(prompt.name, []),
            ),
        )
        
    if agent_pages:
        log(f"{len(agent_pages)} page(s) Agent generees.")
    if prompt_pages:
        log(f"{len(prompt_pages)} page(s) Prompt generees.")
        
    return agent_pages, prompt_pages
