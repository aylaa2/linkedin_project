import httpx

from .config import SERPER_API_KEY, SERP_PAGES, SERP_GL, SERP_HL, has_serper

SERPER_URL = "https://google.serper.dev/search"


async def serper_search(query: str, pages: int | None = None, mock: bool = False) -> list[dict]:
    """Run ONE query against Serper.dev, pulling `pages` pages.

    Returns raw organic items: {"link", "title", "snippet"}.

    To swap in SerpApi: change URL/params here and map its
    organic_results[].{link,title,snippet} — nothing else in the pipeline changes.
    """
    if mock or not has_serper():
        return _mock(query)

    pages = pages or SERP_PAGES
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for page in range(1, pages + 1):
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
