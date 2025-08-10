import re
import math
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup
from readability import Document


def fetch_html(url: str, timeout_sec: int = 20) -> str:
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout_sec,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        },
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def extract_readable_fields(html: str, url: str) -> Dict[str, Optional[str]]:
    doc = Document(html)
    title = doc.short_title()
    summary_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(summary_html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)

    soup_full = BeautifulSoup(html, "lxml")
    site_name = None
    meta_site = soup_full.find("meta", attrs={"property": "og:site_name"})
    if meta_site and meta_site.get("content"):
        site_name = meta_site["content"].strip()
    byline = None
    author_meta = soup_full.find("meta", attrs={"name": "author"}) or soup_full.find("meta", attrs={"property": "article:author"})
    if author_meta and author_meta.get("content"):
        byline = author_meta["content"].strip()

    return {
        "title": title.strip() if title else None,
        "byline": byline,
        "site_name": site_name,
        "content": text or None,
    }


def estimate_reading_minutes(word_count: int) -> int:
    return max(1, math.ceil(word_count / 200))


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def tags_to_str(tags: Optional[list[str]]) -> Optional[str]:
    if not tags:
        return None
    return ",".join([t.strip() for t in tags if t and t.strip()]) or None


