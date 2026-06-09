import json
import requests
import pandas as pd
from synthesis.data.fred import DataSeries


WB_BASE = "https://api.worldbank.org/v2"

COMMON_INDICATORS = {
    "unemployment": "SL.UEM.TOTL.ZS",
    "gdp per capita": "NY.GDP.PCAP.CD",
    "gdp growth": "NY.GDP.MKTP.KD.ZG",
    "inflation": "FP.CPI.TOTL.ZG",
    "poverty": "SI.POV.DDAY",
    "gini": "SI.POV.GINI",
    "fdi": "BX.KLT.DINV.WD.GD.ZS",
    "trade": "NE.TRD.GNFS.ZS",
    "labor participation": "SL.TLF.CACT.ZS",
    "minimum wage": "SL.WAG.0714.MA.ZS",
    "income share": "SI.DST.10TH.10",
    "education": "SE.XPD.TOTL.GD.ZS",
    "health spending": "SH.XPD.CHEX.GD.ZS",
}


def _identify_indicators_with_claude(question: str, client, max_indicators: int = 3) -> list[str]:
    prompt = f"""You are an expert in World Bank development data indicators.

Given this economics research question: "{question}"

List the {max_indicators} most relevant World Bank indicator codes that provide cross-country empirical data to test it.

Common indicators:
- SL.UEM.TOTL.ZS: Unemployment, total (% of labor force)
- NY.GDP.PCAP.CD: GDP per capita (current US$)
- NY.GDP.MKTP.KD.ZG: GDP growth (annual %)
- FP.CPI.TOTL.ZG: Inflation, consumer prices (annual %)
- SI.POV.DDAY: Poverty headcount ratio at $2.15/day (%)
- SI.POV.GINI: GINI index
- BX.KLT.DINV.WD.GD.ZS: Foreign direct investment (% of GDP)
- SL.TLF.CACT.ZS: Labor force participation rate (%)
- SE.XPD.TOTL.GD.ZS: Government expenditure on education (% of GDP)
- SH.DYN.MORT: Mortality rate, under-5
- EG.USE.PCAP.KG.OE: Energy use per capita
- IT.NET.USER.ZS: Internet users (% of population)

Return ONLY a JSON array of indicator code strings, e.g. ["SL.UEM.TOTL.ZS", "NY.GDP.PCAP.CD"]
No explanation, just the JSON array."""

    try:
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())[:max_indicators]
    except Exception:
        return ["SL.UEM.TOTL.ZS", "NY.GDP.PCAP.CD"]


def fetch_worldbank(question: str, client, max_indicators: int = 2) -> list[DataSeries]:
    indicators = _identify_indicators_with_claude(question, client, max_indicators)
    results = []
    for indicator in indicators:
        try:
            series = _fetch_indicator(indicator)
            if series:
                results.append(series)
        except Exception:
            pass
    return results


def _fetch_indicator(indicator: str, years: int = 20) -> DataSeries | None:
    url = f"{WB_BASE}/country/all/indicator/{indicator}"
    params = {
        "format": "json",
        "mrv": years,
        "per_page": 5000,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if len(data) < 2 or not data[1]:
        return None

    # Filter for world aggregate or high-income group
    rows = []
    for entry in data[1]:
        country_id = entry.get("countryiso3code", "")
        value = entry.get("value")
        year = entry.get("date", "")
        if country_id == "WLD" and value is not None:
            rows.append({"date": pd.to_datetime(f"{year}-01-01"), "value": float(value)})

    if not rows:
        return None

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    title = data[1][0].get("indicator", {}).get("value", indicator) if data[1] else indicator

    return DataSeries(
        series_id=f"WB:{indicator}",
        title=f"{title} (World Bank, Global)",
        units="%",
        frequency="Annual",
        data=df,
    )
