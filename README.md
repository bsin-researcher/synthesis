# Synthesis

**AI-powered economics research briefs combining qualitative literature and quantitative data.**

Synthesis retrieves papers from arXiv, OpenAlex, and NBER, extracts structured empirical claims using Claude, pulls FRED and World Bank time-series data, and scores theory against evidence using a novel **Quantitative-Qualitative Alignment (QQA)** method — all in a single command.

```bash
synthesis "Does raising the minimum wage increase unemployment?"
```

→ Generates an 8-section PhD-level research brief with interactive charts and a gap matrix in under 2 minutes.

---

## What It Produces

- **Literature consensus** across 20+ papers with identified fault lines
- **Extracted claims** structured by variable, direction, methodology, geography, and confidence
- **Empirical data** from FRED (US macro) and World Bank (cross-country)
- **QQA alignment scores** — each theoretical claim scored against empirical data
- **Research gap matrix** — unstudied methodology × geography combinations
- **Suggested research directions** with identification strategies
- **Interactive HTML report** with Plotly charts (zoomable, hoverable)

---

## The Core Idea: QQA

Most research tools do one of two things: search literature (qualitative) or fetch data (quantitative). **Synthesis does both and aligns them.**

The Quantitative-Qualitative Alignment (QQA) method:
1. Extracts structured claims from paper abstracts: `variable_a → variable_b | direction | methodology | geography | confidence`
2. Fetches empirical data relevant to the question via Claude-identified FRED and World Bank series
3. Scores each claim against the data: `strongly_supported / supported / neutral / contradicted / strongly_contradicted / insufficient_data`
4. Identifies where the literature and data diverge — the most productive place for new research

---

## Quick Start

```bash
pip install synthesis-econ
```

