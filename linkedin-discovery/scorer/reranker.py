try:
    from FlagEmbedding import FlagReranker
except ImportError:
    FlagReranker = None

from models import Candidate

USE_RERANKER = True
RERANKER_MIN_PROFILES = 3
RERANKER_THRESHOLD = 0.2

def candidate_to_document(candidate: Candidate) -> str:
    lines = []
    if candidate.skills:
        lines.append(f"Skill-uri principale: {', '.join(candidate.skills)}")
    if candidate.years_experience is not None:
        lines.append(f"Ani de experiență: {candidate.years_experience}")
    if candidate.location:
        lines.append(f"Locație: {candidate.location}")
    if candidate.summary:
        lines.append(f"Sumar: {candidate.summary}")
    if candidate.education:
        lines.append(f"Studii: {', '.join(candidate.education)}")
    return "\n".join(lines)

_reranker: "FlagReranker | None" = None

def get_reranker(model_name: str = "BAAI/bge-reranker-v2-m3") -> "FlagReranker":
    global _reranker
    if FlagReranker is None:
        raise RuntimeError("Pachetul 'FlagEmbedding' nu este instalat. Rulează: pip install FlagEmbedding")
    if _reranker is None:
        _reranker = FlagReranker(model_name, use_fp16=False)
    return _reranker

def rerank_candidates(
    recruiter_requirement: str,
    candidates: list[Candidate],
    model_name: str = "BAAI/bge-reranker-v2-m3",
) -> tuple[list[tuple[Candidate, float]], list[tuple[Candidate, float]]]:
    if not candidates:
        return [], []

    reranker = get_reranker(model_name)
    pairs = [(recruiter_requirement, candidate_to_document(candidate)) for candidate in candidates]
    scores = reranker.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]

    scored = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    
    top_scored = []
    bottom_scored = []
    
    for i, (candidate, score) in enumerate(scored):
        if score > RERANKER_THRESHOLD or i < RERANKER_MIN_PROFILES:
            top_scored.append((candidate, round(score, 4)))
        else:
            bottom_scored.append((candidate, round(score, 4)))

    return top_scored, bottom_scored
