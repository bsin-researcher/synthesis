import re
from synthesis.retrieval.arxiv import Paper


def deduplicate(papers: list[Paper]) -> list[Paper]:
    """
    Remove duplicate papers by DOI (exact) then normalized title (fuzzy).
    Keeps the first occurrence — arXiv first since those have full abstracts.
    """
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    result: list[Paper] = []

    for p in papers:
        doi_key = _extract_doi(p.url)
        title_key = _normalize_title(p.title)

        if doi_key and doi_key in seen_dois:
            continue
        if title_key and title_key in seen_titles:
            continue

        if doi_key:
            seen_dois.add(doi_key)
        if title_key:
            seen_titles.add(title_key)
        result.append(p)

    return result


def _extract_doi(url: str) -> str:
    if not url:
        return ""
    url = url.strip().lower()
    if "doi.org/" in url:
        return url.split("doi.org/")[-1].rstrip("/")
    if url.startswith("10."):
        return url.rstrip("/")
    return ""


def _normalize_title(title: str) -> str:
    # Keep only alphanumeric, lowercase, first 80 chars — enough to catch near-duplicates
    return re.sub(r"[^a-z0-9]", "", title.lower())[:80]
