"""
Quantitative-Qualitative Alignment (QQA)

The core technical contribution of Synthesis.

For each theoretical claim extracted from the literature, QQA scores how well
the empirical data supports, contradicts, or fails to address it.
It then builds a gap matrix identifying which claim types lack empirical coverage.
"""

import json
import anthropic
from dataclasses import dataclass
from synthesis.extraction.claims import Claim
from synthesis.data.fred import DataSeries


SUPPORT_LEVELS = {
    "strongly_supported": 2,
    "supported": 1,
    "neutral": 0,
    "contradicted": -1,
    "strongly_contradicted": -2,
    "insufficient_data": None,
}


@dataclass
class AlignmentResult:
    claim: Claim
    support_level: str       # from SUPPORT_LEVELS
    support_score: int | None
    data_series_used: list[str]
    explanation: str         # one sentence


def score_alignment(
    claims: list[Claim],
    data_series: list[DataSeries],
    client: anthropic.Anthropic,
) -> list[AlignmentResult]:
    if not claims or not data_series:
        return []

    data_summaries = "\n".join(
        f"- {s.series_id}: {s.title} | units: {s.units} | "
        f"latest: {s.summary().get('latest_value')} | "
        f"range: {s.summary().get('min')}–{s.summary().get('max')} | "
        f"period: {s.summary().get('start')} to {s.summary().get('end')}"
        for s in data_series
    )

    claims_text = "\n".join(
        f"[{i}] {c.variable_a} → {c.variable_b} | direction: {c.direction} | "
        f"method: {c.methodology} | confidence: {c.confidence} | finding: {c.finding}"
        for i, c in enumerate(claims, 1)
    )

    prompt = f"""You are an expert quantitative economist assessing how well empirical data supports theoretical claims from the literature.

LITERATURE CLAIMS:
{claims_text}

AVAILABLE EMPIRICAL DATA:
{data_summaries}

For each claim, assess how well the available data supports or contradicts it.

Return a JSON array with one item per claim (same order). Each item:
- claim_index: integer (1-based, matching claim number above)
- support_level: one of "strongly_supported", "supported", "neutral", "contradicted", "strongly_contradicted", "insufficient_data"
- data_series_used: list of FRED series IDs used in this assessment (empty list if none relevant)
- explanation: one sentence explaining the alignment or why data is insufficient

Return ONLY the JSON array."""

    resp = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )

    raw = ""
    for block in resp.content:
        if block.type == "text":
            raw = block.text.strip()
            break

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        scored = json.loads(raw)
    except json.JSONDecodeError:
        return []

    results = []
    for item in scored:
        idx = item.get("claim_index", 1) - 1
        if 0 <= idx < len(claims):
            level = item.get("support_level", "insufficient_data")
            results.append(AlignmentResult(
                claim=claims[idx],
                support_level=level,
                support_score=SUPPORT_LEVELS.get(level),
                data_series_used=item.get("data_series_used", []),
                explanation=item.get("explanation", ""),
            ))
    return results


def build_gap_matrix(claims: list[Claim]) -> dict:
    """
    Identify understudied combinations of methodology × geography × time period.
    These are where new research opportunities live.
    """
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
