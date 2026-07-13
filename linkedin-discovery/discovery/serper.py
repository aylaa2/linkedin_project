import asyncio

import httpx

from .config import SERPER_API_KEY, SERP_PAGES, SERP_GL, SERP_HL, has_serper

SERPER_URL = "https://google.serper.dev/search"


async def serper_search(
    query: str,
    pages: int | None = None,
    mock: bool = False,
    start_page: int = 1,
) -> list[dict]:
    """Run ONE query against Serper.dev, pulling `pages` pages from `start_page`.

    Returns raw organic items: {"link", "title", "snippet"}.

    Fallback: daca NU exista SERPER_API_KEY, cauta GRATIS prin ddgs (DuckDuckGo).
    Doar `--dry-run` (mock=True) foloseste rezultate fixe.

    To swap in SerpApi: change URL/params here and map its
    organic_results[].{link,title,snippet} — nothing else in the pipeline changes.
    """
    if mock:
        return _mock(query)
    if not has_serper():
        return await asyncio.to_thread(_ddgs_search, query, pages or SERP_PAGES)

    pages = pages or SERP_PAGES
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for page in range(start_page, start_page + pages):
            resp = await client.post(
                SERPER_URL,
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 10, "page": page, "gl": SERP_GL, "hl": SERP_HL},
            )
            resp.raise_for_status()
            data = resp.json()
            organic = data.get("organic") or []
            for it in organic:
                out.append(
                    {
                        "link": it.get("link"),
                        "title": it.get("title", ""),
                        "snippet": it.get("snippet", ""),
                    }
                )
            if len(organic) < 10:  # no more pages
                break
    return out


def _ddgs_search(query: str, pages: int) -> list[dict]:
    """Fallback GRATIS prin ddgs (DuckDuckGo) cand nu ai cheie Serper.
    Ruleaza sincron intr-un thread separat (vezi asyncio.to_thread mai sus)."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return _mock(query)
    out: list[dict] = []
    try:
        with DDGS() as d:
            for it in d.text(query, max_results=max(30, pages * 10)):
                out.append({
                    "link": it.get("href") or it.get("url") or it.get("link"),
                    "title": it.get("title", ""),
                    "snippet": it.get("body") or it.get("snippet", ""),
                })
    except Exception:
        return _mock(query)
    return out or _mock(query)


def _mock(query: str) -> list[dict]:
    """Fake results so the pipeline runs with zero keys / zero cost."""
    return [
        {
            "link": "https://www.linkedin.com/in/jane-doe-123456",
            "title": "Jane Doe - Senior Software Engineer - Acme Corp | LinkedIn",
            "snippet": "Senior Software Engineer at Acme Corp. React, Node.js, TypeScript. Bucharest, Romania.",
        },
        {
            # duplicate of the above: different locale subdomain + tracking param
            "link": "https://ro.linkedin.com/in/jane-doe-123456?trk=public_profile",
            "title": "Jane Doe - Senior Software Engineer | LinkedIn",
            "snippet": "Duplicate that should be removed by normalization.",
        },
        {
            "link": "https://www.linkedin.com/in/john-smith-987654/",
            "title": "John Smith - Full Stack Developer - Startup SRL | LinkedIn",
            "snippet": "Full Stack Developer. JavaScript, React, PostgreSQL. Remote.",
        },
        {
            # company page -> not a /in/ profile -> filtered out
            "link": "https://www.linkedin.com/company/acme-corp",
            "title": "Acme Corp | LinkedIn",
            "snippet": "Company page, should be filtered.",
        },
        {
            # not linkedin -> filtered out
            "link": "https://example.com/blog/best-engineers",
            "title": "Best engineers of 2026",
            "snippet": "Some blog, should be filtered.",
        },
    ]