Set your API keys (get them free):
- [Anthropic API key](https://console.anthropic.com/) — for Claude
- [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) — for US macro data

```bash
export ANTHROPIC_API_KEY='sk-ant-...'
export FRED_API_KEY='your-fred-key'
```

Run a research brief:
```bash
synthesis "Does immigration lower wages for native workers?"
synthesis "What is the effect of quantitative easing on inflation?"
synthesis "Do charter schools improve student outcomes?"
synthesis "Does foreign aid promote economic growth?"
```

The HTML report opens automatically in your browser.

---

## Install from Source

```bash
git clone https://github.com/bsin-researcher/synthesis.git
cd synthesis
pip install -e .
```

---

## How It Works

```
Your question
    │
    ├── arXiv  (economics: econ.GN, econ.EM, econ.LG, econ.TH, econ.HE, econ.IO)
    ├── OpenAlex  (250M+ peer-reviewed works)
    └── NBER  (64K+ working papers)
           │
           ▼
    Claude extracts structured claims
    (variable_a → variable_b, direction, methodology, geography, confidence)
           │
           ├── FRED  (US macro time-series — series IDs chosen by Claude)
           └── World Bank  (cross-country indicators — chosen by Claude)
                  │
                  ▼
           QQA Alignment Scoring
           (theory vs. data, claim by claim)
                  │
                  ▼
           Research Gap Matrix
           (unstudied methodology × geography combinations)
                  │
                  ▼
    8-section research brief + interactive Plotly HTML report
```

---

## Example Output

**Question:** Does raising the minimum wage increase unemployment?

**Papers:** 22 (arXiv: 8, OpenAlex: 8, NBER: 8, 2 duplicates removed)  
**Claims extracted:** 14  
**FRED series:** Federal Minimum Wage, Unemployment Rate, Nonfarm Payrolls, Labor Force Participation  
**World Bank series:** Unemployment total (% of labor force), Labor Force Participation  
**Pooled estimate:** NEGATIVE −0.17 (weighted by method quality × confidence × citations)

**Statistical QQA results (actual tests, not summaries):**
- ΔSTTMINWGFG → ΔUNRATE: Spearman r=0.239, OLS slope=+2.29, **p=0.034** — significant but cycle-confounded
- ΔSTTMINWGFG → ΔPAYEMS: Spearman r=−0.422, OLS slope=−5705, **p=0.036** — supports disemployment direction
- Federal minimum frozen at $7.25 since 2009: CV of Δ=0.00031 → correctly flagged as **insufficient_variation**

> **Verdict:** Directionally negative, small, margin-shifting, and badly under-identified at the level where policy actually binds. Adjustment runs through hours and slowed hiring, not stock job losses.
>
> **Top gap:** Contiguous-county-pair DiD on the post-2009 real-minimum-wage decline — tests the inverse natural experiment (falling real floor) that no one has run.

---

## Benchmark: Synthesis vs. Consensus

Same question: *"Does raising the minimum wage increase unemployment?"*

| | **Synthesis** | **Consensus** |
|--|--|--|
| Papers retrieved | 22 (3 sources, deduplicated) | 16 |
| Verdict | NEGATIVE −0.17 (weighted pooled) | 56% No, 31% Yes |
| Quantitative data | FRED + World Bank (6 series) | None |
| Statistical tests | Spearman r, OLS slope, p-values | None |
| Confound detection | Flagged business-cycle contamination | Not mentioned |
| Research gap matrix | 8 unstudied method × geography cells | None |
| Research directions | 5 with identification strategies | None |
| Citation weighting | Yes (log-scaled by paper citations) | Unknown |

**Consensus** is excellent for a quick literature read — intuitive verdict meter, clean country table, fast. Use it to find out *what* the literature says.

**Synthesis** is for researchers who need to know *why* the data can or can't test a claim, *where* the gaps are, and *how* to close them. It is the only tool that aligns theoretical claims against real economic data with actual statistical tests.

---

## Data Sources

| Source | Coverage | Key |
|--------|----------|-----|
| arXiv | Economics preprints (7 categories) | None required |
| OpenAlex | 250M+ peer-reviewed works | None required |
| NBER | 64K+ working papers | None required |
| FRED | 800K+ US macro time-series | Free API key |
| World Bank | Cross-country development indicators | None required |

---

## Options

```
synthesis "question" [OPTIONS]

  -o, --output TEXT    Output directory  [default: ./synthesis_output]
  -p, --papers INT     Max papers to retrieve  [default: 24]
  --no-fred            Skip FRED data
  --no-worldbank       Skip World Bank data
```

---

## Requirements

- Python 3.10+
- Anthropic API key (uses Claude Opus 4.8 with adaptive thinking)
- FRED API key (free, optional but strongly recommended)

```
anthropic>=0.109.0
requests>=2.34.0
pandas>=2.0.0
plotly>=5.20.0
rich>=13.0.0
typer>=0.9.0
python-dotenv>=1.0.0
```

---

## Roadmap

- [x] arXiv + OpenAlex + NBER retrieval with deduplication (DOI + title)
- [x] Claude-powered structured claim extraction (adaptive thinking, citations included)
- [x] FRED + World Bank empirical data (series chosen by Claude)
- [x] Statistical QQA — Spearman r + OLS on first differences, p-value thresholds, flat-series detection
- [x] Citation-weighted meta-analytic pooling (method quality × confidence × log citations)
- [x] Research gap matrix (unstudied methodology × geography combinations)
- [x] Interactive Plotly HTML report with pooled evidence card
- [x] Benchmark vs Consensus (see table above)
- [ ] Confidence intervals on pooled score (bootstrap)
- [ ] Semantic deduplication across sources (sentence-transformers)
- [ ] PDF and LaTeX export
- [ ] Jupyter notebook mode

---

## Citation

If you use Synthesis in your research:

```bibtex
@software{sinclair2026synthesis,
  author  = {Sinclair, Blake},
  title   = {Synthesis: AI-Powered Economics Research via Quantitative-Qualitative Alignment},
  year    = {2026},
  url     = {https://github.com/bsin-researcher/synthesis},
}
```

---

## Contributing

Pull requests welcome. The highest-value open items are in the roadmap above.

To add a new data source, implement the pattern in `synthesis/data/` — a function `fetch_X(question: str, client: anthropic.Anthropic) -> list[DataSeries]` and wire it into `synthesis/cli.py`.

---

## License

MIT
