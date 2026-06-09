import re
import time
import requests
from .arxiv import Paper


OPENALEX_API = "https://api.openalex.org/works"
NBER_INSTITUTION_ID = "I1321305853"  # OpenAlex institution ID for NBER (64K+ papers)


def search_nber(query: str, max_results: int = 8) -> list[Paper]:
    """Search NBER working papers via OpenAlex institution filter."""
    clean_query = re.sub(r"[?!.,;:'\"]", "", query).strip()
    params = {
        "search": clean_query,
        "filter": f"institutions.id:{NBER_INSTITUTION_ID},has_abstract:true",
        "sort": "relevance_score:desc",
        "per-page": max_results,
        "select": "title,authorships,abstract_inverted_index,doi,publication_year",
        "mailto": "research@synthesis-econ.io",
    }
    try:
        resp = requests.get(OPENALEX_API, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []

    papers = []
    for r in results:
        title = r.get("title") or ""
        abstract = _reconstruct(r.get("abstract_inverted_index") or {})
        doi = r.get("doi") or ""
        year = str(r.get("publication_year") or "")
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in (r.get("authorships") or [])[:3]
        ]
        if title and abstract:
            papers.append(Paper(title=title, authors=authors, abstract=abstract,
                                url=doi, published=year, source="nber"))

    time.sleep(0.3)
    return papers


def _reconstruct(inverted_index: dict) -> str:
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))
