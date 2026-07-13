from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """One person's structured, validated profile."""

    profile_url: str = ""                            
    name: str = ""
    headline: str = ""                               
    location: str = ""
    years_experience: int | None = None
    skills: list[str] = Field(default_factory=list)
    current_title: str = ""
    current_company: str = ""
    education: list[str] = Field(default_factory=list)
    summary: str = ""                                
