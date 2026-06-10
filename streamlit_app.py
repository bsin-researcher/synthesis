import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(
    page_title="Synthesis — AI Economics Research",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

REPORTS_DIR = Path(__file__).parent / "demo_reports"

QUESTIONS = {
    "Does raising the minimum wage increase unemployment?": "does_raising_the_minimum_wage_increase_unemploymen.html",
    "Does immigration lower wages for native workers?":    "does_immigration_lower_wages_for_native_workers_.html",
    "Does quantitative easing increase inflation?":        "does_quantitative_easing_increase_inflation_.html",
    "Does income inequality reduce economic growth?":      "does_income_inequality_reduce_economic_growth_.html",
    "Does foreign aid promote economic growth?":           "does_foreign_aid_promote_economic_growth_.html",
    "Do charter schools improve student outcomes?":        "do_charter_schools_improve_student_outcomes_.html",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.markdown("## Synthesis")
st.sidebar.markdown(
    "AI-powered economics research — literature claims tested against real data.\n\n"
    "Select a question to view the full research brief."
)
st.sidebar.markdown("---")
st.sidebar.markdown("### Questions")

selected = st.sidebar.radio(
    label="",
    options=list(QUESTIONS.keys()),
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Run your own question:**\n"
    "```\npip install synthesis-econ\n"
    "synthesis \"your question here\"\n```\n\n"
    "Requires an [Anthropic API key](https://console.anthropic.com) "
    "and a free [FRED key](https://fred.stlouisfed.org/docs/api/api_key.html).\n\n"
    "[![GitHub](https://img.shields.io/badge/GitHub-bsin--researcher%2Fsynthesis-blue?logo=github)](https://github.com/bsin-researcher/synthesis) "
    "[![PyPI](https://img.shields.io/pypi/v/synthesis-econ)](https://pypi.org/project/synthesis-econ/)"
)

# ── Main area ─────────────────────────────────────────────────────────────────

report_path = REPORTS_DIR / QUESTIONS[selected]

if report_path.exists():
    html_content = report_path.read_text(encoding="utf-8")
    components.html(html_content, height=5800, scrolling=True)
else:
    st.error(f"Report file not found: {QUESTIONS[selected]}")
    st.info("Re-run the report locally: `synthesis \"" + selected + "\"`")
