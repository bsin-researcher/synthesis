"""
Effect size extraction from paper abstracts.

Claude extracts ONLY explicit numerical estimates — no inference, no fabrication.
Papers that only say "significant positive effect" without a number are skipped.
"""

import json
import anthropic
from dataclasses import dataclass
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
) -> list[EffectSize]:
    if not papers:
        return []

    papers_text = "\n\n".join(
        f"[{i + 1}] Title: {p.title[:80]}\n"
        f"Citations: {p.citations}\n"
        f"Abstract: {(p.abstract or '')[:600]}"
        for i, p in enumerate(papers[:20])
    )

    prompt = f"""You are extracting quantitative effect size estimates from economics paper abstracts.

RESEARCH QUESTION: {question}

TASK: For each paper below, extract the PRIMARY numerical finding ONLY if:
1. The abstract states an explicit number (e.g., "-0.3%", "elasticity of -0.1", "2,000 jobs lost")
2. The finding directly addresses the research question
3. The finding is the headline result, not a robustness check

For each paper that qualifies, return:
- paper_index: 1-based index from the list
- paper_title: 40 characters max
- estimate: point estimate as a float
- lower_ci: lower 95% CI bound as float, or null if not reported
- upper_ci: upper 95% CI bound as float, or null if not reported
- unit: brief description of what the number means (e.g., "employment elasticity w.r.t. minimum wage")
- methodology: DiD / RCT / IV / OLS / meta-analysis / structural / other
- geography: country or region (e.g., US, UK, Global)

CRITICAL RULES:
- Skip papers with only vague language ("significant", "positive effect", "about X%")
- Do NOT invent or infer numbers not in the abstract
- One entry per paper maximum (the headline result)

PAPERS:
{papers_text}

Return ONLY a JSON array. Empty array [] if none qualify."""

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
