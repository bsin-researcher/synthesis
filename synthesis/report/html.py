import json
from synthesis.data.fred import DataSeries
from synthesis.alignment.qqa import AlignmentResult, build_gap_matrix
from synthesis.alignment.meta import PooledEvidence
from synthesis.extraction.effect_sizes import EffectSize
from synthesis.report.forest import build_forest_plot


BG    = "#0d1117"
SURF  = "#161b22"
BORD  = "#30363d"
MUTED = "#8b949e"
TEXT  = "#e6edf3"
BLUE  = "#58a6ff"
GREEN = "#3fb950"
RED   = "#f85149"
ORG   = "#ffa657"
PURP  = "#d2a8ff"

SUPPORT_COLORS = {
    "strongly_supported":     GREEN,
    "supported":              "#79c0ff",
    "neutral":                MUTED,
    "contradicted":           ORG,
    "strongly_contradicted":  RED,
    "insufficient_data":      MUTED,
}

SUPPORT_LABELS = {
    "strongly_supported":    "Strongly Supported",
    "supported":             "Supported",
    "neutral":               "Neutral",
    "contradicted":          "Contradicted",
    "strongly_contradicted": "Strongly Contradicted",
    "insufficient_data":     "Insufficient Data",
}


def _plotly_spec(series: DataSeries, chart_id: str) -> tuple[str, str]:
    """Returns (div_html, js_call) for an interactive Plotly chart."""
    df = series.data.dropna(subset=["value"])
    if df.empty:
        return "", ""

    dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
    values = [round(float(v), 4) for v in df["value"].tolist()]

    is_wb  = series.series_id.startswith("WB:")
    is_bls = series.series_id.startswith("BLS:")
    if is_wb:
        line_color = PURP
        fill_color = "rgba(210,168,255,0.07)"
    elif is_bls:
        line_color = ORG
        fill_color = "rgba(255,166,87,0.07)"
    else:
        line_color = BLUE
        fill_color = "rgba(88,166,255,0.08)"

    trace = {
        "x": dates,
        "y": values,
        "type": "scatter",
        "mode": "lines",
        "fill": "tozeroy",
        "fillcolor": fill_color,
        "line": {"color": line_color, "width": 1.8},
        "hovertemplate": f"%{{x}}<br>{series.units}: %{{y:.3f}}<extra></extra>",
        "name": series.series_id,
    }
    layout = {
        "paper_bgcolor": SURF,
        "plot_bgcolor": SURF,
        "font": {"color": MUTED, "size": 11, "family": "-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif"},
        "title": {
            "text": series.title,
            "font": {"color": TEXT, "size": 12},
            "x": 0.02,
            "xanchor": "left",
        },
        "xaxis": {
            "gridcolor": BORD,
            "showgrid": True,
            "tickfont": {"size": 10},
            "linecolor": BORD,
        },
        "yaxis": {
            "gridcolor": BORD,
            "showgrid": True,
            "title": {"text": series.units, "font": {"size": 10}},
            "tickfont": {"size": 10},
            "linecolor": BORD,
        },
        "margin": {"t": 50, "b": 40, "l": 60, "r": 16},
        "height": 260,
        "hovermode": "x unified",
        "hoverlabel": {
            "bgcolor": BG,
            "bordercolor": BORD,
            "font": {"color": TEXT, "size": 11},
        },
    }
    config = {"responsive": True, "displayModeBar": False}

    div_html = f'<div id="{chart_id}" style="width:100%;border-radius:8px;overflow:hidden"></div>'
    js_call = (
        f'Plotly.newPlot("{chart_id}",'
        f'{json.dumps([trace])},'
        f'{json.dumps(layout)},'
        f'{json.dumps(config)});'
    )
    return div_html, js_call


