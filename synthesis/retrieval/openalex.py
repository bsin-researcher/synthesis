import time
import requests
from .arxiv import Paper


OPENALEX_API = "https://api.openalex.org/works"


def search_openalex(query: str, max_results: int = 10) -> list[Paper]:
    import re
    clean_query = re.sub(r"[?!.,;:'\"]", "", query).strip()
    params = {
        "search": clean_query,
        "filter": "has_abstract:true,type:article",
        "sort": "relevance_score:desc",
        "per-page": max_results,
        "select": "title,authorships,abstract_inverted_index,doi,publication_year,topics",
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
        abstract = _reconstruct_abstract(r.get("abstract_inverted_index") or {})
        doi = r.get("doi") or ""
        year = str(r.get("publication_year") or "")
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in (r.get("authorships") or [])[:3]
        ]
        if title and abstract:
            papers.append(Paper(title=title, authors=authors, abstract=abstract,
                                url=doi, published=year, source="openalex"))

    time.sleep(0.3)
    return papers


def _reconstruct_abstract(inverted_index: dict) -> str:
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))
