import re
from collections import Counter

from .config import DISCOVERY_MODEL, has_llm
from .models import QuerySignals

# ─────────────────────────────────────────────────────────────────────────────
# PROMPT — iterate on this during prompt-design research.
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a technical recruiter's sourcing assistant.

You receive:
- JOB DESCRIPTION (JD): free text describing a role.
- LOCATION: a single location given by the user (may be empty).

First extract from the JD the signals a recruiter would use to find matching
candidates on LinkedIn: role_titles, must_have skills/technologies,
nice_to_have, seniority. Then produce Google search queries.

Rules for boolean_queries:
- Every query MUST start with: site:linkedin.com/in
- Cover ALL the JD's cases: at least one title-focused query, one
  skills/technology-focused query, and one seniority-focused query — whenever
  the JD contains that signal. Together the queries should cover every major
  signal in the JD.
- Use ONLY signals present in the JD. NEVER invent titles, skills, seniority
  or companies that are not in it.
- You MAY group well-known spelling variants of the SAME term with OR in
  parentheses, e.g. (react OR "react.js" OR reactjs). No new concepts.
- Put multi-word titles / exact skills in "double quotes".
- The LOCATION input overrides the JD: IGNORE any location written in the JD.
- If LOCATION is given, EVERY query MUST include it, in "double quotes".
  If LOCATION is empty, write queries with no location.
- Prefer 3-6 SHORT, DIVERSE queries over one giant query.
- Keep each query under ~12 terms so Google returns results.

Echo the given LOCATION (original wording) into `location`.
"""


def _user_prompt(jd: str, location: str) -> str:
    return (
        f'JOB DESCRIPTION:\n"""\n{jd.strip()}\n"""\n\n'
        f"LOCATION: {location.strip() or '(none)'}\n\n"
        "Extract the signals and produce the queries as specified."
    )


async def generate_queries(jd: str, location: str = "") -> QuerySignals:
    """LLM #1: (JD, location) -> QuerySignals via Groq (pydantic-ai).

    Falls back to a heuristic if there's no API key OR if the model fails to
    return valid structured output (Llama tool-calling is good but not
    bulletproof, so we degrade gracefully instead of crashing).
    """
    if not jd or not jd.strip():
        raise ValueError("Empty job description.")
    # single-location mode: if someone passes "Cluj, Bucharest", keep the first
    location = (location or "").split(",")[0].strip()

    if not has_llm():
        return _heuristic(jd, location)

    # Imported lazily so the dry-run / heuristic path works even without the dep.
    from pydantic_ai import Agent

    try:
        agent = Agent(
            DISCOVERY_MODEL,               # e.g. "groq:llama-3.3-70b-versatile"
            output_type=QuerySignals,
            system_prompt=SYSTEM_PROMPT,
            defer_model_check=True,
        )
        result = await agent.run(_user_prompt(jd, location))
        signals: QuerySignals = result.output
        signals.location = location
        signals.boolean_queries = _ensure_location(
            _sanitize(signals.boolean_queries), location
        )
        if not signals.boolean_queries:      # empty output -> use heuristic
            return _heuristic(jd, location)
        return signals
    except Exception as err:  # noqa: BLE001
        print(f"[LLM #1] Groq call failed, using heuristic. Reason: {err}")
        return _heuristic(jd, location)


def _sanitize(queries: list[str], cap: int = 6) -> list[str]:
    """Force every query to include the site: filter, dedup, cap."""
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
    return out[:cap]


def _ensure_location(queries: list[str], location: str) -> list[str]:
    """Guarantee the location rule no matter what the model produced:
    every query carries the given location."""
    if not location:
        return queries
    out = []
    for q in queries:
        if location.lower() not in q.lower():
            q = f'{q} "{location}"'
        out.append(q)
    return out


_STOP = {
    "the", "and", "for", "with", "you", "our", "will", "are", "have", "this",
    "that", "from", "your", "who", "job", "role", "team", "work", "experience",
    "years", "skills", "required", "preferred", "ability", "strong", "join",
}


def _heuristic(jd: str, location: str) -> QuerySignals:
    """No LLM -> crude keyword extraction so the pipeline still runs."""
    words = re.findall(r"[a-z][a-z+.#-]{2,}", jd.lower())
    freq = Counter(w for w in words if w not in _STOP)
    top = [w for w, _ in freq.most_common(6)]
    if not top:
        return QuerySignals(location=location)
    query = f"site:linkedin.com/in {' '.join(top)}"
    if location:
        query += f' "{location}"'
    return QuerySignals(must_have=top, location=location, boolean_queries=[query])
