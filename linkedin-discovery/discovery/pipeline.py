import math
import sys

from .query_agent import generate_queries
from .serper import serper_search
from .normalize import dedupe_to_hits
from .models import DiscoveryResult

_MAX_PAGES = 5  # per query; Google rarely returns anything useful deeper


async def discover(
    jd: str,
    location: str = "",
    mock: bool = False,
    max_hits: int = 50,
) -> DiscoveryResult:
    """Serper — discovery box.

        JD text + location (single, optional)
          -> LLM #1 (generate_queries)        : boolean Google queries
          -> Serper (equal share per query)   : raw organic results
          -> normalize (filter /in/ + dedup)  : DiscoveryHit list
          -> top-up (round-robin)             : refill what dedup removed
    """
    if not jd or not jd.strip():
        raise ValueError("Empty job description.")

    # 1-LLM #1: JD + location -> queries
    signals = await generate_queries(jd, location)
    queries = signals.boolean_queries
    if not queries:
        raise RuntimeError("LLM produced no queries.")

    # 2-Serper
    per_query = math.ceil(max_hits / len(queries))
    pages = min(_MAX_PAGES, math.ceil(per_query / 10))
    leftovers: dict[str, list[dict]] = {}
    pages_used: dict[str, int] = {}
    raw_all: list[dict] = []
    for q in queries:
        items = await _fetch(q, pages=pages, start_page=1, mock=mock)
        raw_all.extend(items[:per_query])
        leftovers[q] = items[per_query:]
        pages_used[q] = pages
    hits = dedupe_to_hits(raw_all)

    # 3-Top-up: cross-query duplicates shrink the pool below max_hits
    exhausted: set[str] = set()
    while len(hits) < max_hits and len(exhausted) < len(queries):
        for q in queries:
            if len(hits) >= max_hits:
                break
            if q in exhausted:
                continue
            if not leftovers[q]:
                if mock or pages_used[q] >= _MAX_PAGES:
                    exhausted.add(q)
                    continue
                pages_used[q] += 1
                leftovers[q] = await _fetch(
                    q, pages=1, start_page=pages_used[q], mock=mock
                )
                if not leftovers[q]:
                    exhausted.add(q)
                    continue
            raw_all.append(leftovers[q].pop(0))
            hits = dedupe_to_hits(raw_all)

    return DiscoveryResult(
        signals=signals,
        hits=hits[:max_hits],
        stats={
            "queries": len(queries),
            "per_query": per_query,
            "serp_pages": sum(pages_used.values()),
            "raw": len(raw_all),
            "hits": min(len(hits), max_hits),
        },
    )


async def _fetch(q: str, pages: int, start_page: int, mock: bool) -> list[dict]:
    """One Serper call; tags items, never raises (bad query -> no results)."""
    try:
        items = await serper_search(q, pages=pages, start_page=start_page, mock=mock)
    except Exception as err:  # noqa: BLE001 - keep going on a single bad query
        print(f"[serper] query failed, skipping: {q}\n  {err}", file=sys.stderr)
        return []
    for it in items:
        it["found_by_query"] = q
    return items


async def discover_urls(
    jd: str,
    location: str = "",
    mock: bool = False,
    max_hits: int = 50,
) -> list[str]:
    """Same pipeline, but returns ONLY the profile URLs (list of strings).

    This is what the API returns and what the scraper stage consumes.
    """
    result = await discover(jd, location, mock=mock, max_hits=max_hits)
    return [hit.profile_url for hit in result.hits]
