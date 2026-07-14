"""
candidate_scorer.py

Scorarea unui candidat LinkedIn fata de cerinta unui recruiter.

Flux:
1. Primiți cerința recruiterului și lista de candidați ca obiecte Pydantic.
2. Filtrați candidații folosind un reranker local semantic.
3. Trimiteți top candidații către Groq.
4. Groq extrage cerințele structurate și oferă scoruri semantice.
5. Combinați rezultatele într-o listă finală completă.

Exemplu:
    from candidate_scorer import process_candidates_pipeline, Candidate
    results = process_candidates_pipeline(requirement_text, candidates_list)
"""

from __future__ import annotations
import os
from dotenv import load_dotenv

from models import Candidate, ScoreWeights, CandidateScoreResult
from heuristics import calculate_skills_score, calculate_experience_score, clamp_score
from groq_client import get_groq_evaluation
from reranker import USE_RERANKER, rerank_candidates

def score_candidate(
    candidate: Candidate,
    recruiter_requirement: str,
    weights: ScoreWeights | None = None,
    model: str | None = None,
    reranker_score: float | None = None,
) -> CandidateScoreResult:
    weights = weights or ScoreWeights()
    weights.validate_totals()

    selected_model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    llm_evaluation = get_groq_evaluation(
        candidate=candidate,
        recruiter_requirement=recruiter_requirement,
        model=selected_model,
    )

    requirements = llm_evaluation.extracted_requirements

    skills_score, skill_matches, missing_required_skills = calculate_skills_score(
        required_skills=requirements.required_skills,
        preferred_skills=requirements.preferred_skills,
        candidate_skills=candidate.skills,
    )

    experience_score = calculate_experience_score(
        candidate_years=candidate.years_experience,
        minimum_years=requirements.minimum_years_experience,
    )

    component_scores = {
        "skills": skills_score,
        "experience": experience_score,
        "title": clamp_score(llm_evaluation.title_relevance_score),
        "location": clamp_score(llm_evaluation.location_score),
        "education": clamp_score(llm_evaluation.education_score),
        "profile_quality": clamp_score(llm_evaluation.profile_quality_score),
    }

    heuristic_score = (
        component_scores["skills"] * weights.skills
        + component_scores["experience"] * weights.experience
        + component_scores["title"] * weights.title
        + component_scores["location"] * weights.location
        + component_scores["education"] * weights.education
        + component_scores["profile_quality"] * weights.profile_quality
    )

    holistic_llm_score = clamp_score(llm_evaluation.holistic_llm_score)

    final_score = (
        heuristic_score * weights.heuristic_weight
        + holistic_llm_score * weights.llm_weight
    )

    strengths = list(dict.fromkeys(
        llm_evaluation.matched_strengths
        + [f"Skill match: {match}" for match in skill_matches]
    ))

    missing = list(dict.fromkeys(
        llm_evaluation.missing_requirements
        + [f"Required skill missing: {skill}" for skill in missing_required_skills]
    ))

    return CandidateScoreResult(
        candidate_name=candidate.name,
        profile_url=candidate.profile_url,
        evaluation_status="FULL_EVALUATION",
        reranker_score=reranker_score,
        final_score=clamp_score(final_score),
        heuristic_score=clamp_score(heuristic_score),
        holistic_llm_score=holistic_llm_score,
        component_scores=component_scores,
        extracted_requirements=requirements,
        matched_strengths=strengths,
        missing_requirements=missing,
        explanation=llm_evaluation.explanation,
    )

def process_candidates_pipeline(
    recruiter_requirement: str,
    candidates: list[Candidate],
    model: str | None = None,
) -> list[CandidateScoreResult]:
    """
    Funcția principală pentru a procesa candidați dintr-un alt proiect.
    Primește direct obiectele și returnează rezultatele (fără a citi din fișiere).
    """
    load_dotenv()
    if USE_RERANKER:
        print("Aplicăm pre-filtrarea (reranking)...")
        top_scored, bottom_scored = rerank_candidates(
            recruiter_requirement=recruiter_requirement,
            candidates=candidates
        )
        print(f"Am selectat {len(top_scored)} candidați pentru evaluarea detaliată, am sărit {len(bottom_scored)}.")
    else:
        top_scored = [(c, None) for c in candidates]
        bottom_scored = []

    all_results = []
    top_results = []
    
    for candidate, rerank_score in top_scored:
        print(f"Evaluăm candidatul: {candidate.name}...")
        result = score_candidate(
            candidate=candidate,
            recruiter_requirement=recruiter_requirement,
            model=model,
            reranker_score=rerank_score
        )
        top_results.append(result)
        
    top_results.sort(key=lambda r: r.final_score or 0.0, reverse=True)
    all_results.extend(top_results)
    
    for candidate, rerank_score in bottom_scored:
        result = CandidateScoreResult(
            candidate_name=candidate.name,
            profile_url=candidate.profile_url,
            evaluation_status="SKIPPED_BY_RERANKER",
            reranker_score=rerank_score,
            final_score=None,
            heuristic_score=None,
            holistic_llm_score=None,
            component_scores=None,
            extracted_requirements=None,
            matched_strengths=None,
            missing_requirements=None,
            explanation=None,
        )
        all_results.append(result)

    return all_results
