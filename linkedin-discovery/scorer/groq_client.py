import json
import os
from pydantic import ValidationError

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from models import Candidate, GroqEvaluation

SYSTEM_PROMPT = """
You are a recruitment matching evaluator.

Your task is to compare a candidate's professional profile with a recruiter's
job requirement. Evaluate only job-relevant professional information.

Rules:
1. Do not infer sensitive personal attributes.
2. Do not use name, gender, age, ethnicity, religion, disability, marital
   status or other protected characteristics in scoring.
3. Treat missing information as unknown, not automatically false.
4. Extract explicit requirements conservatively. Do not invent requirements.
5. Required skills must contain only technologies or competencies presented as
   mandatory or central to the request.
6. Preferred skills must contain technologies or competencies presented as
   optional, advantageous or secondary.
7. Scores must be between 0 and 100.
8. title_relevance_score measures semantic relevance of headline/current title
   to the requested role.
9. location_score is 100 when there is no location constraint. When remote work
   is accepted, do not penalize an otherwise compatible location.
10. education_score is 100 when no education requirement is stated.
11. profile_quality_score evaluates how much relevant evidence is available in
    the profile, not writing style or personal identity.
12. holistic_llm_score is an independent overall professional-fit estimate.
13. Explain the score using concrete evidence from the supplied data.
14. Return only JSON matching the provided schema.
""".strip()

def build_user_prompt(candidate: Candidate, recruiter_requirement: str) -> str:
    edu_text = "\n".join([f"- {ed}" for ed in candidate.education])
    skills_text = ", ".join(candidate.skills)
    exp_text = f"- {candidate.current_title} la {candidate.current_company} ({candidate.years_experience or 0} ani)"

    return f"""
CERINȚA RECRUITERULUI:
{recruiter_requirement}

PROFIL CANDIDAT:
Nume: {candidate.name}
Locație: {candidate.location}
Headline: {candidate.headline}
Rezumat: {candidate.summary}

Experiență curentă:
{exp_text}

Educație:
{edu_text}

Skill-uri: {skills_text}

Extract the job requirements, evaluate the semantic components and provide a
holistic fit score. Do not calculate the final weighted score; Python will do
that deterministically.
""".strip()

def get_groq_evaluation(
    candidate: Candidate,
    recruiter_requirement: str,
    model: str = "llama-3.3-70b-versatile",
) -> GroqEvaluation:
    if OpenAI is None:
        raise RuntimeError("Pachetul 'openai' nu este instalat. Rulează: pip install openai")
        
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Lipsește GROQ_API_KEY. Adaugă cheia în variabilele de mediu.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=120.0,
    )

    schema_str = json.dumps(GroqEvaluation.model_json_schema(), indent=2)
    sys_prompt_json = f"{SYSTEM_PROMPT}\n\nTrebuie să răspunzi DOAR cu un JSON valid care respectă strict această schemă:\n{schema_str}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt_json},
            {"role": "user", "content": build_user_prompt(candidate, recruiter_requirement)},
        ],
        response_format={"type": "json_object"},
    )

    try:
        raw_json = response.choices[0].message.content
        return GroqEvaluation.model_validate_json(raw_json)
    except (ValidationError, AttributeError, IndexError) as exc:
        raise RuntimeError(f"Eroare la parsarea răspunsului LLM: {exc}") from exc
