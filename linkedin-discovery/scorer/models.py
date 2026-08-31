from __future__ import annotations
from pydantic import BaseModel, Field, field_validator

class RerankedCandidate(BaseModel):
    rank: int
    candidate_name: str
    profile_url: str
    relevance_score: float

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

    @field_validator("years_experience")
    @classmethod
    def validate_years_experience(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("years_experience nu poate fi negativ.")
        return value

class ExtractedRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_years_experience: int | None = None
    target_titles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)

    @field_validator(
        "required_skills", "preferred_skills", "target_titles",
        "preferred_locations", "education_requirements",
        mode="before"
    )
    @classmethod
    def convert_none_to_list(cls, v):
        return [] if v is None else v

class GroqEvaluation(BaseModel):
    extracted_requirements: ExtractedRequirements

    title_relevance_score: float = Field(ge=0, le=100)
    location_score: float = Field(ge=0, le=100)
    education_score: float = Field(ge=0, le=100)
    profile_quality_score: float = Field(ge=0, le=100)
    holistic_llm_score: float = Field(ge=0, le=100)

    matched_strengths: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    explanation: str

    @field_validator("matched_strengths", "missing_requirements", mode="before")
    @classmethod
    def convert_none_to_list(cls, v):
        return [] if v is None else v

class ScoreWeights(BaseModel):
    skills: float = 0.45
    experience: float = 0.25
    title: float = 0.15
    location: float = 0.05
    education: float = 0.05
    profile_quality: float = 0.05

    heuristic_weight: float = 0.75
    llm_weight: float = 0.25

    def validate_totals(self) -> None:
        heuristic_components = (
            self.skills + self.experience + self.title +
            self.location + self.education + self.profile_quality
        )
        if abs(heuristic_components - 1.0) > 1e-9:
            raise ValueError("Ponderile componentelor euristice trebuie să însumeze 1.0.")

        if abs(self.heuristic_weight + self.llm_weight - 1.0) > 1e-9:
            raise ValueError("heuristic_weight și llm_weight trebuie să însumeze 1.0.")

class CandidateScoreResult(BaseModel):
    candidate_name: str
    profile_url: str
    evaluation_status: str
    reranker_score: float | None = None
    final_score: float | None = None
    heuristic_score: float | None = None
    holistic_llm_score: float | None = None
    component_scores: dict[str, float] | None = None
    extracted_requirements: ExtractedRequirements | None = None
    matched_strengths: list[str] | None = None
    missing_requirements: list[str] | None = None
    explanation: str | None = None
