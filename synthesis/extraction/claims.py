import json
import anthropic
from dataclasses import dataclass


@dataclass
class Claim:
    variable_a: str
    variable_b: str
    direction: str        # positive / negative / ambiguous / nonlinear / no_effect
    magnitude: str        # small / moderate / large / unclear
    methodology: str      # RCT / DiD / IV / OLS / structural / meta-analysis / other
    geography: str
    time_period: str
    confidence: str       # high / moderate / low / contested
    finding: str          # one-sentence plain English summary
    effect_size: str      # numerical estimate if reported, e.g. "-0.1 to -0.3 elasticity"
    paper_title: str
    paper_url: str
    citations: int = 0    # citation count of the source paper


def extract_claims(papers: list, question: str, client: anthropic.Anthropic) -> list[Claim]:
    if not papers:
        return []

    # Build citation lookup for use after extraction
    citation_lookup: dict[str, int] = {p.title: getattr(p, "citations", 0) for p in papers}

    abstracts_text = ""
    for i, p in enumerate(papers[:20], 1):
        authors = ", ".join(p.authors[:2]) + (" et al." if len(p.authors) > 2 else "")
        cite_str = f"Citations: {p.citations}\n" if getattr(p, "citations", 0) > 0 else ""
        abstracts_text += f"\n[{i}] {p.title}\nAuthors: {authors} ({p.published})\n{cite_str}{p.abstract}\nURL: {p.url}\n"

    prompt = f"""You are an expert economist extracting structured research claims from paper abstracts.

Research question: "{question}"

Papers:
{abstracts_text}

For each paper that makes a relevant empirical or theoretical claim about the research question, extract up to TWO distinct claims. Only extract a second claim if it is meaningfully different from the first (e.g., different outcome variable, different subgroup, or a key heterogeneous effect).

Return a JSON array. Each item must have exactly these fields:
- variable_a: the independent variable or cause (string)
- variable_b: the dependent variable or effect (string)
- direction: one of "positive", "negative", "ambiguous", "nonlinear", "no_effect"
- magnitude: one of "small", "moderate", "large", "unclear"
- methodology: one of "RCT", "DiD", "IV", "OLS", "structural", "meta-analysis", "natural_experiment", "survey", "theoretical", "other"
- geography: the geographic scope (e.g., "United States", "OECD", "global", "developing countries")
- time_period: approximate period studied (e.g., "1990-2010", "post-2008", "long-run")
- confidence: one of "high", "moderate", "low", "contested"
- finding: one sentence in plain English summarizing the key finding
- effect_size: the numerical effect size if reported (e.g., "-0.1 to -0.3 elasticity", "1-2pp employment loss", "10% wage increase → 0.5% unemployment increase"); write "unclear" if no number is given
- paper_title: the paper title exactly as given
- paper_url: the URL exactly as given

Only include papers with clear empirical or theoretical claims relevant to the question.
Return ONLY the JSON array, no other text."""

    resp = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )

    raw = ""
    for block in resp.content:
        if block.type == "text":
            raw = block.text.strip()
            break

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []

    claims = []
    for item in items:
        try:
            kwargs = {k: str(v) for k, v in item.items() if k != "citations"}
            # Inject citation count from paper lookup
            title = kwargs.get("paper_title", "")
            kwargs["citations"] = citation_lookup.get(title, 0)
            claims.append(Claim(**kwargs))
        except (TypeError, KeyError):
            pass
    return claims
