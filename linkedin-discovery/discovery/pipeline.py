from .query_agent import generate_queries
from .serper import serper_search
from .normalize import dedupe_to_hits
from .models import DiscoveryResult


async def discover(jd: str, mock: bool = False, max_hits: int = 50) -> DiscoveryResult:
    """Serper — discovery box.

        JD text
          -> LLM #1 (generate_queries)        : boolean Google queries
          -> Serper (one call per query)      : raw organic results
          -> normalize (filter /in/ + dedup)  : DiscoveryHit list

    The returned DiscoveryResult.hits feed the `Normalize + validate` box.
    Call this from a FastAPI worker; it's fully async.
    """
    if not jd or not jd.strip():
        raise ValueError("Empty job description.")

    # 1) LLM #1: JD -> queries
    signals = await generate_queries(jd)
    queries = signals.boolean_queries
    if not queries:
        raise RuntimeError("LLM produced no queries.")

    # 2) Serper: run each query (sequential = friendlier to rate limits)
    raw_all: list[dict] = []
    for q in queries:
        try:
            items = await serper_search(q, mock=mock)
            for it in items:
                it["found_by_query"] = q
            raw_all.extend(items)
        except Exception as err:  # noqa: BLE001 - keep going on a single bad query
            import sys
            print(f"[serper] query failed, skipping: {q}\n  {err}", file=sys.stderr)

    # 3) Normalize: filter to /in/ + dedup across all queries
    hits = dedupe_to_hits(raw_all)[:max_hits]

    return DiscoveryResult(
        signals=signals,
        hits=hits,
        stats={"queries": len(queries), "raw": len(raw_all), "hits": len(hits)},
    )


async def discover_urls(jd: str, mock: bool = False, max_hits: int = 50) -> list[str]:
    """Same pipeline, but returns ONLY the profile URLs (list of strings).

    This is what the scraper stage consumes: a plain list of links, nothing else.
    """
    result = await discover(jd, mock=mock, max_hits=max_hits)
    return [hit.profile_url for hit in result.hits]