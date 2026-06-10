"""
Forest plot generator for effect sizes.

Standard academic forest plot layout:
- One row per study: square marker (sized by citations), horizontal CI bar
- Marker color: green (CI > 0), red (CI < 0), gray (CI crosses 0 or no CI)
- Dotted vertical reference line at x=0
- Diamond row at bottom: citation-weighted pooled estimate
"""

import json
import math
from synthesis.extraction.effect_sizes import EffectSize

BG    = "#0d1117"
SURF  = "#161b22"
BORD  = "#30363d"
MUTED = "#8b949e"
TEXT  = "#e6edf3"
BLUE  = "#58a6ff"
GREEN = "#3fb950"
RED   = "#f85149"


def build_forest_plot(
    effect_sizes: list[EffectSize],
    chart_id: str = "chart_forest",
) -> tuple[str, str]:
    """Returns (div_html, js_call). Empty strings if fewer than 2 effect sizes."""
    if len(effect_sizes) < 2:
        return "", ""

    sorted_es = sorted(effect_sizes, key=lambda e: e.estimate)

    # Citation-weighted pooled estimate
    weights = [math.log(e.citations + 1) + 1 for e in sorted_es]
    total_w = sum(weights)
    pooled_est = sum(e.estimate * w for e, w in zip(sorted_es, weights)) / total_w

    y_labels = [e.paper_title[:42] for e in sorted_es] + ["◆ Pooled (citation-weighted)"]
    x_vals = [round(e.estimate, 4) for e in sorted_es] + [round(pooled_est, 4)]

    # Error bar arrays — None draws no bar for that point
    err_plus, err_minus = [], []
    for e in sorted_es:
        if e.lower_ci is not None and e.upper_ci is not None:
            err_plus.append(round(abs(e.upper_ci - e.estimate), 4))
            err_minus.append(round(abs(e.estimate - e.lower_ci), 4))
        else:
            err_plus.append(None)
            err_minus.append(None)
    err_plus.append(None)
    err_minus.append(None)

    # Marker colors
    colors = []
    for i, e in enumerate(sorted_es):
        if err_plus[i] is not None and e.lower_ci is not None and e.upper_ci is not None:
            if e.lower_ci > 0:
                colors.append(GREEN)
            elif e.upper_ci < 0:
                colors.append(RED)
            else:
                colors.append(MUTED)
        else:
            colors.append(MUTED)
    colors.append(BLUE)

    # Marker sizes: 10–18px log-scaled by citations
    sizes = [round(max(10, min(18, 10 + math.log(e.citations + 1) * 1.5)), 1) for e in sorted_es]
    sizes.append(20)

    symbols = ["square"] * len(sorted_es) + ["diamond"]

    # Hover text
    hover = []
    for e in sorted_es:
        ci_str = (
            f"[{e.lower_ci:.3f}, {e.upper_ci:.3f}]"
            if e.lower_ci is not None else "not reported"
        )
        hover.append(
            f"<b>{e.paper_title}</b><br>"
            f"Estimate: {e.estimate:.4f}<br>"
            f"95% CI: {ci_str}<br>"
            f"Unit: {e.unit}<br>"
            f"Method: {e.methodology} · {e.geography}<br>"
            f"Citations: {e.citations}"
        )
    hover.append(
        f"<b>Pooled (citation-weighted mean)</b><br>"
        f"n={len(sorted_es)} studies<br>"
        f"Estimate: {pooled_est:.4f}"
    )

    trace = {
        "type": "scatter",
        "mode": "markers",
        "x": x_vals,
        "y": y_labels,
        "error_x": {
            "type": "data",
            "symmetric": False,
            "array": err_plus,
            "arrayminus": err_minus,
            "visible": True,
            "color": MUTED,
            "thickness": 1.8,
            "width": 7,
        },
        "marker": {
            "color": colors,
            "size": sizes,
            "symbol": symbols,
            "line": {"color": BG, "width": 1.5},
        },
        "hovertemplate": "%{customdata}<extra></extra>",
        "customdata": hover,
        "showlegend": False,
    }

    height = max(320, 54 * (len(sorted_es) + 2) + 80)

    layout = {
        "paper_bgcolor": SURF,
        "plot_bgcolor": SURF,
        "font": {
            "color": MUTED,
            "size": 11,
            "family": "-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif",
        },
        "title": {
            "text": (
                f"{len(sorted_es)} studies · pooled = {pooled_est:+.3f}"
                f"  <span style='font-size:10px;color:{MUTED}'>marker size ∝ citations</span>"
            ),
            "font": {"color": TEXT, "size": 12},
            "x": 0.02,
            "xanchor": "left",
        },
        "xaxis": {
            "title": {"text": "Effect Size (as reported by study)", "font": {"size": 10}},
            "gridcolor": BORD,
            "showgrid": True,
            "zeroline": True,
            "zerolinecolor": MUTED,
            "zerolinewidth": 2,
            "tickfont": {"size": 10},
            "linecolor": BORD,
        },
        "yaxis": {
            "type": "category",
            "autorange": True,
            "tickfont": {"size": 11},
            "gridcolor": BORD,
            "linecolor": BORD,
        },
        "margin": {"t": 50, "b": 55, "l": 230, "r": 40},
        "height": height,
        "hovermode": "closest",
        "hoverlabel": {
            "bgcolor": BG,
            "bordercolor": BORD,
            "font": {"color": TEXT, "size": 11},
        },
        "shapes": [{
            "type": "line",
            "x0": 0, "x1": 0,
            "y0": 0, "y1": 1,
            "xref": "x", "yref": "paper",
            "line": {"color": MUTED, "width": 1.5, "dash": "dot"},
        }],
    }

    config = {"responsive": True, "displayModeBar": False}

    div_html = f'<div id="{chart_id}" style="width:100%;border-radius:8px;overflow:hidden"></div>'
    js_call = (
        f'Plotly.newPlot("{chart_id}",'
        f"{json.dumps([trace])},"
        f"{json.dumps(layout)},"
        f"{json.dumps(config)});"
    )
    return div_html, js_call
