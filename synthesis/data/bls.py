"""
BLS (Bureau of Labor Statistics) data fetcher.

Provides demographic, industry, hours, and state-level series that FRED national
aggregates cannot supply — the exact gaps that make QQA return INSUFFICIENT_DATA
for claims about teens, food service workers, weekly hours, and state comparisons.

BLS API v2: free, no key required (25 queries/day, 10 years of data).
Optional BLS_API_KEY env var unlocks 500 queries/day and 20 years.
"""

import os
import json
import requests
import pandas as pd
import anthropic
from synthesis.data.fred import DataSeries


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Curated catalog: series IDs confirmed working, covering the gaps most relevant
# to labor economics research (MW, inequality, employment, hours, wages).
BLS_CATALOG = {
    # ── Unemployment by demographic group ──────────────────────────────────────
    "LNS14000012": "Unemployment Rate, Teens 16-19 yrs (%)",
    "LNS14000024": "Unemployment Rate, Age 20-24 yrs (%)",
    "LNS14032183": "Unemployment Rate, Less than HS Diploma (%)",
    "LNS14027659": "Unemployment Rate, HS Graduates, No College (%)",
    "LNS14000006": "Unemployment Rate, Black or African American (%)",
    "LNS14000003": "Unemployment Rate, White (%)",

    # ── Employment-population ratio (cleaner than unemployment for MW research)
    "LNS12000012": "Employment-Population Ratio, Teens 16-19 (%)",
    "LNS12000000": "Employment-Population Ratio, All 16+ (%)",

    # ── Industry employment (thousands of persons) ──────────────────────────────
    "CES7072200001": "Food Services & Drinking Places Employment (thousands)",
    "CES4200000001": "Retail Trade Employment (thousands)",
    "CES7000000001": "Leisure & Hospitality Employment (thousands)",
    "CES0600000001": "Goods-Producing Employment (thousands)",
    "CES6500000001": "Health Care & Social Assistance Employment (thousands)",

    # ── Hours and wages (key for 'adjustment through hours' and pass-through) ──
    "CES0500000007": "Average Weekly Hours, Private Sector",
    "CES0500000008": "Average Hourly Earnings, Private Sector ($/hr)",
    "CES7072200007": "Average Weekly Hours, Food Services",
    "CES7072200008": "Average Hourly Earnings, Food Services ($/hr)",
    "CES4200000007": "Average Weekly Hours, Retail Trade",
    "CES4200000008": "Average Hourly Earnings, Retail Trade ($/hr)",

    # ── State unemployment (NJ/PA for Card-Krueger; high-MW states for DiD) ───
    "LAUST340000000000003": "New Jersey Unemployment Rate (%)",
    "LAUST420000000000003": "Pennsylvania Unemployment Rate (%)",
    "LAUST060000000000003": "California Unemployment Rate (%)",
    "LAUST480000000000003": "Texas Unemployment Rate (%)",
    "LAUST530000000000003": "Washington State Unemployment Rate (%)",
    "LAUST360000000000003": "New York Unemployment Rate (%)",
}

_UNITS_MAP = {
    "(%)": "percent",
    "($/hr)": "$/hour",
    "(thousands)": "thousands of persons",
}


def fetch_bls(
    question: str,
    client: anthropic.Anthropic,
    max_series: int = 3,
) -> list[DataSeries]:
    selected = _select_series(question, client, max_series)
    if not selected:
        return []
    return _fetch_series(selected)


def _select_series(
    question: str,
    client: anthropic.Anthropic,
    max_series: int,
) -> list[str]:
    catalog_text = "\n".join(
        f"  {sid}: {desc}" for sid, desc in BLS_CATALOG.items()
    )
    prompt = f"""Select the {max_series} BLS series most useful for testing claims about this question.

QUESTION: {question}

SERIES CATALOG:
{catalog_text}

Prioritize series that test the specific mechanisms the question is about:
- Minimum wage / disemployment → teen unemployment, food service employment, weekly hours
- Wages / inequality → earnings series, education-group unemployment
- Hours adjustment → weekly hours series
- Regional effects → state unemployment pairs (e.g. NJ + PA for Card-Krueger)

Return ONLY a JSON array of series ID strings."""

    try:
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        ids = json.loads(raw.strip())
        return [s for s in ids if s in BLS_CATALOG][:max_series]
    except Exception:
        return []


def _fetch_series(series_ids: list[str]) -> list[DataSeries]:
    api_key = os.environ.get("BLS_API_KEY", "")
    # Without a key, BLS returns max 10 years from startyear.
    # Anchor to recent data (2015-2025) so we get current series, not 2000-2009.
    # With a key, go back further for more context.
    startyear = "2005" if api_key else "2015"
    payload: dict = {
        "seriesid": series_ids,
        "startyear": startyear,
        "endyear": "2025",
    }
    if api_key:
        payload["registrationkey"] = api_key

    try:
        resp = requests.post(BLS_API_URL, json=payload, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    if data.get("status") != "REQUEST_SUCCEEDED":
        return []

    results = []
    for series in data.get("Results", {}).get("series", []):
        sid = series.get("seriesID", "")
        raw_data = series.get("data", [])
        if not raw_data:
            continue

        rows = []
        for point in raw_data:
            period = point.get("period", "")
            if period == "M13" or not period.startswith("M"):
                continue
            footnotes = point.get("footnotes", [])
            # Skip suppressed/unreliable values (BLS footnote code "C")
            if any(f.get("code") == "C" for f in footnotes if f):
                continue
            try:
                month = int(period[1:])
                year = int(point["year"])
                val = float(point["value"])
            except (ValueError, KeyError):
                continue
            rows.append({
                "date": pd.Timestamp(year=year, month=month, day=1),
                "value": val,
            })

        if not rows:
            continue

        df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        desc = BLS_CATALOG.get(sid, sid)

        # Infer units from description suffix
        units = "index"
        for suffix, unit_label in _UNITS_MAP.items():
            if suffix in desc:
                units = unit_label
                break

        results.append(DataSeries(
            series_id=f"BLS:{sid}",
            title=desc,
            units=units,
            frequency="Monthly",
            data=df,
        ))

    return results
