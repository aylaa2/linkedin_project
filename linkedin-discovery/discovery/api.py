"""FastAPI app for the discovery box.

Run from linkedin-discovery/:
    uvicorn discovery.api:app --reload

GET  /              minimal web UI (job description + location inputs)
POST /api/discover  {"jd": "...", "location": "..."} -> JSON list of enriched profile objects
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .pipeline import discover
from .scraper import enrich, render_html, Profile

app = FastAPI(title="LinkedIn Discovery")

# Serveste folderul profile_html ca fisiere statice
os.makedirs("profile_html", exist_ok=True)
app.mount("/profiles", StaticFiles(directory="profile_html"), name="profiles")


class DiscoverRequest(BaseModel):
    jd: str = Field(..., description="Job description (free text)")
    location: str = Field("", description="A single location (optional)")
    max_hits: int = Field(50, ge=1, le=200)


@app.post("/api/discover")
async def api_discover(req: DiscoverRequest) -> list[Profile]:
    try:
        # 1. Cauta URL-uri (Discovery)
        result = await discover(req.jd, req.location, max_hits=req.max_hits)
        
        # 2. Extrage informatii complete (Scraping)
        profiles = enrich(result.hits)
        
        # 3. Salveaza fisierele HTML local in profile_html/
        render_html(profiles, "profile_html")
        
        return profiles
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _PAGE


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LinkedIn Discovery</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 16px; color: #1c1c1c; }
  h1 { font-size: 1.4rem; }
  label { display: block; font-weight: 600; margin-top: 16px; }
  .hint { color: #777; font-weight: 400; font-size: 0.85rem; }
  textarea, input { width: 100%; padding: 10px; margin-top: 6px; font-size: 15px; box-sizing: border-box;
                    border: 1px solid #ccc; border-radius: 6px; font-family: inherit; }
  textarea { min-height: 180px; resize: vertical; }
  button { margin-top: 18px; padding: 10px 28px; font-size: 15px; border: 0; border-radius: 6px;
           background: #0a66c2; color: #fff; cursor: pointer; }
  button:disabled { background: #9bbcd8; cursor: wait; }
  #status { color: #555; }
  ol { padding-left: 22px; }
  li { margin: 8px 0; word-break: break-all; }
  pre { background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }
</style>
</head>
<body>
<h1>LinkedIn profile discovery</h1>

<label>Job description <span class="hint">paste the JD — free text</span></label>
<textarea id="jd" placeholder="We are looking for a Senior React Engineer with Node.js experience in the fintech domain..."></textarea>

<label>Location <span class="hint">one location, optional</span></label>
<input id="location" placeholder="Bucharest">

<label>Profiles needed <span class="hint">1–200</span></label>
<input id="max_hits" type="number" min="1" max="200" value="50">

<button id="go">Search</button>
<p id="status"></p>
<ol id="list"></ol>
<pre id="json" hidden></pre>

<script>
const $ = (id) => document.getElementById(id);

// Converteste numele intr-un slug de fisier (la fel cum face scraper.py)
function toSlug(name, idx) {
  if (!name) return `profil-${idx}`;
  return name.toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '') || `profil-${idx}`;
}

async function search() {
  const jd = $("jd").value.trim();
  if (!jd) { $("status").textContent = "Paste a job description."; return; }
  $("status").textContent = "Searching…";
  $("list").innerHTML = "";
  $("json").hidden = true;
  $("go").disabled = true;
  try {
    const res = await fetch("/api/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jd,
        location: $("location").value.trim(),
        max_hits: Math.min(200, Math.max(1, parseInt($("max_hits").value, 10) || 50)),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    $("status").textContent = data.length + " profiles processed";
    
    data.forEach((p, idx) => {
      const li = document.createElement("li");
      
      const fileIndex = idx + 1;
      const paddedIndex = String(fileIndex).padStart(2, '0');
      const slug = toSlug(p.name, fileIndex);
      const localHtmlUrl = `/profiles/${paddedIndex}_${slug}.html`;

      li.innerHTML = `
        <a href="${localHtmlUrl}" target="_blank">${p.name || 'Profile HTML'}</a> - 
        <a href="${p.profile_url}" target="_blank" rel="noopener">LinkedIn Link</a>
      `;
      $("list").appendChild(li);
    });
    
    $("json").textContent = JSON.stringify(data, null, 2);
    $("json").hidden = false;
  } catch (err) {
    $("status").textContent = "Error: " + err.message;
  }
  $("go").disabled = false;
}

$("go").addEventListener("click", search);
for (const id of ["location", "max_hits"]) {
  $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
}
</script>
</body>
</html>
"""

