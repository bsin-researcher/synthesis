"""
QQA (Quantitative-Qualitative Alignment) — main scoring pipeline.

Support levels are determined by statistical tests in stats.py.
Claude's role is ONLY to write the plain-English explanation citing
the actual numbers — it does NOT decide the verdict.
"""

import json
import anthropic
import pandas as pd
from dataclasses import dataclass
from synthesis.extraction.claims import Claim
from synthesis.data.fred import DataSeries
from synthesis.alignment.stats import (
    AlignmentStats,
    map_variables_to_series,
    compute_alignment_stats,
)


SUPPORT_LEVELS = {
    "strongly_supported":     2,
    "supported":              1,
    "neutral":                0,
    "contradicted":          -1,
    "strongly_contradicted": -2,
    "insufficient_variation": None,
    "no_data":                None,
}

# Map stats module names → legacy "insufficient_data" for backwards compat in report
_DISPLAY_MAP = {
    "insufficient_variation": "insufficient_data",
    "no_data":                "insufficient_data",
}


@dataclass
class AlignmentResult:
    claim: Claim
    support_level: str        # from SUPPORT_LEVELS
    support_score: int | None
    data_series_used: list[str]
    explanation: str          # one sentence, cites actual statistics
    stats: AlignmentStats | None = None


def score_alignment(
    claims: list[Claim],
    data_series: list[DataSeries],
    client: anthropic.Anthropic,
) -> list[AlignmentResult]:
    if not claims or not data_series:
        return []

    # Step 1: Map claim variables to data series (cheap Claude call, no thinking)
    mapping = map_variables_to_series(claims, data_series, client)

    # Step 2: Compute statistical alignment (pure Python/scipy — no Claude)
    stat_list = compute_alignment_stats(claims, data_series, mapping)

    # Step 3: Ask Claude to explain each result in plain English
    # Claude sees the numbers and writes ONE sentence per claim.
    # It does NOT decide the support level.
    stats_context = "\n".join(
        f"[{s.claim_index + 1}] verdict={s.statistical_support} | {s.data_summary}"
        for s in stat_list
    )
    claims_text = "\n".join(
        f"[{i + 1}] {c.variable_a} → {c.variable_b} ({c.direction}) | "
        f"method: {c.methodology} | finding: {c.finding}"
        for i, c in enumerate(claims)
    )

    prompt = f"""You are an econometrician explaining statistical alignment results in plain English.

CLAIMS:
{claims_text}

STATISTICAL RESULTS (already computed — do NOT override the verdict):
{stats_context}

For each claim, write ONE precise sentence explaining what the statistics mean in economic terms.
Reference specific numbers (correlation, slope, p-value, CV) where available.
If the verdict is insufficient_variation, explain WHY (e.g., "the minimum wage has been
frozen at $7.25 since 2009, so Δ series has near-zero variance and cannot identify any effect").

Return a JSON array:
- claim_index: int (1-based)
- explanation: one sentence

Return ONLY the JSON array."""

    explanations: dict[int, str] = {}
    try:
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        for item in json.loads(raw.strip()):
            explanations[int(item["claim_index"]) - 1] = item.get("explanation", "")
    except Exception:
        pass

    results = []
    for i, (claim, stat) in enumerate(zip(claims, stat_list)):
        raw_level = stat.statistical_support
        display_level = _DISPLAY_MAP.get(raw_level, raw_level)
        explanation = explanations.get(i, stat.data_summary)
        used = [s for s in [stat.series_a_id, stat.series_b_id] if s]
        results.append(AlignmentResult(
            claim=claim,
            support_level=display_level,
            support_score=SUPPORT_LEVELS.get(raw_level),
            data_series_used=used,
            explanation=explanation,
            stats=stat,
        ))

    return results


def _series_to_trend(s: DataSeries, max_points: int = 12) -> str:
    """Annual time series as 'year: value' pairs."""
    df = s.data.dropna(subset=["value"]).copy()
    if df.empty:
        return "no data"
    df["year"] = pd.to_datetime(df["date"]).dt.year
    annual = df.groupby("year")["value"].last().tail(max_points)
    return " | ".join(f"{yr}: {round(val, 2)}" for yr, val in annual.items())


def build_gap_matrix(claims: list[Claim]) -> dict:
    seen = set()
    for c in claims:
        seen.add((c.methodology, c.geography, c.time_period))

    methodologies = {"RCT", "DiD", "IV", "OLS", "structural", "meta-analysis", "natural_experiment"}
    geographies = {c.geography for c in claims}
    gaps = []

    for method in methodologies:
        for geo in geographies:
            if not any(m == method and g == geo for m, g, _ in seen):
                gaps.append({"methodology": method, "geography": geo,
                             "note": f"No {method} study found for {geo}"})

    contested = [c for c in claims if c.confidence in ("low", "contested")]

    return {
        "total_claims": len(claims),
        "methodologies_covered": list({c.methodology for c in claims}),
        "geographies_covered": list({c.geography for c in claims}),
        "unstudied_combinations": gaps[:8],
        "contested_claims": [c.finding for c in contested],
    }
