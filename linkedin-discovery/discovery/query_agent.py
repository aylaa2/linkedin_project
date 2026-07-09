import re
from collections import Counter

from .config import DISCOVERY_MODEL, has_llm
from .models import QuerySignals

# ─────────────────────────────────────────────────────────────────────────────
# PROMPT — iterate on this during prompt-design research.
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a technical recruiter's sourcing assistant.
Given a job description (JD), extract the signals a recruiter would use to find
matching candidates on LinkedIn via Google, and produce Google search queries.

Rules for boolean_queries:
- Every query MUST start with: site:linkedin.com/in
- Put multi-word titles / exact skills in "double quotes".
- Group synonyms with parentheses and OR, e.g. (react OR "react.js" OR reactjs).
- Prefer 3-6 SHORT, DIVERSE queries over one giant query. Vary the angle:
  one title-focused, one skills-focused, one seniority/location-focused, etc.
- Do NOT invent a location if the JD is remote or has none.
- Keep each query under ~12 terms so Google returns results.
"""


def _user_prompt(jd: str) -> str:
    return (
        f'JOB DESCRIPTION:\n"""\n{jd.strip()}\n"""\n\n'
        "Extract the signals and produce the queries as specified."
    )


async def generate_queries(jd: str) -> QuerySignals:
    """LLM #1: JD -> QuerySignals via Groq (pydantic-ai).

    Falls back to a heuristic if there's no API key OR if the model fails to
    return valid structured output (Llama tool-calling is good but not as
    bulletproof as Claude's, so we degrade gracefully instead of crashing).
    """
    if not has_llm():
        return _heuristic(jd)

    # Imported lazily so the dry-run / heuristic path works even without the dep.
    from pydantic_ai import Agent

    try:
        agent = Agent(
            DISCOVERY_MODEL,               # e.g. "groq:llama-3.3-70b-versatile"
            output_type=QuerySignals,
            system_prompt=SYSTEM_PROMPT,
            defer_model_check=True,
        )
        result = await agent.run(_user_prompt(jd))
        signals: QuerySignals = result.output
        signals.boolean_queries = _sanitize(signals.boolean_queries)
        if not signals.boolean_queries:      # empty output -> use heuristic
            return _heuristic(jd)
        return signals
    except Exception as err:  # noqa: BLE001
        print(f"[LLM #1] Groq call failed, using heuristic. Reason: {err}")
        return _heuristic(jd)


def _sanitize(queries: list[str]) -> list[str]:
    """Force every query to include the site: filter, dedup, cap at 6."""
    seen, out = set(), []
    for q in queries or []:
        if not isinstance(q, str):
            continue
        q = q.strip()
        if not q:
            continue
        if not re.search(r"site:linkedin\.com/in", q, re.IGNORECASE):
            q = f"site:linkedin.com/in {q}"
        key = q.lower()
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out[:6]


_STOP = {
    "the", "and", "for", "with", "you", "our", "will", "are", "have", "this",
    "that", "from", "your", "who", "job", "role", "team", "work", "experience",
    "years", "skills", "required", "preferred", "ability", "strong", "join",
}


def _heuristic(jd: str) -> QuerySignals:
    """No API key -> crude keyword extraction so the pipeline still runs."""
    words = re.findall(r"[a-z][a-z+.#-]{2,}", jd.lower())
    freq = Counter(w for w in words if w not in _STOP)
    top = [w for w, _ in freq.most_common(6)]
    return QuerySignals(
        must_have=top,
        boolean_queries=[f"site:linkedin.com/in {' '.join(top)}"] if top else [],
    )