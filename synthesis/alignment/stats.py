"""
Statistical alignment computation for QQA.

Two-step process:
1. map_variables_to_series: Claude maps each claim's variable_a / variable_b
   to the best available data series.
2. compute_alignment_stats: pure Python/scipy computes Spearman correlation
   and OLS slope on FIRST DIFFERENCES of annual data — removes spurious trends
   so a flat series is correctly flagged as insufficient, not "supported."

The statistical_support determination is rule-based (not Claude):
  - insufficient_variation: regressor (variable_a) has CV < threshold
  - strongly_supported / supported: sign matches claim, p <= threshold
  - strongly_contradicted / contradicted: sign opposes claim, p <= threshold
  - neutral: direction right but not significant
  - no_data: series not found

Claude's role in QQA is now ONLY to write the explanation in plain English
citing the actual numbers — not to decide the verdict.
"""

import json
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from dataclasses import dataclass
import anthropic
from synthesis.extraction.claims import Claim
from synthesis.data.fred import DataSeries


MIN_OBS = 5          # minimum overlapping annual observations
CV_THRESHOLD = 0.01  # coefficient of variation of Δa below this → flat regressor
P_STRONG = 0.05      # strongly supported/contradicted threshold
P_WEAK = 0.20        # supported/contradicted threshold

DIRECTION_SIGN: dict[str, int] = {
    "positive":  1,
    "negative": -1,
    "no_effect":  0,
    "ambiguous":  0,
    "nonlinear":  0,
}


@dataclass
class AlignmentStats:
    claim_index: int
    series_a_id: str | None      # proxy for variable_a
    series_b_id: str | None      # proxy for variable_b
    correlation: float | None    # Spearman r on Δa, Δb
    slope: float | None          # OLS slope of Δb on Δa
    p_value: float | None        # p-value on slope
    n_obs: int                   # overlapping annual observations
    cv_a: float | None           # coefficient of variation of Δa
    statistical_support: str     # the verdict — determined by numbers, not Claude
    data_summary: str            # compact stats string for Claude to interpret


def map_variables_to_series(
    claims: list[Claim],
    data_series: list[DataSeries],
    client: anthropic.Anthropic,
) -> dict[int, tuple[str | None, str | None]]:
    """
    Ask Claude to identify which data series best proxy each claim's
    variable_a and variable_b. Cheap call — low token budget, no thinking.
    """
    if not data_series:
        return {i: (None, None) for i in range(len(claims))}

    series_list = "\n".join(
        f"- {s.series_id}: {s.title} ({s.units})" for s in data_series
    )
    claims_list = "\n".join(
        f"[{i + 1}] variable_a='{c.variable_a}', variable_b='{c.variable_b}'"
        for i, c in enumerate(claims)
    )

    prompt = f"""Map each claim's variables to available data series.
Only assign a series if it genuinely measures that variable. Use null otherwise.

Available series:
{series_list}

Claims:
{claims_list}

Return a JSON array — one item per claim:
- claim_index: int (1-based)
- series_a: series_id string or null  (proxy for variable_a)
- series_b: series_id string or null  (proxy for variable_b)

Return ONLY the JSON array."""

    try:
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        mappings = json.loads(raw.strip())
        return {
            int(m["claim_index"]) - 1: (m.get("series_a"), m.get("series_b"))
            for m in mappings
        }
    except Exception:
        return {i: (None, None) for i in range(len(claims))}


def compute_alignment_stats(
    claims: list[Claim],
    data_series: list[DataSeries],
    mapping: dict[int, tuple[str | None, str | None]],
) -> list[AlignmentStats]:
    series_by_id = {s.series_id: s for s in data_series}
    return [
        _compute_one(i, claim, series_by_id.get(mapping.get(i, (None, None))[0]),
                     series_by_id.get(mapping.get(i, (None, None))[1]))
        for i, claim in enumerate(claims)
    ]


def _to_annual(s: DataSeries) -> pd.Series:
    df = s.data.dropna(subset=["value"]).copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year
    return df.groupby("year")["value"].last()


