# Synthesis

**AI-powered economics research briefs — literature claims tested against real data.**

[![PyPI](https://img.shields.io/pypi/v/synthesis-econ)](https://pypi.org/project/synthesis-econ/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/synthesis-econ/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**[→ Live Demo](https://synthesis-mxqxkeygdnzx3rciazfpsj.streamlit.app)** — browse 6 pre-run research briefs instantly, no install required.

---

Synthesis retrieves papers from arXiv, OpenAlex, and NBER, extracts structured empirical claims using Claude, pulls FRED, World Bank, and BLS time-series data, and scores theory against evidence using **Quantitative-Qualitative Alignment (QQA)** — all in a single command.

```bash
synthesis "Does raising the minimum wage increase unemployment?"
```

Generates an 8-section research brief with interactive charts, a forest plot, and a gap matrix in under 3 minutes.

---

## What It Produces

- **Literature consensus** — pooled meta-analytic verdict across 20+ papers
- **Structured claims** — each paper's finding as: `variable_a → variable_b | direction | methodology | geography | confidence | effect_size`
- **Testability filter** — pre-screens claims against available data; only runs statistics on claims the data can actually test
- **QQA alignment** — Spearman correlation + OLS on first differences, with p-values, for each testable claim
- **Literature inventory** — untestable claims (wrong geography, sub-national scope, structural models) filed separately with explanation
- **Forest plot** — citation-weighted effect sizes across studies
- **Research gap matrix** — unstudied methodology × geography combinations
- **Suggested research directions** with identification strategies
- **Interactive HTML report** with Plotly charts

---

## The Core Idea: QQA

Most tools either search literature (qualitative) or fetch data (quantitative). Synthesis does both and aligns them.

```
Your question
    │
    ├── arXiv · OpenAlex · NBER  (20+ papers)
    │          │
    │    Claude extracts structured claims
    │    (variable, direction, methodology, geography, effect_size)
    │
    ├── FRED · World Bank · BLS  (7–9 empirical series)
    │
    ▼
Testability filter  ─── untestable claims → Literature Inventory
    │
    ▼
Statistical QQA  (Spearman r + OLS on Δ, p-value thresholds)
    │
    ▼
Forest plot + Gap matrix + 8-section research brief
```

The **testability filter** is the key architectural decision. Most economics claims are country-specific or sub-national — a study of New Jersey fast food workers, or a Hungarian natural experiment — and national aggregate data cannot test them. Rather than filling a report with meaningless "insufficient data" rows, Synthesis pre-screens each claim and routes untestable ones to a Literature Inventory section, reserving the statistical engine for claims it can actually evaluate.

---

## Quick Start

```bash
pip install synthesis-econ
```

Set your API keys (all free):

```bash
export ANTHROPIC_API_KEY='sk-ant-...'   # console.anthropic.com
export FRED_API_KEY='your-fred-key'     # fred.stlouisfed.org/docs/api/api_key.html
export BLS_API_KEY='your-bls-key'       # data.bls.gov/registrationEngine (optional)
```

Run:

```bash
synthesis "Does raising the minimum wage increase unemployment?"
synthesis "Does immigration lower wages for native workers?"
synthesis "What is the effect of quantitative easing on inflation?"
synthesis "Do charter schools improve student outcomes?"
synthesis "Does foreign aid promote economic growth?"
```

The HTML report opens automatically in your browser.

---

## Example Output

**Question:** Does raising the minimum wage increase unemployment?

**Retrieved:** 22 papers (arXiv: 8, OpenAlex: 8, NBER: 8) · **Claims:** 11 · **Testable:** 3 · **Effect sizes:** 8  
**Data:** FRED (4) · World Bank (2) · BLS (3)  
**Pooled verdict:** MIXED −0.18

**Tested claims (statistical results):**

| Claim | Verdict | Stats |
|-------|---------|-------|
| 138 state DiD → no employment loss | **SUPPORTED** | OLS slope −384, p=0.578, n=19 — cannot distinguish from zero |
| Min wage → reduced job growth | **STRONGLY SUPPORTED** | Spearman r=−0.422, OLS slope=−5705, **p=0.036**, n=26 |
| Min wage → teen unemployment (Mincer) | **STRONGLY SUPPORTED** | Spearman r=+0.299, OLS slope=+5.04, **p=0.032**, n=19 |

**Literature inventory (8 claims):** Germany (DiD), NJ/PA fast food (Card-Krueger), Hungary, Western Europe, Spain, Bulgaria, global structural — not testable against US national data, recorded separately.

> **Bottom line:** Aggregate employment levels show null effects. Employment *growth* slows significantly (p=0.036). Teen *unemployment* rises significantly (p=0.032). These are not contradictions — they measure different margins of the same phenomenon. The genuine empirical gap is that 8/11 claims span geographies the available data cannot test.

---

## Data Sources

| Source | Coverage | Key Required |
|--------|----------|-------------|
| arXiv | Economics preprints (7 categories) | None |
| OpenAlex | 250M+ peer-reviewed works | None |
| NBER | 64K+ working papers | None |
| FRED | 800K+ US macro time-series | Free |
| World Bank | Cross-country development indicators | None |
| BLS | Demographics, industry, hours, state series | Free (optional) |

---

## Options

```
synthesis "question" [OPTIONS]

  -o, --output TEXT    Output directory  [default: ./synthesis_output]
  -p, --papers INT     Max papers to retrieve  [default: 24]
  --no-fred            Skip FRED data
  --no-worldbank       Skip World Bank data
  --no-bls             Skip BLS demographic/industry data
```

---

## Install from Source

```bash
git clone https://github.com/bsin-researcher/synthesis.git
cd synthesis
pip install -e .
```

---

## Running the Demo Locally

```bash
pip install streamlit
streamlit run streamlit_app.py
```

---

## Requirements

- Python 3.10+
- Anthropic API key (Claude Opus 4.8 with adaptive thinking)
- FRED API key (free — strongly recommended)
- BLS API key (free — optional, unlocks demographic series back to 2005)

```
anthropic>=0.109.0
requests>=2.34.0
pandas>=2.0.0
plotly>=5.20.0
scipy>=1.10.0
rich>=13.0.0
typer>=0.9.0
python-dotenv>=1.0.0
```

---

## Roadmap

- [x] arXiv + OpenAlex + NBER retrieval with deduplication
- [x] Claude-powered structured claim extraction (adaptive thinking)
- [x] FRED + World Bank + BLS empirical data
- [x] Statistical QQA — Spearman r + OLS on first differences, flat-series detection
- [x] Testability filter — pre-screens claims before running statistics
- [x] Citation-weighted meta-analytic pooling
- [x] Forest plot — effect sizes across studies
- [x] arXiv HTML full-text extraction for effect size detection
- [x] Research gap matrix
- [x] Interactive Plotly HTML report
- [x] Streamlit web demo
- [ ] State-level minimum wage data (resolves NJ/PA and sub-national claims)
- [ ] Confidence intervals on pooled score (bootstrap)
- [ ] arXiv methods note on QQA
- [ ] PDF/LaTeX export

---

## Citation

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

Pull requests welcome. Highest-value open items are in the roadmap above.

To add a data source: implement `fetch_X(question: str, client: anthropic.Anthropic) -> list[DataSeries]` in `synthesis/data/` and wire it into `synthesis/cli.py`.

---

## License

MIT