def build_html(
    question: str,
    report_md: str,
    alignment: list[AlignmentResult],
    data_series: list[DataSeries],
    papers_count: int,
    fred_count: int = 0,
    wb_count: int = 0,
    bls_count: int = 0,
    pooled: PooledEvidence | None = None,
    effect_sizes: list[EffectSize] | None = None,
) -> str:
    gap_matrix = build_gap_matrix([r.claim for r in alignment])

    css = f"""
    :root {{
      --bg:{BG}; --surf:{SURF}; --bord:{BORD}; --muted:{MUTED};
      --text:{TEXT}; --blue:{BLUE}; --green:{GREEN}; --red:{RED}; --org:{ORG}; --purp:{PURP};
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:var(--bg); color:var(--text);
           font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
           font-size:15px; line-height:1.7; padding-bottom:80px; }}
    .header {{ background:var(--surf); border-bottom:1px solid var(--bord);
               padding:28px 48px; display:flex; justify-content:space-between; align-items:center; }}
    .header h1 {{ font-size:22px; font-weight:800; color:var(--blue); }}
    .header .meta {{ color:var(--muted); font-size:13px; text-align:right; line-height:1.9; }}
    .question-banner {{ max-width:1100px; margin:40px auto 0; padding:0 32px; }}
    .question-box {{ background:var(--surf); border:1px solid var(--bord);
                     border-left:4px solid var(--blue); border-radius:8px;
                     padding:20px 24px; }}
    .question-box .label {{ font-size:11px; color:var(--muted); text-transform:uppercase;
                            letter-spacing:1px; margin-bottom:6px; }}
    .question-box .q {{ font-size:20px; font-weight:700; color:var(--text); }}
    .stats-row {{ max-width:1100px; margin:24px auto 0; padding:0 32px;
                  display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }}
    .stat {{ background:var(--surf); border:1px solid var(--bord); border-radius:8px;
             padding:18px 20px; text-align:center; }}
    .stat .num {{ font-size:32px; font-weight:800; color:var(--blue); }}
    .stat .lab {{ font-size:12px; color:var(--muted); margin-top:4px; }}
    .section {{ max-width:1100px; margin:40px auto 0; padding:0 32px; }}
    h2 {{ font-size:17px; font-weight:700; color:var(--blue); padding-bottom:10px;
          border-bottom:1px solid var(--bord); margin-bottom:18px; }}
    h3 {{ font-size:14px; font-weight:600; color:var(--text); margin:16px 0 8px; }}
    p {{ color:var(--muted); margin-bottom:12px; }}
    ul {{ padding-left:20px; color:var(--muted); }}
    li {{ margin-bottom:6px; }}
    strong {{ color:var(--text); }}
    em {{ color:var(--muted); font-style:italic; }}
    .report-body h2 {{ font-size:17px; font-weight:700; color:var(--blue);
                       padding-bottom:10px; border-bottom:1px solid var(--bord);
                       margin:32px 0 16px; }}
    .report-body h3 {{ font-size:14px; font-weight:600; color:var(--text);
                       margin:18px 0 8px; }}
    .report-body p {{ color:var(--muted); margin-bottom:12px; line-height:1.7; }}
    .report-body ul, .report-body ol {{ padding-left:22px; color:var(--muted);
                                        margin-bottom:12px; }}
    .report-body li {{ margin-bottom:6px; }}
    .alignment-grid {{ display:grid; grid-template-columns:1fr; gap:10px; }}
    .alignment-card {{ background:var(--surf); border:1px solid var(--bord);
                       border-radius:8px; padding:14px 18px;
                       display:grid; grid-template-columns:auto 1fr; gap:0 16px; }}
    .align-badge {{ display:inline-block; padding:3px 10px; border-radius:4px;
                    font-size:11px; font-weight:700; white-space:nowrap; }}
    .align-meta {{ font-size:12px; color:var(--muted); margin-top:4px; }}
    .align-finding {{ font-size:13.5px; color:var(--text); margin:6px 0 4px; }}
    .align-explain {{ font-size:12px; color:var(--muted); font-style:italic; }}
    .data-charts {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
    .chart-card {{ background:var(--surf); border:1px solid var(--bord); border-radius:8px;
                   padding:4px; }}
    .chart-badge {{ display:inline-block; padding:2px 8px; border-radius:4px;
                    font-size:10px; font-weight:700; margin:6px 10px 2px;
                    background:rgba(88,166,255,0.15); color:var(--blue); }}
    .chart-badge.wb  {{ background:rgba(210,168,255,0.15); color:var(--purp); }}
    .chart-badge.bls {{ background:rgba(255,166,87,0.15);  color:var(--org);  }}
    .chart-meta {{ padding:6px 12px 10px; font-size:12px; color:var(--muted); }}
    .gap-list {{ list-style:none; padding:0; }}
    .gap-list li {{ background:var(--surf); border:1px solid var(--bord);
                    border-left:3px solid var(--org); border-radius:6px;
                    padding:10px 14px; margin-bottom:8px; font-size:13px;
                    color:var(--text); }}
    .pooled-card {{ max-width:1100px; margin:28px auto 0; padding:0 32px; }}
    .pooled-inner {{ border-radius:10px; padding:20px 24px;
                     display:grid; grid-template-columns:auto 1fr; gap:0 24px;
                     align-items:start; }}
    .pooled-direction {{ font-size:28px; font-weight:900; letter-spacing:-0.5px; }}
    .pooled-score {{ font-size:13px; color:var(--muted); margin-top:4px; }}
    .pooled-statement {{ font-size:14px; color:var(--text); line-height:1.6; }}
    .pooled-breakdown {{ display:flex; gap:16px; margin-top:10px; flex-wrap:wrap; }}
    .pooled-pill {{ font-size:11px; padding:3px 10px; border-radius:4px;
                    font-weight:700; background:rgba(255,255,255,0.06); color:var(--muted); }}
    .effect-sizes {{ margin-top:10px; font-size:12px; color:var(--muted); }}
    .effect-sizes li {{ list-style:disc; margin-left:16px; margin-bottom:3px; }}
    .footer {{ max-width:1100px; margin:60px auto 0; padding:20px 32px 0;
               border-top:1px solid var(--bord); color:var(--muted);
               font-size:12px; display:flex; justify-content:space-between; }}
    @media(max-width:800px) {{
      .stats-row {{ grid-template-columns:repeat(2,1fr); }}
      .data-charts {{ grid-template-columns:1fr; }}
      .header {{ flex-direction:column; gap:10px; }}
    }}
    """

    supported = sum(1 for r in alignment if r.support_score is not None and r.support_score > 0)
    contradicted = sum(1 for r in alignment if r.support_score is not None and r.support_score < 0)
    gaps = len(gap_matrix.get("unstudied_combinations", []))

    def md_to_html(text: str) -> str:
        lines = text.split("\n")
        out = []
        for line in lines:
            if line.startswith("## "):
                out.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                out.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("- ") or line.startswith("* "):
                out.append(f"<li>{_inline(line[2:])}</li>")
            elif line.strip() == "":
                out.append("</ul><p></p>")
            else:
                out.append(f"<p>{_inline(line)}</p>")
        html = "\n".join(out)
        html = html.replace("</li>\n<p></p>\n<li>", "</li>\n<li>")
        return html

    def _inline(text: str) -> str:
        import re
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        return text

    # Pre-build forest plot
    forest_div, forest_js = build_forest_plot(effect_sizes or [])

    # Pre-build chart divs and collect all JS calls
    chart_divs = []
    chart_scripts = []
    for i, s in enumerate(data_series):
        cid = f"chart_{i}"
        div_html, js_call = _plotly_spec(s, cid)
        if div_html:
            is_wb  = s.series_id.startswith("WB:")
            is_bls = s.series_id.startswith("BLS:")
            if is_wb:
                badge_cls, badge_txt = "chart-badge wb",  "World Bank"
            elif is_bls:
                badge_cls, badge_txt = "chart-badge bls", "BLS"
            else:
                badge_cls, badge_txt = "chart-badge",     "FRED"
            summ = s.summary()
            meta = (
                f"{s.series_id} &nbsp;·&nbsp; "
                f"Latest: <strong>{summ.get('latest_value')} {s.units}</strong> "
                f"&nbsp;·&nbsp; {summ.get('start','')[:4]}–{summ.get('end','')[:4]}"
            )
            card = (
                f'<div class="chart-card">'
                f'<span class="{badge_cls}">{badge_txt}</span>'
                f'{div_html}'
                f'<div class="chart-meta">{meta}</div>'
                f'</div>'
            )
            chart_divs.append(card)
            chart_scripts.append(js_call)

    source_line = "arXiv · OpenAlex · NBER"
    parts = ["FRED"] + (["World Bank"] if wb_count else []) + (["BLS"] if bls_count else [])
    data_source_line = " · ".join(parts)

    h = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Synthesis — {question[:60]}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>{css}</style>
