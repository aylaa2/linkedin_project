import re

from bs4 import BeautifulSoup, Comment

_NOISE_BLOCK_RE = re.compile(
    r"<(script|style|code|template|svg|noscript)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)

_DROP_CHROME = ["head", "nav", "footer", "aside", "form", "button", "iframe"]


def clean_html(html: str) -> str:
    """One profile page's raw HTML -> clean, minimal text for LLM extraction.

    Strips markup, scripts/styles, hidden JSON blocks and obvious chrome, then
    collapses whitespace. Never raises on messy input — empty/garbage in gives
    "" out. Does NOT extract fields (name/skills) — that's the downstream LLM.
    """
    if not html or not html.strip():
        return ""

    html = _NOISE_BLOCK_RE.sub(" ", html)

    soup = BeautifulSoup(html, "html5lib")

    for tag in soup(_DROP_CHROME):
        tag.decompose()

    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    text = soup.get_text(separator="\n")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return re.sub(r"[ \t]{2,}", " ", "\n".join(lines))
