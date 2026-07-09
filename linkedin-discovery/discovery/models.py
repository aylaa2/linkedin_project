from typing import Optional
from pydantic import BaseModel, Field


class QuerySignals(BaseModel):
    """Structured signals LLM #1 extracts from the JD, plus ready Google queries.

    Keeping the signals separate from `boolean_queries` lets you rebuild/A-B queries
    in code without re-prompting — useful for the prompt-design research.
    """

    role_titles: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    locations: list[str] = Field(default_factory=list)
    boolean_queries: list[str] = Field(default_factory=list)


class DiscoveryHit(BaseModel):
    """One deduplicated LinkedIn profile found by the discovery adapter.

    This is the handoff object into the `Normalize + validate` box. Discovery only
    does cheap hygiene (filter to /in/, dedup). Semantic field extraction
    (name/headline/experience) is that downstream box's job, from `title`/`snippet`
    or the scraped HTML.
    """

    profile_url: str
    canonical_key: str            # e.g. "linkedin.com/in/jane-doe-123456"
    title: str = ""
    snippet: str = ""
    source: str = "serper"        # discovery adapter that produced this hit
    found_by_query: str = ""      # which boolean query surfaced it


class DiscoveryResult(BaseModel):
    signals: QuerySignals
    hits: list[DiscoveryHit]
    stats: dict
