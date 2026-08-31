from typing import Optional
from pydantic import BaseModel, Field


class QuerySignals(BaseModel):

    role_titles: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    location: str = ""
    boolean_queries: list[str] = Field(default_factory=list)


class DiscoveryHit(BaseModel):

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
