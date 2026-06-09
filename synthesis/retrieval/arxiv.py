import time
import urllib.parse
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass


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


def search_arxiv(query: str, max_results: int = 15) -> list[Paper]:
    # Build URL manually so +OR+/+AND+ operators are not double-encoded
    econ_cats = "cat:econ.GN+OR+cat:econ.EM+OR+cat:econ.LG+OR+cat:econ.TH+OR+cat:econ.HE+OR+cat:econ.IO+OR+cat:q-fin.EC"
    encoded_query = urllib.parse.quote(query)
    search_query = f"({encoded_query})+AND+({econ_cats})"
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