</head>
<body>
<div class="header">
  <div>
    <h1>Synthesis · Economics Research Brief</h1>
    <div style="color:var(--muted);font-size:13px;margin-top:4px;">
      Qualitative · Quantitative · QQA Alignment
    </div>
  </div>
  <div class="meta">
    Model: claude-opus-4-8 · Adaptive Thinking<br>
    Literature: {source_line}<br>
    Data: {data_source_line} &nbsp;·&nbsp; synthesis-econ v0.3.0
  </div>
</div>

<div class="question-banner">
  <div class="question-box">
    <div class="label">Research Question</div>
    <div class="q">{question}</div>
  </div>
</div>

<div class="stats-row">
  <div class="stat"><div class="num">{papers_count}</div><div class="lab">Papers Retrieved</div></div>
  <div class="stat"><div class="num">{len(alignment)}</div><div class="lab">Claims Extracted</div></div>
  <div class="stat"><div class="num" style="color:var(--green)">{supported}</div><div class="lab">Data-Supported</div></div>
  <div class="stat"><div class="num" style="color:var(--red)">{contradicted}</div><div class="lab">Contradicted by Data</div></div>
</div>
"""

    # Pooled evidence card
    if pooled and pooled.n_claims > 0:
        dir_colors = {
            "positive":  (GREEN, "rgba(63,185,80,0.1)"),
            "negative":  (RED,   "rgba(248,81,73,0.1)"),
            "no_effect": (BLUE,  "rgba(88,166,255,0.1)"),
            "mixed":     (ORG,   "rgba(255,166,87,0.1)"),
        }
        dcol, dbg = dir_colors.get(pooled.pooled_direction, (MUTED, f"rgba(139,148,158,0.1)"))
        dir_label = {
            "positive": "POSITIVE",
            "negative": "NEGATIVE",
            "no_effect": "NO CLEAR EFFECT",
            "mixed": "MIXED",
        }.get(pooled.pooled_direction, pooled.pooled_direction.upper())

        methods_str = " · ".join(pooled.top_methods) if pooled.top_methods else "—"
        h += f'<div class="pooled-card">'
        h += (
            f'<div class="pooled-inner" style="background:{dbg};border:1px solid {dcol}44;">'
            f'<div>'
            f'<div class="pooled-direction" style="color:{dcol}">{dir_label}</div>'
            f'<div class="pooled-score">Weighted score: {pooled.weighted_score:+.2f} &nbsp;·&nbsp; '
            f'{pooled.n_claims} claims &nbsp;·&nbsp; {pooled.high_confidence_count} high-confidence'
            f'&nbsp;·&nbsp; Top methods: {methods_str}</div>'
            f'</div>'
            f'<div>'
            f'<div class="pooled-statement">{pooled.consensus_statement}</div>'
            f'<div class="pooled-breakdown">'
            f'<span class="pooled-pill">▲ {pooled.n_positive} positive</span>'
            f'<span class="pooled-pill">▼ {pooled.n_negative} negative</span>'
            f'<span class="pooled-pill">— {pooled.n_no_effect} no effect</span>'
            f'<span class="pooled-pill">~ {pooled.n_ambiguous} ambiguous</span>'
            f'</div>'
        )
        if pooled.effect_sizes:
            h += '<ul class="effect-sizes">'
            for es in pooled.effect_sizes:
                h += f"<li>{es}</li>"
            h += "</ul>"
        h += "</div></div></div>"

    # Report body
    h += '<div class="section"><div class="report-body">'
    h += md_to_html(report_md)
    h += "</div></div>"

    # QQA Alignment section
    if alignment:
        h += '<div class="section"><h2>QQA Alignment — Theory vs. Data</h2>'
        h += '<div class="alignment-grid">'
        for r in alignment:
            color = SUPPORT_COLORS.get(r.support_level, MUTED)
            label = SUPPORT_LABELS.get(r.support_level, r.support_level)
            method_geo = f"{r.claim.methodology} · {r.claim.geography} · {r.claim.time_period}"
            dir_color = GREEN if r.claim.direction == "positive" else (RED if r.claim.direction == "negative" else MUTED)
            h += f"""<div class="alignment-card">
  <div>
    <span class="align-badge" style="background:{color}22;color:{color}">{label}</span>
    <div class="align-meta">{method_geo}</div>
  </div>
  <div>
    <div class="align-finding"><strong>{r.claim.variable_a} → {r.claim.variable_b}</strong>
     &nbsp;<span style="color:{dir_color}">({r.claim.direction})</span></div>
    <div class="align-explain">{r.claim.finding}</div>
    <div class="align-explain" style="margin-top:4px;color:{color}">↳ {r.explanation}</div>
  </div>
