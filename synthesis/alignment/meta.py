"""
Meta-analytic pooling for Synthesis.

Weights each extracted claim by methodology quality × confidence × log(citations+1),
then computes a pooled direction score and consensus statement.
"""

import math
from dataclasses import dataclass
from synthesis.extraction.claims import Claim


# Evidence hierarchy — standard in meta-analysis
METHOD_WEIGHTS: dict[str, int] = {
    "RCT":                5,
    "IV":                 4,
    "DiD":                4,
    "natural_experiment": 4,
    "meta-analysis":      3,
    "structural":         2,
    "OLS":                2,
    "survey":             1,
    "theoretical":        1,
    "other":              1,
}

CONFIDENCE_MULT: dict[str, float] = {
    "high":      1.0,
    "moderate":  0.6,
    "low":       0.3,
    "contested": 0.2,
}

DIRECTION_SCORE: dict[str, float] = {
    "positive":  1.0,
    "negative":  -1.0,
    "no_effect":  0.0,
    "ambiguous":  0.0,
    "nonlinear":  0.0,
}


@dataclass
class PooledEvidence:
    # Core pooled estimate
    pooled_direction: str          # "positive" / "negative" / "no_effect" / "mixed"
    weighted_score: float          # -1.0 to +1.0
    total_weight: float

    # Direction breakdown
    n_positive: int
    n_negative: int
    n_no_effect: int
    n_ambiguous: int
    n_claims: int

    # Quality
    high_confidence_count: int
    top_methods: list[str]         # top 3 methods by total weight

    # Effect sizes (raw strings from extraction)
    effect_sizes: list[str]

    # Human-readable summary sentence
    consensus_statement: str


def pool_evidence(claims: list[Claim]) -> PooledEvidence:
    if not claims:
        return PooledEvidence(
            pooled_direction="insufficient_data", weighted_score=0.0,
            total_weight=0.0, n_positive=0, n_negative=0, n_no_effect=0,
            n_ambiguous=0, n_claims=0, high_confidence_count=0,
            top_methods=[], effect_sizes=[], consensus_statement="No claims to pool.",
        )

    weighted_sum = 0.0
    total_w = 0.0
    direction_counts: dict[str, int] = {"positive": 0, "negative": 0,
                                         "no_effect": 0, "ambiguous": 0, "nonlinear": 0}
    method_weights: dict[str, float] = {}
    high_conf = 0
    effect_sizes: list[str] = []

    for c in claims:
        mw = METHOD_WEIGHTS.get(c.methodology, 1)
        cw = CONFIDENCE_MULT.get(c.confidence, 0.3)
        cite_w = math.log(getattr(c, "citations", 0) + 1) + 1  # +1 floor so uncited claims still count
        weight = mw * cw * cite_w

        d = c.direction if c.direction in DIRECTION_SCORE else "ambiguous"
        direction_counts[d] = direction_counts.get(d, 0) + 1
        weighted_sum += DIRECTION_SCORE[d] * weight
        total_w += weight

        method_weights[c.methodology] = method_weights.get(c.methodology, 0.0) + weight

        if c.confidence == "high":
            high_conf += 1

        es = getattr(c, "effect_size", "")
        if es and es not in ("unclear", "", "not reported", "N/A"):
            effect_sizes.append(f"{c.paper_title[:40]}… — {es}")

    norm_score = weighted_sum / total_w if total_w > 0 else 0.0

    # Determine pooled direction
    if abs(norm_score) < 0.15:
        pooled_dir = "no_effect"
    elif norm_score > 0:
        pooled_dir = "positive"
    else:
        pooled_dir = "negative"

    # Check for genuine disagreement
    n_directional = direction_counts["positive"] + direction_counts["negative"]
    if n_directional >= 2:
        minority = min(direction_counts["positive"], direction_counts["negative"])
        if minority / n_directional >= 0.35:
            pooled_dir = "mixed"

    top_methods = sorted(method_weights, key=method_weights.get, reverse=True)[:3]

    consensus_statement = _build_statement(
        pooled_dir, norm_score, direction_counts, high_conf, len(claims), top_methods
    )

    return PooledEvidence(
        pooled_direction=pooled_dir,
        weighted_score=round(norm_score, 3),
        total_weight=round(total_w, 1),
        n_positive=direction_counts["positive"],
        n_negative=direction_counts["negative"],
        n_no_effect=direction_counts["no_effect"],
        n_ambiguous=direction_counts.get("ambiguous", 0) + direction_counts.get("nonlinear", 0),
        n_claims=len(claims),
        high_confidence_count=high_conf,
        top_methods=top_methods,
        effect_sizes=effect_sizes[:6],
        consensus_statement=consensus_statement,
    )


def _build_statement(
    direction: str,
    score: float,
    counts: dict[str, int],
    high_conf: int,
    n: int,
    methods: list[str],
) -> str:
    method_str = " + ".join(methods) if methods else "various methods"
    conf_str = f"{high_conf} high-confidence" if high_conf else "no high-confidence"

    if direction == "negative":
        strength = "strongly" if score < -0.6 else "moderately"
        return (
            f"Pooled evidence ({conf_str} of {n} claims via {method_str}) "
            f"{strength} supports a NEGATIVE effect (weighted score {score:+.2f}). "
            f"{counts['positive']} claims find positive, {counts['negative']} negative, "
            f"{counts['no_effect']} no effect."
        )
    elif direction == "positive":
        strength = "strongly" if score > 0.6 else "moderately"
        return (
            f"Pooled evidence ({conf_str} of {n} claims via {method_str}) "
            f"{strength} supports a POSITIVE effect (weighted score {score:+.2f}). "
            f"{counts['positive']} claims find positive, {counts['negative']} negative, "
            f"{counts['no_effect']} no effect."
        )
    elif direction == "no_effect":
        return (
            f"Pooled evidence ({conf_str} of {n} claims via {method_str}) "
            f"finds NO CLEAR EFFECT (weighted score {score:+.2f}). "
            f"{counts['no_effect']} claims find no effect, "
            f"{counts['positive']} positive, {counts['negative']} negative."
        )
    else:  # mixed
        return (
            f"Evidence is MIXED across {n} claims via {method_str} "
            f"(weighted score {score:+.2f}, {conf_str} findings). "
            f"{counts['positive']} positive vs {counts['negative']} negative — "
            f"genuine disagreement in the literature."
        )
