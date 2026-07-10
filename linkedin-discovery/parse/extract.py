from pydantic_ai import Agent

from discovery.config import DISCOVERY_MODEL, has_llm
from .models import Candidate

SYSTEM_PROMPT = """You are given the cleaned text of a LinkedIn profile page.
Extract the person's details into the required fields.

Rules:
- Use ONLY information present in the text. NEVER invent or guess.
- If a field is not present, leave it empty ("" for strings, null, or []).
- years_experience: total professional experience as an integer if stated or
  clearly derivable; otherwise null.
- skills: distinct skills / technologies mentioned, as a list.
"""


async def extract(clean_text: str) -> Candidate:
    if not clean_text or not clean_text.strip():
        return Candidate()
    if not has_llm():
        raise RuntimeError("No LLM key set — add GROQ_API_KEY to your .env file.")

    agent = Agent(
        DISCOVERY_MODEL,
        output_type=Candidate,
        system_prompt=SYSTEM_PROMPT,
        defer_model_check=True,
    )
    result = await agent.run(clean_text)
    return result.output
