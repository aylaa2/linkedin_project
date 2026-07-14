import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)
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


# ---- Scraper (Normalize + validate box — Tania & Mihaela) ----
# Aduce datele structurate din profil. Lant de fallback cu portofele separate:
#   Apify (harvestapi) -> RapidAPI -> ScraperAPI
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
APIFY_ACTOR = os.getenv("APIFY_ACTOR", "harvestapi~linkedin-profile-scraper")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "linkedin-data-api.p.rapidapi.com")
RAPIDAPI_PATH = os.getenv("RAPIDAPI_PATH", "/get-profile-data-by-url")

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY") or os.getenv("SCRAPER_API_KEY") or ""

# Bright Data - 5000 profile/luna GRATIS, portofel separat, robust (async trigger/poll).
# Token de la https://brightdata.com/cp/setting/users
BRIGHTDATA_TOKEN = os.getenv("BRIGHTDATA_TOKEN", "")
# Dataset LinkedIn people profiles (implicit); poti schimba din .env daca ai alt id.
BRIGHTDATA_DATASET = os.getenv("BRIGHTDATA_DATASET", "gd_l1viktl72bvl7bjuj0")


def has_llm() -> bool:
    return bool(GROQ_API_KEY)


def has_serper() -> bool:
    return bool(SERPER_API_KEY)


def has_apify() -> bool:
    return bool(APIFY_TOKEN)


def has_rapidapi() -> bool:
    return bool(RAPIDAPI_KEY)


def has_scraperapi() -> bool:
    return bool(SCRAPERAPI_KEY)


def has_brightdata() -> bool:
    return bool(BRIGHTDATA_TOKEN)