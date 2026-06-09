import os
import json
import requests
import pandas as pd
from dataclasses import dataclass, field


FRED_BASE = "https://api.stlouisfed.org/fred"


@dataclass
class DataSeries:
    series_id: str
    title: str
    units: str
    frequency: str
    data: pd.DataFrame = field(default_factory=pd.DataFrame)

    def summary(self) -> dict:
        if self.data.empty:
            return {}
        vals = self.data["value"].dropna()
        return {
            "series_id": self.series_id,
            "title": self.title,
            "units": self.units,
            "start": str(self.data["date"].iloc[0]),
            "end": str(self.data["date"].iloc[-1]),
            "latest_value": round(float(vals.iloc[-1]), 3) if len(vals) else None,
            "min": round(float(vals.min()), 3),
            "max": round(float(vals.max()), 3),
            "mean": round(float(vals.mean()), 3),
            "observations": len(vals),
        }


class FredClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "FRED API key required. Get one free at "
                "https://fred.stlouisfed.org/docs/api/api_key.html\n"
                "Then: export FRED_API_KEY='your-key'"
            )

    def _get(self, endpoint: str, params: dict) -> dict:
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        resp = requests.get(f"{FRED_BASE}/{endpoint}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def fetch_series(self, series_id: str, observation_start: str = "2000-01-01") -> DataSeries:
        meta = self._get("series", {"series_id": series_id})
        s = meta["seriess"][0]
        obs = self._get("series/observations", {
            "series_id": series_id,
            "observation_start": observation_start,
            "sort_order": "asc",
        })
        rows = [
            {"date": pd.to_datetime(o["date"]),
             "value": float(o["value"]) if o["value"] != "." else None}
            for o in obs.get("observations", [])
        ]
        df = pd.DataFrame(rows)
        return DataSeries(
            series_id=series_id,
            title=s.get("title", series_id),
            units=s.get("units_short", ""),
            frequency=s.get("frequency_short", ""),
            data=df,
        )

    def fetch_relevant(self, question: str, client, max_series: int = 4) -> list[DataSeries]:
        """Use Claude to identify the most relevant FRED series IDs for the question."""
        series_ids = self._identify_series_with_claude(question, client, max_series)
        result = []
        for sid in series_ids:
            try:
                result.append(self.fetch_series(sid))
            except Exception:
                pass
        return result

    def _identify_series_with_claude(self, question: str, client, max_series: int) -> list[str]:
        prompt = f"""You are an expert in FRED (Federal Reserve Economic Data) series.

Given this economics research question: "{question}"

List the {max_series} most relevant FRED series IDs that would provide empirical data to test it.
Focus on: outcome variables (what the question is asking about), key treatment/explanatory variables, and important controls.

Common useful series:
- UNRATE: Unemployment Rate
- LNS14000000: Unemployment Rate (seasonally adjusted)
- PAYEMS: Total Nonfarm Payrolls
- CIVPART: Labor Force Participation Rate
- LES1252881600Q: Median Usual Weekly Earnings
- STTMINWGFG: Federal Minimum Wage
- GDPC1: Real GDP
- CPIAUCSL: Consumer Price Index
- FEDFUNDS: Federal Funds Rate
- DGS10: 10-Year Treasury Rate
- GFDEBTN: Federal Debt
- DPCERA3Q086SBEA: Real Personal Consumption Expenditures
- HOUST: Housing Starts
- MEHOINUSA672N: Median Household Income
- GINIALLRH: GINI Coefficient
- MSPUS: Median Sales Price of Houses
- UMCSENT: Consumer Sentiment
- INDPRO: Industrial Production Index
- DEXUSEU: US/Euro Exchange Rate
- BOGMBASE: Monetary Base

Return ONLY a JSON array of series ID strings, e.g. ["UNRATE", "STTMINWGFG", "PAYEMS"]
No explanation, just the JSON array."""

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
            return json.loads(raw.strip())[:max_series]
        except Exception:
            # Fallback to sensible defaults
            return ["UNRATE", "PAYEMS", "CIVPART", "GDPC1"]
