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
git clone https://github.com/blakesinclair/synthesis.git
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

**Papers:** 24 (arXiv: 8, OpenAlex: 8, NBER: 8)  
**Claims extracted:** 10  
**FRED series:** Federal Minimum Wage, Unemployment Rate, Nonfarm Payrolls, Labor Force Participation  
**World Bank series:** Unemployment, total (% of labor force)

> **Consensus:** No detectable disemployment effect from realistic minimum wage increases — a 138-change US DiD study and the 2022 German 22% hike both find employment essentially unchanged. Adjustment occurs on the *hours* margin, not headcount.
>
> **Key tension:** Structural search-friction models predict disemployment by construction; DiD studies find none. The reconciliation is a monopsony nonlinearity — disemployment appears only in competitive markets (German IV result), vanishes under labor-market concentration.
>
> **Top gap:** A US IV study interacting minimum wage changes with local labor-market concentration (HHI) — the German monopsony result has never been replicated on US data.

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

- [x] arXiv + OpenAlex + NBER retrieval
- [x] Claude-powered structured claim extraction (adaptive thinking)
- [x] FRED + World Bank empirical data (series chosen by Claude)
- [x] QQA alignment scoring
- [x] Research gap matrix
- [x] Interactive Plotly HTML report
- [ ] Semantic deduplication across sources (sentence-transformers)
- [ ] Numerical effect size extraction and meta-analytic pooling
- [ ] Formal QQA with confidence intervals
- [ ] Citation importance weighting (h-index, citation count)
- [ ] PDF and LaTeX export
- [ ] Benchmark vs Elicit, Consensus, Semantic Scholar

---

## Citation

If you use Synthesis in your research:

```bibtex
@software{sinclair2026synthesis,
  author  = {Sinclair, Blake},
  title   = {Synthesis: AI-Powered Economics Research via Quantitative-Qualitative Alignment},
  year    = {2026},
  url     = {https://github.com/blakesinclair/synthesis},
}
```

---

## Contributing

Pull requests welcome. The highest-value open items are in the roadmap above.

To add a new data source, implement the pattern in `synthesis/data/` — a function `fetch_X(question: str, client: anthropic.Anthropic) -> list[DataSeries]` and wire it into `synthesis/cli.py`.

---

## License

MIT
