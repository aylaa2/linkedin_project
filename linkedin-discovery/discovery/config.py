import os
from dotenv import load_dotenv

load_dotenv()

# ---- LLM (Groq) ----
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# pydantic-ai model string: "groq:<model>". DISCOVERY_MODEL can override the whole
# thing (e.g. to point at another provider) without touching code.
DISCOVERY_MODEL = os.getenv("DISCOVERY_MODEL", f"groq:{GROQ_MODEL}")

# ---- SERP (Serper.dev) ----
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERP_PAGES = int(os.getenv("SERP_PAGES", "2"))
SERP_GL = os.getenv("SERP_GL", "us")
SERP_HL = os.getenv("SERP_HL", "en")


def has_llm() -> bool:
    return bool(GROQ_API_KEY)


def has_serper() -> bool:
    return bool(SERPER_API_KEY)