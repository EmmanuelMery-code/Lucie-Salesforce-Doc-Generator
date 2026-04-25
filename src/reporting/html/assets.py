"""Static assets used by the HTML documentation site.

Holds the CSS, the Mermaid runtime ``<script>`` block embedded in every
page header, and the JavaScript that drives tab activation. These pieces
were originally inlined inside :class:`src.reporting.html_writer.HtmlReportWriter`
and have been extracted verbatim so the byte-for-byte HTML output stays
unchanged after the refactor.
"""

from __future__ import annotations

from pathlib import Path

from src.core.utils import write_text


SEVERITY_CSS_CLASS: dict[str, str] = {
    "Critical": "sev-critical",
    "Major": "sev-major",
    "Minor": "sev-minor",
    "Info": "sev-info",
}

SEVERITY_LABEL: dict[str, str] = {
    "Critical": "Critique",
    "Major": "Majeur",
    "Minor": "Mineur",
    "Info": "Info",
}


MERMAID_RUNTIME_SCRIPT = r"""
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.5/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
<script>
(function(){
  function isVisible(el){
    var p = el.parentElement;
    while(p && p !== document.body){
      if(p.classList && p.classList.contains("tab-panel") && !p.classList.contains("active")){
        return false;
      }
      p = p.parentElement;
    }
    return true;
  }
  function captureSource(el){
    if(!el.hasAttribute("data-mermaid-source")){
      el.setAttribute("data-mermaid-source", el.textContent);
    }
  }
  function parseTranslate(str){
    if(!str) return {x:0,y:0};
    var m = str.match(/translate\(\s*([-\d.eE+]+)\s*[, ]\s*([-\d.eE+]+)\s*\)/);
    if(!m) return {x:0,y:0};
    return {x: parseFloat(m[1]), y: parseFloat(m[2])};
  }
  function centerOfNode(node){
    var tr = parseTranslate(node.getAttribute("transform"));
    return {x: tr.x, y: tr.y};
  }
  function shiftPathEndpoints(path, startDelta, endDelta){
    var d = path.getAttribute("d");
    if(!d) return;
    var numberRe = /-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?/g;
    var nums = d.match(numberRe);
    if(!nums || nums.length < 4) return;
    if(startDelta){
      nums[0] = String(parseFloat(nums[0]) + startDelta.x);
      nums[1] = String(parseFloat(nums[1]) + startDelta.y);
    }
    if(endDelta){
      nums[nums.length-2] = String(parseFloat(nums[nums.length-2]) + endDelta.x);
      nums[nums.length-1] = String(parseFloat(nums[nums.length-1]) + endDelta.y);
    }
    var i = 0;
    var newD = d.replace(numberRe, function(){ return nums[i++]; });
    path.setAttribute("d", newD);
  }
  function nodeNameFromId(id){
    if(!id) return "";
    var m = id.match(/^flowchart-(.+?)-\d+$/);
    return m ? m[1] : id;
  }
  function findConnectedEdges(svg, nodeName){
    if(!nodeName) return {outgoing: [], incoming: []};
    var outgoing = [];
    var incoming = [];
    var paths = svg.querySelectorAll("g.edgePaths path, path.flowchart-link");
    paths.forEach(function(p){
      var cls = (p.getAttribute("class") || "").split(/\s+/);
      var fromCls = null, toCls = null;
      cls.forEach(function(c){
        if(c.indexOf("LS-") === 0){ fromCls = c.substring(3); }
        else if(c.indexOf("LE-") === 0){ toCls = c.substring(3); }
      });
      if(fromCls === nodeName){ outgoing.push(p); }
      if(toCls === nodeName){ incoming.push(p); }
    });
    return {outgoing: outgoing, incoming: incoming};
  }
  function moveEdgeLabel(svg, nodeName, delta){
    // labels are usually in g.edgeLabels and have labels per edge; we skip to avoid breakage.
  }
  function enableNodeDrag(svg, panZoom){
    var nodes = svg.querySelectorAll("g.node");
    nodes.forEach(function(node){
      if(node.dataset.mmDragEnabled === "true") return;
      node.dataset.mmDragEnabled = "true";
      var nodeName = nodeNameFromId(node.getAttribute("id"));
      var dragging = false;
      var startClient = null;
      var startOffset = null;
      var edges = null;
      var panEnabledBefore = true;
      node.addEventListener("mousedown", function(ev){
        if(ev.button !== 0) return;
        dragging = true;
        startClient = {x: ev.clientX, y: ev.clientY};
        startOffset = parseTranslate(node.getAttribute("transform"));
        edges = findConnectedEdges(svg, nodeName);
        try { panEnabledBefore = panZoom.isPanEnabled(); panZoom.disablePan(); } catch(e){}
        ev.stopPropagation();
        ev.preventDefault();
      });
      var lastDelta = {x:0,y:0};
      function onMove(ev){
        if(!dragging) return;
        var zoom = 1;
        try { zoom = panZoom.getZoom() || 1; } catch(e){}
        var dx = (ev.clientX - startClient.x) / zoom;
        var dy = (ev.clientY - startClient.y) / zoom;
        node.setAttribute("transform", "translate(" + (startOffset.x + dx) + "," + (startOffset.y + dy) + ")");
        var frameDelta = {x: dx - lastDelta.x, y: dy - lastDelta.y};
        if(edges){
          edges.outgoing.forEach(function(p){ shiftPathEndpoints(p, frameDelta, null); });
          edges.incoming.forEach(function(p){ shiftPathEndpoints(p, null, frameDelta); });
        }
        lastDelta = {x: dx, y: dy};
      }
      function onUp(){
        if(!dragging) return;
        dragging = false;
        lastDelta = {x:0, y:0};
        if(panEnabledBefore){ try { panZoom.enablePan(); } catch(e){} }
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }
  function enhanceContainer(container){
    if(container.dataset.mmEnhanced === "true") return;
    var mermaidDiv = container.querySelector(".mermaid");
    if(!mermaidDiv) return;
    if(mermaidDiv.getAttribute("data-processed") !== "true") return;
    var svg = mermaidDiv.querySelector("svg");
    if(!svg) return;
    container.dataset.mmEnhanced = "true";
    svg.removeAttribute("height");
    svg.removeAttribute("width");
    svg.style.width = "100%";
    svg.style.height = "100%";
    svg.style.maxWidth = "100%";
    var panZoom = null;
    try {
      panZoom = svgPanZoom(svg, {
        zoomEnabled: true,
        controlIconsEnabled: false,
        fit: true,
        center: true,
        minZoom: 0.2,
        maxZoom: 10,
        zoomScaleSensitivity: 0.35,
        dblClickZoomEnabled: false,
        preventMouseEventsDefault: false
      });
    } catch(err){
      console.error("svg-pan-zoom init failed", err);
      return;
    }
    var toolbar = container.querySelector(".mermaid-toolbar");
    if(toolbar){
      toolbar.addEventListener("click", function(ev){
        var btn = ev.target.closest("[data-mermaid-action]");
        if(!btn) return;
        var action = btn.getAttribute("data-mermaid-action");
        if(action === "zoom-in"){ panZoom.zoomBy(1.25); }
        else if(action === "zoom-out"){ panZoom.zoomBy(0.8); }
        else if(action === "reset"){ panZoom.resetZoom(); panZoom.center(); panZoom.fit(); }
      });
    }
    svg.addEventListener("dblclick", function(ev){
      if(ev.shiftKey){ panZoom.zoomBy(0.7); }
      else { panZoom.zoomBy(1.4); }
      ev.preventDefault();
    });
    enableNodeDrag(svg, panZoom);
  }
  function enhanceAll(scope){
    var containers = (scope || document).querySelectorAll(".mermaid-container");
    containers.forEach(enhanceContainer);
  }
  window.__enhanceMermaid = enhanceAll;
  window.__renderMermaid = function(root){
    if(!window.mermaid){return;}
    var scope = root || document;
    var nodes = Array.prototype.slice.call(scope.querySelectorAll(".mermaid"));
    var targets = nodes.filter(function(n){
      captureSource(n);
      if(!isVisible(n)){return false;}
      return n.getAttribute("data-processed") !== "true";
    });
    if(!targets.length){ enhanceAll(scope); return; }
    try{
      var result = window.mermaid.run({nodes: targets});
      if(result && typeof result.then === "function"){
        result.then(function(){ enhanceAll(scope); })
              .catch(function(e){ console.error("mermaid run", e); });
      } else {
        setTimeout(function(){ enhanceAll(scope); }, 50);
      }
    }
    catch(e){ console.error("mermaid run", e); }
  };
  function boot(){
    if(!window.mermaid){return;}
    try{
      window.mermaid.initialize({startOnLoad:false,securityLevel:"loose",theme:"default",flowchart:{htmlLabels:true,curve:"basis"}});
    }catch(e){ console.error("mermaid init", e); }
    Array.prototype.forEach.call(document.querySelectorAll(".mermaid"), captureSource);
    window.__renderMermaid();
  }
  if(document.readyState==="loading"){ document.addEventListener("DOMContentLoaded", boot); }
  else{ boot(); }
})();
</script>
""".strip()


