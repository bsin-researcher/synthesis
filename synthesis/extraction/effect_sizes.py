"""
Effect size extraction for forest plots.

Primary path: parse the structured Claim.effect_size strings that claims.py
already extracted (e.g. "-0.1 to -0.3 elasticity", "1-2pp employment loss").
These are richer than raw abstracts because the claim extractor already found
the headline number.

Fallback path: if no claims are supplied, try to extract directly from abstracts
(less reliable — numbers are rarely in abstracts rather than tables).
"""

import json
import anthropic
from dataclasses import dataclass
from synthesis.extraction.claims import Claim
from synthesis.retrieval.arxiv import Paper


@dataclass
class EffectSize:
    paper_title: str
    estimate: float
    lower_ci: float | None
    upper_ci: float | None
    unit: str
    citations: int
    methodology: str
    geography: str


def extract_effect_sizes(
    papers: list[Paper],
    question: str,
    client: anthropic.Anthropic,
    claims: list[Claim] | None = None,
) -> list[EffectSize]:
    """
    If claims are provided, parse their effect_size strings into floats.
    Otherwise, attempt extraction from raw paper abstracts.
    """
    if claims:
        return _from_claims(claims, client)
    return _from_abstracts(papers, question, client)


def _from_claims(claims: list[Claim], client: anthropic.Anthropic) -> list[EffectSize]:
    """Parse Claim.effect_size strings into numerical EffectSize objects."""
    candidates = [c for c in claims if c.effect_size.lower() not in ("unclear", "unknown", "")]
    if not candidates:
        return []

    claims_text = "\n".join(
        f"[{i + 1}] paper=\"{c.paper_title[:50]}\" "
        f"effect_size=\"{c.effect_size}\" "
        f"direction={c.direction} "
        f"method={c.methodology} geo={c.geography}"
        for i, c in enumerate(candidates)
    )

    prompt = f"""Parse each effect size string below into a numerical estimate.

Rules:
- If a range is given (e.g. "-0.1 to -0.3"), use the midpoint as estimate and the bounds as CI
- If a conditional is given (e.g. "10% wage increase → 0.5% unemployment rise"),
  express as a signed coefficient (positive = same direction as stated)
- If the effect_size string contains no discernible number, return null for that item
- Negative direction claims should have negative estimates where appropriate
- unit: brief description of what the number measures (e.g. "employment elasticity")

Return a JSON array — one item per claim index:
- claim_index: int (1-based)
- estimate: float or null
- lower_ci: float or null (lower bound of range/CI, or null)
- upper_ci: float or null (upper bound of range/CI, or null)
- unit: string describing the scale

CLAIMS:
{claims_text}

Return ONLY the JSON array."""

    try:
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        items = json.loads(raw.strip())
    except Exception:
        return []

    results = []
    for item in items:
        try:
            if item.get("estimate") is None:
                continue
            idx = int(item["claim_index"]) - 1
            if not (0 <= idx < len(candidates)):
                continue
            c = candidates[idx]
            results.append(EffectSize(
                paper_title=c.paper_title[:45],
                estimate=float(item["estimate"]),
                lower_ci=float(item["lower_ci"]) if item.get("lower_ci") is not None else None,
                upper_ci=float(item["upper_ci"]) if item.get("upper_ci") is not None else None,
                unit=str(item.get("unit", "effect size"))[:80],
                citations=c.citations,
                methodology=c.methodology,
                geography=c.geography,
            ))
        except (KeyError, ValueError, TypeError):
            continue

    return results


def _from_abstracts(
    papers: list[Paper],
    question: str,
    client: anthropic.Anthropic,
) -> list[EffectSize]:
    """Fallback: extract explicit numbers from raw abstracts."""
    if not papers:
        return []

    papers_text = "\n\n".join(
        f"[{i + 1}] Title: {p.title[:80]}\n"
        f"Citations: {p.citations}\n"
        f"Abstract: {(p.abstract or '')[:600]}"
        for i, p in enumerate(papers[:20])
    )

    prompt = f"""Extract quantitative effect size estimates from economics paper abstracts.

RESEARCH QUESTION: {question}

For each paper, extract the PRIMARY numerical finding ONLY if the abstract
contains an explicit number (approximate values like "roughly 0.3%" are fine).
Skip papers with only vague language ("significant", "positive effect").

Return a JSON array — one item per qualifying paper:
- paper_index: 1-based index
- paper_title: ≤45 characters
- estimate: float (midpoint if range given)
- lower_ci: float or null
- upper_ci: float or null
- unit: what the number measures
- methodology: DiD / RCT / IV / OLS / meta-analysis / other
- geography: country or region

PAPERS:
{papers_text}

Return ONLY a JSON array (empty [] if none qualify)."""

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
        items = json.loads(raw.strip())
    except Exception:
        return []

    results = []
    for item in items:
        try:
            idx = int(item.get("paper_index", 1)) - 1
            citations = papers[idx].citations if 0 <= idx < len(papers) else 0
            results.append(EffectSize(
                paper_title=str(item.get("paper_title", "Unknown"))[:45],
                estimate=float(item["estimate"]),
                lower_ci=float(item["lower_ci"]) if item.get("lower_ci") is not None else None,
                upper_ci=float(item["upper_ci"]) if item.get("upper_ci") is not None else None,
                unit=str(item.get("unit", "effect size"))[:80],
                citations=citations,
                methodology=str(item.get("methodology", "unknown")),
                geography=str(item.get("geography", "unknown")),
            ))
        except (KeyError, ValueError, TypeError):
            continue

    return results
