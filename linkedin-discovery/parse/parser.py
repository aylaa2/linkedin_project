import re

from bs4 import BeautifulSoup, Comment

_DROP = [
    "script", "style", "head", "noscript", "template", "svg", "iframe",
    "code", "nav", "footer", "aside", "form", "button",
]


def clean_html(html: str) -> str:
    """One profile page's raw HTML -> clean, minimal text for LLM extraction.

    Strips markup, scripts/styles, hidden JSON blocks and obvious chrome, then
    collapses whitespace. Never raises on messy input — empty/garbage in gives
    "" out. Does NOT extract fields (name/skills) — that's the downstream LLM.
    """
    if not html or not html.strip():
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(_DROP):
        tag.decompose()

    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    text = soup.get_text(separator="\n")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return re.sub(r"[ \t]{2,}", " ", "\n".join(lines))
