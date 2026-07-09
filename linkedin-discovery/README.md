# LinkedIn Sourcing — "Serper — discovery" box

**Owners:** Rareș & Ayla · **Plane:** Discovery (automated adapters, no human)

Your box in the architecture diagram. Takes a pasted JD, generates Google queries,
hits Serper, and emits clean deduplicated LinkedIn profile hits that flow **down
into the `Normalize + validate` box (pydantic-ai · Claude Haiku)**.

```
                    ┌─ Discovery plane ────────────────────────────┐
   JD text  ───────▶│  Serper — discovery  (this repo)             │
                    │    LLM #1 (query gen) → Serper → filter/dedup │
                    └───────────────────────┬──────────────────────┘
                                             ▼
                        Normalize + validate  (pydantic-ai · Haiku)   ← next box
                                             ▼
                        Intelligence plane: Filter · Rank · Review
```

Stack matches the diagram: **Python**, **pydantic-ai**, **Claude Haiku**, async
(`httpx`) so it drops into a **FastAPI worker**. Output is Pydantic models.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in ANTHROPIC_API_KEY + SERPER_API_KEY
```

- **Serper key:** https://serper.dev (2,500 free credits).
- **Anthropic key:** https://console.anthropic.com

## Run

```bash
python scripts/run.py --dry-run              # no keys — mock Serper + heuristic query gen
python scripts/run.py                        # real run on data/sample_jd.txt
python scripts/run.py path/to/jd.txt
python scripts/run.py path/to/jd.txt --json  # raw JSON
```

## The handoff contract (into `Normalize + validate`)

`discover(jd)` returns a `DiscoveryResult`. Each `hit` is a `DiscoveryHit`:

```json
{
  "profile_url": "https://www.linkedin.com/in/jane-doe-123456",
  "canonical_key": "linkedin.com/in/jane-doe-123456",
  "title": "Jane Doe - Senior Software Engineer - Acme Corp | LinkedIn",
  "snippet": "Senior Software Engineer at Acme Corp. React, Node.js…",
  "source": "serper",
  "found_by_query": "site:linkedin.com/in \"software engineer\" (react OR reactjs)"
}
```

Called from a worker (Intelligence plane / FastAPI):

```python
from discovery import discover
result = await discover(jd_text)
for hit in result.hits:
    enqueue_scrape(hit)      # -> Headless scraper, then Normalize + validate
```

### Division of labour (why fields are "thin" here)

Discovery does only **cheap hygiene**: keep `/in/` URLs, dedup by canonical URL.
**Semantic extraction** (name, headline, experience, `data_source` full/snippet)
belongs to the `Normalize + validate` box — it has both the Serper `snippet` and
the scraped HTML, and it's the one running Haiku for validation. So this box
deliberately does **not** parse names; it hands over `title` + `snippet` raw.

## Design notes

- **LLM #1 uses pydantic-ai** with `output_type=QuerySignals`, so the model's
  output is validated into a typed object — no manual JSON parsing.
- **Model = Claude Haiku** (`anthropic:claude-haiku-4-5`), matching the diagram's
  "cheap" discovery plane. Change via `DISCOVERY_MODEL` in `.env`.
- **Every query is forced to include `site:linkedin.com/in`** (`_sanitize`), even
  if the model forgets.
- **Dedup is locale/tracking-proof:** `ro.linkedin.com/in/x?trk=…` and
  `www.linkedin.com/in/x/` collapse to one person (`canonical_key`).
- **Graceful degradation:** no Anthropic key → heuristic keyword query;
  no Serper key / `--dry-run` → mock results. Pipeline always runs.
- **Swap Serper → SerpApi:** only `discovery/serper.py` changes.

## Research left (your open TODOs)

1. **Prompt design for LLM #1** — test `SYSTEM_PROMPT` on 5–10 real JDs. Watch for
   over-long queries (Google returns nothing), missing seniority, wrong location.
2. **Breadth vs precision** — how many queries × `SERP_PAGES` yields enough good
   candidates without burning credits. Track `stats.raw` vs `stats.hits` (dedup rate).
3. **Cost** — Serper ≈ 1 credit/page → `queries × SERP_PAGES` credits per JD. Log it
   so Miruna/Vali can budget end-to-end cost per JD.

> Note for the team: the diagram's Discovery plane says **Playwright + proxies**
> for the scraper, while the original text spec said **ScraperAPI instead of
> Playwright**. That's Tania & Mihaela's box — worth confirming which one before
> they start. Doesn't affect discovery.