TABS_SCRIPT = """
<script>
(() => {
  const renderMermaidIn = (panel) => {
    if (!panel) return;
    const fn = window.__renderMermaid;
    if (typeof fn === "function") {
      fn(panel);
      return;
    }
    if (!window.mermaid) return;
    const nodes = Array.from(panel.querySelectorAll('.mermaid:not([data-processed="true"])'));
    if (!nodes.length) return;
    try {
      window.mermaid.run({ nodes });
    } catch (err) {
      console.error("mermaid run (tab)", err);
    }
  };
  const activatePanel = (panel) => {
    if (!panel) return false;
    const group = panel.getAttribute("data-tab-panel");
    if (!group) return false;
    document.querySelectorAll(`[data-tab-group="${group}"]`).forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(`[data-tab-panel="${group}"]`).forEach((item) => item.classList.remove("active"));
    panel.classList.add("active");
    const button = document.querySelector(`[data-tab-group="${group}"][data-tab-target="${panel.id}"]`);
    if (button) button.classList.add("active");
    renderMermaidIn(panel);
    return true;
  };
  document.querySelectorAll("[data-tab-group]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.getAttribute("data-tab-target");
      if (!target) return;
      activatePanel(document.getElementById(target));
    });
  });
  const applyHash = () => {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    activatePanel(document.getElementById(hash));
  };
  window.addEventListener("hashchange", applyHash);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyHash);
  } else {
    applyHash();
  }
})();
</script>
""".strip()


