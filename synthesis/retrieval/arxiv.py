import re
import time
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


ARXIV_API = "https://export.arxiv.org/api/query"


@dataclass
class Paper:
    title: str
    authors: list[str]
    abstract: str
    url: str
    published: str
    source: str = "arxiv"
    citations: int = 0
    full_text: str = ""  # populated by fetch_full_texts() after retrieval


def _arxiv_id(url: str) -> str | None:
    """Extract arXiv ID from https://arxiv.org/abs/XXXX.XXXXX"""
    m = re.search(r"arxiv\.org/abs/([\d.v]+)", url)
    return m.group(1) if m else None


def _fetch_html_text(arxiv_id: str, max_chars: int = 6000) -> str:
    """
    Fetch the arXiv HTML paper version and extract results-section text.
    Returns empty string if HTML version doesn't exist or fetch fails.
    """
    try:
        resp = requests.get(
            f"https://arxiv.org/html/{arxiv_id}",
            timeout=12,
            headers={"User-Agent": "Synthesis-Economics-Research/0.4.0"},
        )
        if resp.status_code != 200:
            return ""
        text = resp.text
        # Strip scripts, styles, nav
        text = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Try to start from the results/findings/empirical section
        lower = text.lower()
        for marker in ("results", "findings", "empirical evidence", "estimates", "conclusion"):
            pos = lower.find(marker)
            if pos > len(text) // 4:  # not in the very beginning (intro/abstract)
                return text[pos: pos + max_chars]
        # Fallback: middle third of document (usually methods + results)
        mid = len(text) // 3
        return text[mid: mid + max_chars]
    except Exception:
        return ""


def fetch_full_texts(papers: list["Paper"]) -> None:
    """
    Populate paper.full_text for arXiv papers that have an HTML version.
    Mutates in place. Skips non-arXiv papers and failed fetches silently.
    """
    for paper in papers:
        if paper.source != "arxiv" or paper.full_text:
            continue
        arxiv_id = _arxiv_id(paper.url)
        if not arxiv_id:
            continue
        paper.full_text = _fetch_html_text(arxiv_id)
        time.sleep(0.3)  # polite rate-limit


def _keywords(query: str) -> str:
    """Strip question words so arXiv gets clean keyword search terms."""
    import re
    stopwords = {"does", "do", "is", "are", "the", "a", "an", "in", "of",
                 "to", "and", "or", "for", "on", "how", "what", "why",
                 "when", "which", "by", "with", "from", "that", "this"}
    words = re.sub(r"[?!.,;:'\"]", "", query.lower()).split()
    keywords = [w for w in words if w not in stopwords and len(w) > 2]
    return "+".join(keywords)


def search_arxiv(query: str, max_results: int = 15) -> list[Paper]:
    # Build URL manually so +OR+/+AND+ operators are not double-encoded
    econ_cats = "cat:econ.GN+OR+cat:econ.EM+OR+cat:econ.LG+OR+cat:econ.TH+OR+cat:econ.HE+OR+cat:econ.IO+OR+cat:q-fin.EC"
    # Use keyword extraction so arXiv gets clean terms, not a full question sentence
    keywords = _keywords(query)
    search_query = f"({keywords})+AND+({econ_cats})"
    url = (
        f"{ARXIV_API}?search_query={search_query}"
        f"&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    papers = []

    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        abstract = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
        url = entry.findtext("atom:id", "", ns).strip()
        published = entry.findtext("atom:published", "", ns)[:10]
        authors = [
            a.findtext("atom:name", "", ns)
            for a in entry.findall("atom:author", ns)
        ]
        if title and abstract:
            papers.append(Paper(title=title, authors=authors, abstract=abstract,
                                url=url, published=published))

    time.sleep(0.5)
    return papers
