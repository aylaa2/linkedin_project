from urllib.parse import urlparse

from .models import DiscoveryHit


def is_profile_url(url: str) -> bool:
    try:
        u = urlparse(url)
    except Exception:
        return False
    host = (u.netloc or "").lower().split(":")[0]
    on_linkedin = host == "linkedin.com" or host.endswith(".linkedin.com")
    parts = [p for p in u.path.split("/") if p]
    return on_linkedin and len(parts) >= 2 and parts[0].lower() == "in"


def canonical_key(url: str) -> str:
    u = urlparse(url)
    parts = [p for p in u.path.split("/") if p]
    slug = parts[1] if len(parts) > 1 else ""
    return f"linkedin.com/in/{slug.lower()}"


def dedupe_to_hits(raw_items: list[dict]) -> list[DiscoveryHit]:
    by_key: dict[str, DiscoveryHit] = {}
    for it in raw_items:
        link = it.get("link")
        if not link or not is_profile_url(link):
            continue
        key = canonical_key(link)
        title = it.get("title", "") or ""
        prev = by_key.get(key)
        # keep the richer title if we see the same person twice
        if prev and len(prev.title) >= len(title):
            continue
        by_key[key] = DiscoveryHit(
            profile_url=f"https://www.{key}",
            canonical_key=key,
            title=title,
            snippet=it.get("snippet", "") or "",
            source="serper",
            found_by_query=it.get("found_by_query", ""),
        )
    return list(by_key.values())