MAIN_CSS = """
body { font-family: Arial, sans-serif; margin: 0; color: #1f2937; background: #f8fafc; }
.page { max-width: 1400px; margin: 0 auto; padding: 24px; }
.topnav { margin-bottom: 20px; }
.topnav a { text-decoration: none; color: #1d4ed8; }
h1, h2, h3 { color: #0f172a; }
.cards { display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0 24px; }
.card { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; min-width: 180px; }
.card .value { display: block; font-size: 1.6rem; font-weight: bold; margin-top: 8px; }
table { width: 100%; border-collapse: collapse; background: white; margin: 12px 0 24px; }
th, td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; vertical-align: top; }
th { background: #dbeafe; }
tr:nth-child(even) td { background: #f8fbff; }
.badge { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #dbeafe; color: #1e3a8a; }
.badge.complexity-simple { background: #dcfce7; color: #166534; }
.badge.complexity-medium { background: #fef3c7; color: #92400e; }
.badge.complexity-complex { background: #fed7aa; color: #9a3412; }
.badge.complexity-very-complex { background: #fecaca; color: #991b1b; }
.section { margin-bottom: 28px; }
ul { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px 32px; }
.empty { color: #64748b; font-style: italic; }
.mermaid { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; overflow: auto; }
.mermaid-container { margin: 14px 0; border: 1px solid #cbd5e1; border-radius: 10px; background: white; overflow: hidden; box-shadow: 0 1px 2px rgba(15,23,42,0.06); width: 100%; box-sizing: border-box; }
.mermaid-toolbar { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-bottom: 1px solid #e2e8f0; background: #f1f5f9; }
.mermaid-toolbar button.mm-btn { border: 1px solid #94a3b8; background: white; border-radius: 6px; padding: 3px 10px; cursor: pointer; font-weight: 600; color: #1e293b; min-width: 34px; line-height: 1.2; }
.mermaid-toolbar button.mm-btn:hover { background: #dbeafe; border-color: #60a5fa; }
.mermaid-toolbar .mm-hint { margin-left: auto; font-size: 0.78rem; color: #64748b; font-style: italic; }
.mermaid-container .mermaid { border: none; border-radius: 0; padding: 0; margin: 0; width: 100%; height: 720px; max-height: 85vh; overflow: hidden; background: white; user-select: none; box-sizing: border-box; display: block; position: relative; }
.mermaid-container .mermaid svg { width: 100% !important; height: 100% !important; max-width: none !important; display: block; }
.mermaid-container .mermaid g.node { cursor: grab; }
.mermaid-container .mermaid g.node:active { cursor: grabbing; }
.tab-panel .mermaid-container { max-width: 100%; }
code { background: #e2e8f0; padding: 2px 4px; border-radius: 4px; }
.smallcards .card { min-width: 150px; }
.graph-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.graph-toolbar button { border: 1px solid #cbd5e1; background: #f8fafc; border-radius: 6px; padding: 6px 10px; cursor: pointer; }
.graph-toolbar button:hover { background: #e2e8f0; }
.graph-filters { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 10px; }
.graph-filters label { display: inline-flex; align-items: center; gap: 6px; font-size: 0.92rem; color: #334155; }
.dependency-graph { height: 440px; border: 1px solid #cbd5e1; border-radius: 8px; background: #ffffff; }
.graph-legend { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 12px; }
.graph-legend .item { display: inline-flex; align-items: center; gap: 6px; font-size: 0.9rem; }
.findings-summary { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 14px; }
.findings-summary .chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; border: 1px solid #cbd5e1; background: white; color: #1e293b; }
.findings-summary .chip strong { font-weight: 700; }
.findings-summary .chip.sev-critical { background: #fef2f2; border-color: #f87171; color: #991b1b; }
.findings-summary .chip.sev-major { background: #fff7ed; border-color: #fb923c; color: #9a3412; }
.findings-summary .chip.sev-minor { background: #fefce8; border-color: #eab308; color: #854d0e; }
.findings-summary .chip.sev-info { background: #eff6ff; border-color: #60a5fa; color: #1e3a8a; }
.findings-list { list-style: none; padding: 0; margin: 0; background: white; border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden; }
.findings-list li.finding { padding: 14px 18px; border-top: 1px solid #e2e8f0; }
.findings-list li.finding:first-child { border-top: none; }
.findings-list li.finding .head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 6px; }
.findings-list li.finding .title { font-weight: 700; color: #0f172a; }
.findings-list li.finding .rule-id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; color: #475569; }
.findings-list li.finding .sev-badge { display: inline-block; font-size: 0.75rem; padding: 2px 8px; border-radius: 999px; font-weight: 700; letter-spacing: 0.02em; }
.findings-list li.finding .sev-badge.sev-critical { background: #fee2e2; color: #991b1b; }
.findings-list li.finding .sev-badge.sev-major { background: #ffedd5; color: #9a3412; }
.findings-list li.finding .sev-badge.sev-minor { background: #fef9c3; color: #854d0e; }
.findings-list li.finding .sev-badge.sev-info { background: #dbeafe; color: #1e3a8a; }
.findings-list li.finding .category-badge { display: inline-block; font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; background: #e2e8f0; color: #334155; letter-spacing: 0.02em; }
.findings-list li.finding .message { margin: 2px 0 6px; color: #1e293b; }
.findings-list li.finding .metadata { font-size: 0.85rem; color: #475569; margin: 4px 0; }
.findings-list li.finding .metadata dt { font-weight: 600; color: #0f172a; float: left; margin-right: 6px; }
.findings-list li.finding .metadata dd { margin: 0 0 4px; }
.findings-list li.finding .metadata a { color: #1d4ed8; }
.findings-list li.finding ul.details { margin: 6px 0 0; padding-left: 18px; }
.findings-list li.finding ul.details li { list-style: disc; color: #334155; }
.analyzer-summary-card { background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #cbd5e1; border-radius: 12px; padding: 18px 22px; margin: 12px 0; }
.analyzer-summary-card h3 { margin-top: 0; }
.analyzer-summary-card table { width: 100%; border: none; background: transparent; border-collapse: collapse; }
.analyzer-summary-card table th, .analyzer-summary-card table td { border: none; background: transparent; padding: 6px 10px; }
.analyzer-summary-card table tbody tr:nth-child(even) td { background: #f1f5f9; }
.graph-legend .dot { width: 12px; height: 12px; border-radius: 999px; border: 1px solid #64748b; display: inline-block; }
.tabs { background: white; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; }
.tab-buttons { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px; border-bottom: 1px solid #cbd5e1; background: #f8fafc; }
.tab-button { border: 1px solid #cbd5e1; border-radius: 999px; background: white; color: #334155; padding: 6px 12px; cursor: pointer; }
.tab-button.active { background: #dbeafe; color: #1e3a8a; border-color: #93c5fd; }
.tab-panel { display: none; padding: 14px; }
.tab-panel.active { display: block; }
        """.strip()


def write_assets(assets_dir: Path) -> None:
    """Write the static stylesheet to ``assets_dir/style.css``."""

    write_text(assets_dir / "style.css", MAIN_CSS)