</div>"""
        h += "</div></div>"

    # Forest plot
    if forest_div:
        h += '<div class="section"><h2>Forest Plot — Effect Sizes Across Studies</h2>'
        h += (
            '<p style="font-size:12px;margin-bottom:12px;">'
            'Squares = individual study estimates (size ∝ citations). '
            '<span style="color:#3fb950">Green</span> = CI excludes zero positively. '
            '<span style="color:#f85149">Red</span> = CI excludes zero negatively. '
            'Gray = CI crosses zero or not reported. '
            '◆ Diamond = citation-weighted pooled estimate.'
            '</p>'
        )
        h += f'<div class="chart-card" style="padding:4px">{forest_div}</div>'
        h += "</div>"
        if forest_js:
            chart_scripts.append(forest_js)

    # Interactive data charts
    if chart_divs:
        h += f'<div class="section"><h2>Empirical Data — {data_source_line}</h2>'
        h += '<div class="data-charts">'
        h += "\n".join(chart_divs)
        h += "</div></div>"

    # Research gaps
    unstudied = gap_matrix.get("unstudied_combinations", [])
    if unstudied:
        h += '<div class="section"><h2>Research Gap Matrix</h2>'
        h += '<ul class="gap-list">'
        for g in unstudied:
            h += f"<li>{g['note']}</li>"
        h += "</ul></div>"

    h += f"""<div class="footer">
  <span>Synthesis v0.1.0 · claude-opus-4-8 · {source_line} · {data_source_line}</span>
  <span>For research purposes — verify all claims independently</span>
</div>
"""

    # All Plotly initialization scripts at end of body
    if chart_scripts:
        h += "<script>\n" + "\n".join(chart_scripts) + "\n</script>\n"

    h += "</body></html>"
    return h
