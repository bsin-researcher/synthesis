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
    "literature_only":        None,
}

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
    explanation: str
    stats: AlignmentStats | None = None
    testability: str = "testable"  # "testable" | "untestable"


def _assess_testability(
    claims: list[Claim],
    data_series: list[DataSeries],
    client: anthropic.Anthropic,
) -> dict[int, str]:
    """
    Returns {0-based claim index: "testable"|"untestable"}.

    A claim is testable only when the available series genuinely proxy its
    variables at the same geographic and sectoral resolution. Claims about
    specific foreign countries, sub-national regions, or structural model
    constructs with no observable counterpart are marked untestable and
    skipped — preventing the report from filling with INSUFFICIENT_DATA rows.
    """
    series_desc = "\n".join(
        f"  {s.series_id}: {s.title} ({s.units})"
        for s in data_series
    )
    claims_text = "\n".join(
        f"  [{i + 1}] cause='{c.variable_a}' effect='{c.variable_b}' "
        f"geo={c.geography or 'unspecified'} method={c.methodology or 'unspecified'}"
        for i, c in enumerate(claims)
    )

    prompt = f"""Judge whether each claim can be statistically tested with the available data series.

TESTABLE: available series proxy BOTH variables at the same geographic/sectoral scope as the claim.
UNTESTABLE if any of these apply:
- Claim is about a specific foreign country (Germany, Hungary, Bangladesh, etc.) but only US/global data available
- Claim is sub-national (NJ/PA border, specific cities) but only national aggregates available
- Claim derives from a theoretical/structural model with no directly observable counterpart
- No series exists that plausibly proxies the key variable

AVAILABLE SERIES:
{series_desc}

CLAIMS TO EVALUATE:
{claims_text}

Return ONLY a JSON array — no explanation:
[{{"claim_index": 1, "testability": "testable"}}, ...]"""

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
        items = json.loads(raw.strip())
        return {
            int(item["claim_index"]) - 1: item.get("testability", "untestable")
            for item in items
        }
    except Exception:
        # Default to testable on parse failure so stats still run
        return {i: "testable" for i in range(len(claims))}


def score_alignment(
    claims: list[Claim],
    data_series: list[DataSeries],
    client: anthropic.Anthropic,
) -> list[AlignmentResult]:
    if not claims or not data_series:
        return []

    # Step 0: Pre-filter — only run stats on claims the data can actually test
    testability_map = _assess_testability(claims, data_series, client)
    testable_indices = [i for i in range(len(claims)) if testability_map.get(i) == "testable"]
    testable_claims = [claims[i] for i in testable_indices]

    stat_list: list = []
    explanations: dict[int, str] = {}

    if testable_claims:
        # Step 1: Map variables to series (only for testable claims)
        mapping = map_variables_to_series(testable_claims, data_series, client)

        # Step 2: Compute statistical alignment (pure Python/scipy)
        stat_list = compute_alignment_stats(testable_claims, data_series, mapping)

        # Step 3: Claude writes plain-English explanations (does NOT decide verdict)
        stats_context = "\n".join(
            f"[{j + 1}] verdict={s.statistical_support} | {s.data_summary}"
            for j, s in enumerate(stat_list)
        )
        claims_for_explain = "\n".join(
            f"[{j + 1}] {c.variable_a} → {c.variable_b} ({c.direction}) | "
            f"method: {c.methodology} | finding: {c.finding}"
            for j, c in enumerate(testable_claims)
        )

        explain_prompt = f"""You are an econometrician explaining statistical results in plain English.

CLAIMS:
{claims_for_explain}

STATISTICAL RESULTS (already computed — do NOT override the verdict):
{stats_context}

For each claim, write ONE precise sentence citing the actual statistics.
If the verdict is insufficient_variation, explain WHY (e.g., "the minimum wage has been
frozen at $7.25 since 2009, so Δ series has near-zero variance and cannot identify any effect").

Return a JSON array:
[{{"claim_index": 1, "explanation": "one sentence"}}, ...]

Return ONLY the JSON array."""

        try:
            resp = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=2048,
                messages=[{"role": "user", "content": explain_prompt}],
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

    # Assemble results preserving original claim order
    results: list[AlignmentResult | None] = [None] * len(claims)

    for j, (claim, stat) in enumerate(zip(testable_claims, stat_list)):
        original_i = testable_indices[j]
        raw_level = stat.statistical_support
        display_level = _DISPLAY_MAP.get(raw_level, raw_level)
        used = [s for s in [stat.series_a_id, stat.series_b_id] if s]
        results[original_i] = AlignmentResult(
            claim=claim,
            support_level=display_level,
            support_score=SUPPORT_LEVELS.get(raw_level),
            data_series_used=used,
            explanation=explanations.get(j, stat.data_summary),
            stats=stat,
            testability="testable",
        )

    for i, claim in enumerate(claims):
        if results[i] is None:
            geo = claim.geography or "unspecified geography"
            results[i] = AlignmentResult(
                claim=claim,
                support_level="literature_only",
                support_score=None,
                data_series_used=[],
                explanation=(
                    f"Claim scope ({geo}) does not match available data resolution — "
                    f"recorded in literature inventory only."
                ),
                stats=None,
                testability="untestable",
            )

    return [r for r in results if r is not None]


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
