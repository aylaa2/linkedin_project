# LinkedIn Sourcing — "Serper — discovery" box

**Owners:** Rareș & Ayla · **Plane:** Discovery (automated adapters, no human)

Takes two inputs — a **job description** (free text) and a **location**
(single, optional) — extracts the JD's signals with an LLM, generates Google
queries (every query carries the given location), hits Serper, and emits
clean deduplicated LinkedIn profile URLs that flow **down into the
`Normalize + validate` box**.

```
        JD + location ┌─ Discovery plane ─────────────────────────────┐
        ─────────────▶│  Serper — discovery  (this repo)              │
                      │    LLM #1 (query gen) → Serper → filter/dedup │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                          Normalize + validate                ← next box
                                              ▼
                          Intelligence plane: Filter · Rank · Review
```

Stack: **Python**, **pydantic-ai**, **Groq (Llama 3.3 70B)**, async (`httpx`),
served by **FastAPI**. Output is Pydantic models / a JSON list of URLs.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in GROQ_API_KEY + SERPER_API_KEY
```

- **Serper key:** https://serper.dev (2,500 free credits).
- **Groq key:** https://console.groq.com

## Run — web UI / API

```bash
uvicorn discovery.api:app --reload
```

- Open http://127.0.0.1:8000 — a JD textarea + a location input, returns the
  profile URLs as a list + raw JSON.
- Or call the endpoint directly; the response is a **JSON list of URLs**:

```bash
curl -s -X POST http://127.0.0.1:8000/api/discover \
  -H 'Content-Type: application/json' \
  -d '{"jd": "Senior React Engineer, Node.js, fintech...", "location": "Bucharest"}'
# -> ["https://www.linkedin.com/in/...", ...]
```

## Run — CLI

```bash
python scripts/run.py data/sample_jd.txt "Bucharest"
python scripts/run.py path/to/jd.txt                       # JD file, no location
python scripts/run.py data/sample_jd.txt "London" --urls   # plain list of links
python scripts/run.py data/sample_jd.txt "London" --json   # raw JSON
python scripts/run.py data/sample_jd.txt --dry-run         # no keys — mock Serper
```

## The handoff contract (into `Normalize + validate`)

`discover(jd, location)` returns a `DiscoveryResult`. Each `hit` is a
`DiscoveryHit`:

```json
{
  "profile_url": "https://www.linkedin.com/in/jane-doe-123456",
  "canonical_key": "linkedin.com/in/jane-doe-123456",
  "title": "Jane Doe - Senior Software Engineer - Acme Corp | LinkedIn",
  "snippet": "Senior Software Engineer at Acme Corp. React, Node.js…",
  "source": "serper",
  "found_by_query": "site:linkedin.com/in (react OR reactjs) fintech \"Bucharest\""
}
```

`discover_urls(jd, location)` returns just the list of URL strings — this
is what `POST /api/discover` responds with and what the scraper stage consumes.

### Division of labour (why fields are "thin" here)

Discovery does only **cheap hygiene**: keep `/in/` URLs, dedup by canonical URL.
**Semantic extraction** (name, headline, experience) belongs to the
`Normalize + validate` box — it has both the Serper `snippet` and the scraped
HTML. So this box deliberately does **not** parse names; it hands over
`title` + `snippet` raw.

## Design notes

- **LLM #1 uses pydantic-ai** with `output_type=QuerySignals`, so the model's
  output is validated into a typed object — no manual JSON parsing.
- **Model = Groq Llama 3.3 70B** (`groq:llama-3.3-70b-versatile`), cheap + fast
  for the discovery plane. Change via `DISCOVERY_MODEL` in `.env`.
- **Queries stay on-input:** the prompt forbids inventing skills/titles/seniority
  not present in the JD; only spelling variants of extracted terms are allowed.
  The queries cover all the JD's cases: title-focused, skills-focused and
  seniority-focused angles.
- **Every query is forced to include `site:linkedin.com/in`** (`_sanitize`), even
  if the model forgets.
- **The location is enforced in code** (`_ensure_location`), not just in the
  prompt: every query gets the user's location appended if the model forgot it.
  The location input overrides any location written in the JD. Single-location
  mode for now: a comma-separated input keeps only the first entry. Query count
  is capped at 6 so a search can't burn Serper credits.
- **Dedup is locale/tracking-proof:** `ro.linkedin.com/in/x?trk=…` and
  `www.linkedin.com/in/x/` collapse to one person (`canonical_key`).
- **Graceful degradation:** no Groq key / LLM failure → deterministic queries
  built straight from the inputs; no Serper key / `--dry-run` → mock results.
  Pipeline always runs.
- **Swap Serper → SerpApi:** only `discovery/serper.py` changes.

## Research left (open TODOs)

1. **Prompt design for LLM #1** — test `SYSTEM_PROMPT` on real criteria sets.
   Watch for over-long queries (Google returns nothing) and off-input drift.
2. **Breadth vs precision** — how many queries × `SERP_PAGES` yields enough good
   candidates without burning credits. Track `stats.raw` vs `stats.hits` (dedup rate).
3. **Cost** — Serper ≈ 1 credit/page. Every query gets an equal share of the
   requested profile count (`max_hits / queries`, ~10 results/page, max 5
   pages/query). When cross-query duplicates leave the pool short, a top-up
   pass draws more results round-robin (already-fetched leftovers first, then
   deeper pages) until the target is reached or the queries run dry.
   `stats.serp_pages` is the credits spent per search — log it so Miruna/Vali
   can budget end-to-end cost.

> Note for the team: the diagram's Discovery plane says **Playwright + proxies**
> for the scraper, while the original text spec said **ScraperAPI instead of
> Playwright**. That's Tania & Mihaela's box — worth confirming which one before
> they start. Doesn't affect discovery.
