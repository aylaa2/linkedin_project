import re
import unicodedata
from difflib import SequenceMatcher

SKILL_ALIASES: dict[str, set[str]] = {
    "javascript": {"javascript", "js", "ecmascript"},
    "typescript": {"typescript", "ts"},
    "python": {"python", "python3"},
    "c++": {"c++", "cpp", "cplusplus"},
    "c#": {"c#", "csharp", ".net c#"},
    "node.js": {"node", "nodejs", "node.js"},
    "react": {"react", "reactjs", "react.js"},
    "vue.js": {"vue", "vuejs", "vue.js"},
    "angular": {"angular", "angularjs"},
    "amazon web services": {"aws", "amazon web services"},
    "google cloud platform": {"gcp", "google cloud", "google cloud platform"},
    "microsoft azure": {"azure", "microsoft azure"},
    "postgresql": {"postgres", "postgresql"},
    "machine learning": {"machine learning", "ml"},
    "artificial intelligence": {"artificial intelligence", "ai"},
    "natural language processing": {"natural language processing", "nlp"},
    "large language models": {"large language model", "large language models", "llm", "llms"},
    "kubernetes": {"k8s", "kubernetes"},
    "continuous integration": {"ci", "continuous integration"},
    "continuous delivery": {"cd", "continuous delivery", "continuous deployment"},
}

def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold().strip()
    value = re.sub(r"[\s_/|]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value

def canonical_skill(skill: str) -> str:
    normalized = normalize_text(skill)
    for canonical, aliases in SKILL_ALIASES.items():
        normalized_aliases = {normalize_text(alias) for alias in aliases}
        if normalized == normalize_text(canonical) or normalized in normalized_aliases:
            return canonical
    return normalized

def skills_are_similar(first: str, second: str, threshold: float = 0.88) -> bool:
    first_canonical = canonical_skill(first)
    second_canonical = canonical_skill(second)
    if first_canonical == second_canonical:
        return True
    if len(first_canonical) >= 4 and len(second_canonical) >= 4 and (first_canonical in second_canonical or second_canonical in first_canonical):
        return True
    return SequenceMatcher(None, first_canonical, second_canonical).ratio() >= threshold

def best_skill_match(required_skill: str, candidate_skills: list[str]) -> str | None:
    for candidate_skill in candidate_skills:
        if skills_are_similar(required_skill, candidate_skill):
            return candidate_skill
    return None

def calculate_skills_score(required_skills: list[str], preferred_skills: list[str], candidate_skills: list[str]) -> tuple[float, list[str], list[str]]:
    required_matches: list[str] = []
    preferred_matches: list[str] = []
    missing_required: list[str] = []

    for skill in required_skills:
        match = best_skill_match(skill, candidate_skills)
        if match:
            required_matches.append(f"{skill} -> {match}")
        else:
            missing_required.append(skill)

    for skill in preferred_skills:
        match = best_skill_match(skill, candidate_skills)
        if match:
            preferred_matches.append(f"{skill} -> {match}")

    if not required_skills and not preferred_skills:
        return 100.0, [], []

    required_ratio = len(required_matches) / len(required_skills) if required_skills else None
    preferred_ratio = len(preferred_matches) / len(preferred_skills) if preferred_skills else None

    if required_ratio is not None and preferred_ratio is not None:
        score = 100 * (0.8 * required_ratio + 0.2 * preferred_ratio)
    elif required_ratio is not None:
        score = 100 * required_ratio
    else:
        score = 100 * (preferred_ratio or 0.0)

    return round(score, 2), required_matches + preferred_matches, missing_required

def calculate_experience_score(candidate_years: int | None, minimum_years: int | None) -> float:
    if minimum_years is None or minimum_years <= 0:
        return 100.0
    if candidate_years is None:
        return 35.0
    return round(min(100.0, 100.0 * candidate_years / minimum_years), 2)

def clamp_score(score: float) -> float:
    return round(max(0.0, min(100.0, score)), 2)
