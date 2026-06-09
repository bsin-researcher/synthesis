import anthropic
from synthesis.extraction.claims import Claim
from synthesis.alignment.qqa import AlignmentResult, build_gap_matrix
from synthesis.data.fred import DataSeries


def generate_report(
    question: str,
    claims: list[Claim],
    alignment: list[AlignmentResult],
    data_series: list[DataSeries],
    client: anthropic.Anthropic,
) -> str:
    gap_matrix = build_gap_matrix(claims)

    claims_summary = "\n".join(
        f"- [{r.support_level.upper()}] {r.claim.variable_a} → {r.claim.variable_b} "
        f"({r.claim.direction}, {r.claim.methodology}, {r.claim.geography}): "
        f"{r.claim.finding} | Alignment: {r.explanation}"
        for r in alignment
    ) or "No claims extracted."

    uncovered = "\n".join(
        f"- {r.claim.finding} (confidence: {r.claim.confidence})"
        for r in alignment if r.support_level == "insufficient_data"
    ) or "All claims have some empirical coverage."

    data_summary = "\n".join(
        f"- {s.title} ({s.series_id}): latest {s.summary().get('latest_value')} {s.units}, "
        f"range {s.summary().get('min')}–{s.summary().get('max')}, "
        f"period {s.summary().get('start')} to {s.summary().get('end')}"
        for s in data_series
    ) or "No empirical data retrieved."

    gaps_text = "\n".join(
        f"- {g['note']}" for g in gap_matrix.get("unstudied_combinations", [])
    )
    contested_text = "\n".join(
        f"- {c}" for c in gap_matrix.get("contested_claims", [])
    )

    prompt = f"""You are a senior economics research analyst. Produce a structured Synthesis Research Brief combining qualitative literature analysis with quantitative empirical data.

RESEARCH QUESTION: "{question}"

LITERATURE CLAIMS WITH QQA ALIGNMENT SCORES:
{claims_summary}

EMPIRICAL DATA (FRED):
{data_summary}

CLAIMS WITH INSUFFICIENT EMPIRICAL COVERAGE:
{uncovered}

UNSTUDIED METHODOLOGY × GEOGRAPHY COMBINATIONS (research gaps):
{gaps_text}

CONTESTED CLAIMS IN THE LITERATURE:
{contested_text}

METHODOLOGIES COVERED: {', '.join(gap_matrix.get('methodologies_covered', []))}
GEOGRAPHIES COVERED: {', '.join(gap_matrix.get('geographies_covered', []))}

---

Produce the Synthesis Research Brief in this exact structure. Be direct, specific, and rigorous. No hedging without reason.

## 1. Research Question
Restate the question precisely.

## 2. Literature Consensus
What do the majority of studies find? State the dominant view and the strongest evidence supporting it. Name specific methodological approaches.

## 3. Where the Literature Disagrees
What are the active debates? Which findings are contested and why? What are the methodological fault lines?

## 4. What the Data Shows
Interpret the FRED empirical data directly. What trends, levels, and inflection points are relevant to the research question? Does the data confirm or challenge the dominant theoretical view?

## 5. Theory vs. Data: The Alignment
For each major claim, state whether the data supports, contradicts, or has insufficient coverage. This is the QQA summary. Be blunt — if the theory and the data disagree, say so.

## 6. Research Gaps (The Gap Matrix)
Based on methodology × geography × time period coverage, what has not been rigorously studied? These are the most promising directions for new research.

## 7. Suggested Research Directions
3–5 specific, actionable research questions that would advance knowledge most efficiently. For each: state the approach, the natural experiment or identification strategy, and why it would resolve a current gap.

## 8. One-Paragraph Research Memo
Write a concise research memo (5–7 sentences) that a PhD advisor or journal editor could read in 60 seconds. State the state of knowledge, the key empirical gap, and the most promising next study."""

    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=6000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text

    return full_text