def _compute_one(
    idx: int,
    claim: Claim,
    series_a: DataSeries | None,
    series_b: DataSeries | None,
) -> AlignmentStats:
    no_data = AlignmentStats(
        claim_index=idx, series_a_id=None, series_b_id=None,
        correlation=None, slope=None, p_value=None, n_obs=0,
        cv_a=None, statistical_support="no_data",
        data_summary="No matching data series available.",
    )

    if series_b is None and series_a is None:
        return no_data

    ann_b = _to_annual(series_b) if series_b else None
    ann_a = _to_annual(series_a) if series_a else None

    # Case: only variable_b available — can't test the relationship
    if ann_a is None:
        return AlignmentStats(
            claim_index=idx,
            series_a_id=None,
            series_b_id=series_b.series_id,
            correlation=None, slope=None, p_value=None,
            n_obs=len(ann_b),
            cv_a=None,
            statistical_support="insufficient_variation",
            data_summary=(
                f"Only {series_b.series_id} available (no series for variable_a '{claim.variable_a}'). "
                f"Cannot test directional relationship."
            ),
        )

    # Overlapping years
    common = ann_a.index.intersection(ann_b.index)
    if len(common) < MIN_OBS:
        return AlignmentStats(
            claim_index=idx,
            series_a_id=series_a.series_id,
            series_b_id=series_b.series_id if series_b else None,
            correlation=None, slope=None, p_value=None,
            n_obs=len(common), cv_a=None,
            statistical_support="insufficient_variation",
            data_summary=f"Only {len(common)} overlapping annual observations (need ≥{MIN_OBS}).",
        )

    a = ann_a[common].values.astype(float)
    b = ann_b[common].values.astype(float)

    # First differences — removes spurious trends (standard econometric practice)
    da = np.diff(a)
    db = np.diff(b)

    # Coefficient of variation of Δa — detects flat regressor
    std_da = float(np.std(da))
    mean_a = float(np.abs(np.mean(a))) + 1e-10
    cv_a = std_da / mean_a

    if cv_a < CV_THRESHOLD:
        return AlignmentStats(
            claim_index=idx,
            series_a_id=series_a.series_id,
            series_b_id=series_b.series_id if series_b else None,
            correlation=None, slope=None, p_value=None,
            n_obs=len(common), cv_a=round(cv_a, 6),
            statistical_support="insufficient_variation",
            data_summary=(
                f"{series_a.series_id} is essentially flat (CV of Δ = {cv_a:.5f} < {CV_THRESHOLD}). "
                f"No identifying variation to test the effect on {series_b.series_id if series_b else 'outcome'}."
            ),
        )

    # Spearman correlation on first differences
    rho, _ = scipy_stats.spearmanr(da, db)
    # OLS slope + p-value on first differences
    slope, _, _, p_val, _ = scipy_stats.linregress(da, db)

    # Determine support level from statistics
    claim_sign = DIRECTION_SIGN.get(claim.direction, 0)
    slope_sign = 1 if slope > 0.0 else (-1 if slope < 0.0 else 0)
    sign_match = (claim_sign == slope_sign)

    if claim_sign == 0:
        support = "supported" if p_val > P_WEAK else "neutral"
    elif sign_match:
        if p_val <= P_STRONG:
            support = "strongly_supported"
        elif p_val <= P_WEAK:
            support = "supported"
        else:
            support = "neutral"
    else:
        if p_val <= P_STRONG:
            support = "strongly_contradicted"
        elif p_val <= P_WEAK:
            support = "contradicted"
        else:
            support = "neutral"

    summary = (
        f"Δ{series_a.series_id} → Δ{series_b.series_id} | "
        f"Spearman r={rho:.3f}, OLS slope={slope:.4f}, p={p_val:.3f}, "
        f"n={len(da)} annual first-differences | "
        f"claim={claim.direction}, data slope={'positive' if slope > 0 else 'negative'}"
    )

    return AlignmentStats(
        claim_index=idx,
        series_a_id=series_a.series_id,
        series_b_id=series_b.series_id if series_b else None,
        correlation=round(float(rho), 4),
        slope=round(float(slope), 4),
        p_value=round(float(p_val), 4),
        n_obs=len(common),
        cv_a=round(cv_a, 5),
        statistical_support=support,
        data_summary=summary,
    )
