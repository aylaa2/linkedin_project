"""
Scraper box (Normalize + validate) — Tania & Mihaela.

Ia URL-urile produse de cutia de discovery (Serper/ddgs) si scoate datele
STRUCTURATE din fiecare profil: nume, rol, experienta, educatie, locatie.

Lant de fallback cu portofele separate (daca unul se termina, continua urmatorul):
    Apify (harvestapi)  ->  RapidAPI  ->  ScraperAPI
Toate sunt mapate la ACELASI model Profile / acelasi HTML.
"""

import os
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from pydantic import BaseModel, Field

from .config import (
    APIFY_TOKEN, APIFY_ACTOR,
    RAPIDAPI_KEY, RAPIDAPI_HOST, RAPIDAPI_PATH,
    SCRAPERAPI_KEY,
    BRIGHTDATA_TOKEN, BRIGHTDATA_DATASET,
    has_apify, has_rapidapi, has_scraperapi, has_brightdata,
)
from .normalize import canonical_key

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Pune SCRAPER_DEBUG=1 in .env ca sa vezi exact ce raspunde fiecare API.
DEBUG = bool(os.getenv("SCRAPER_DEBUG"))


# ----------------------------- Model -----------------------------

class Profile(BaseModel):
    """Profil imbogatit, gata de afisat. Acelasi format indiferent de sursa."""
    profile_url: str
    name: str = ""
    headline: str = ""
    role: str = ""
    experience: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    location: str = ""
    source: str = ""  # apify / rapidapi / scraperapi / (gol = doar din discovery)
    raw_html: str = ""


# ----------------------------- Helperi de mapare -----------------------------

def _txt(v):
    if isinstance(v, dict):
        return (v.get("linkedinText") or v.get("text") or v.get("name")
                or v.get("title") or v.get("parsed") or "")
    if isinstance(v, list):
        return ", ".join(_txt(x) for x in v if x)
    return v or ""


def _prima(d, *chei):
    for k in chei:
        v = d.get(k)
        if v:
            t = _txt(v)
            if t:
                return t
    return ""


def _perioada(e):
    for k in ("caption", "duration", "dateRange", "period", "employmentPeriod", "timePeriod"):
        v = e.get(k)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, dict):
            s = _txt(v.get("start")) or v.get("startDate", "")
            en = _txt(v.get("end")) or v.get("endDate", "") or "prezent"
            if s:
                return f"{s} - {en}"
    return ""


def _perioada_ym(e):
    def ym(o):
        if isinstance(o, dict):
            y, m = o.get("year"), o.get("month")
            if y:
                return f"{int(m):02d}/{y}" if m else str(y)
            return ""
        return _txt(o)
    s, en = ym(e.get("start")), ym(e.get("end"))
    if s:
        return f"{s} - {en or 'prezent'}"
    return _prima(e, "duration", "dateRange", "period")


def _slug(url):
    return (url or "").split("?")[0].rstrip("/").split("/in/")[-1].lower()


# ----------------------------- Apify -----------------------------

def scrape_apify(urls):
    """Batch: trimite toate URL-urile la actorul Apify. (items, eroare)."""
    endpoint = (f"https://api.apify.com/v2/acts/{APIFY_ACTOR}"
                f"/run-sync-get-dataset-items?token={APIFY_TOKEN}")
    key = "urls" if "harvestapi" in APIFY_ACTOR else "profileUrls"
    try:
        r = requests.post(endpoint, json={key: urls}, timeout=300)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:120]}"
        return r.json(), ""
    except Exception as e:
        return None, str(e)


def map_apify(item):
    p = {"nume": "", "url": "", "experienta": [], "educatie": [], "rol": "", "locatie": ""}
    p["nume"] = _prima(item, "fullName", "name") or \
        " ".join(x for x in [item.get("firstName", ""), item.get("lastName", "")] if x).strip()
    p["url"] = _prima(item, "linkedinUrl", "url", "profileUrl", "inputUrl", "publicIdentifierUrl")
    p["locatie"] = _prima(item, "addressWithCountry", "location", "addressWithoutCountry",
                          "geoLocationName", "locationName")
    for e in item.get("experiences") or item.get("experience") or item.get("positions") or []:
        if not isinstance(e, dict):
            continue
        titlu = _prima(e, "title", "position", "positionTitle", "role", "jobTitle")
        comp = re.sub(r"\s*·.*$", "", _prima(e, "companyName", "company", "subtitle", "organisation"))
        parts = [x for x in [titlu, comp, _perioada(e)] if x]
        linie = " · ".join(dict.fromkeys(parts))
        if linie and linie not in p["experienta"]:
            p["experienta"].append(linie)
    for ed in item.get("educations") or item.get("education") or item.get("schools") or []:
        if not isinstance(ed, dict):
            continue
        scoala = _prima(ed, "title", "schoolName", "school", "institutionName", "subtitle")
        detaliu = _prima(ed, "degree", "fieldOfStudy", "field", "degreeName", "subtitle")
        linie = scoala + (f" · {detaliu}" if detaliu and detaliu != scoala else "")
        if scoala and linie not in p["educatie"]:
            p["educatie"].append(linie)
    if p["experienta"]:
        p["rol"] = p["experienta"][0].split(" · ")[0]
    return p


# ----------------------------- Bright Data -----------------------------

def scrape_brightdata(urls):
    """Batch prin Bright Data (async: trigger -> poll -> download). (items, eroare).
    5000 profile/luna gratis. Portofel separat de Apify/RapidAPI."""
    if not has_brightdata():
        return None, "fara token"
    base = "https://api.brightdata.com/datasets/v3"
    hdr = {"Authorization": f"Bearer {BRIGHTDATA_TOKEN}", "Content-Type": "application/json"}
    try:
        tr = requests.post(
            f"{base}/trigger",
            params={"dataset_id": BRIGHTDATA_DATASET, "include_errors": "true"},
            headers=hdr, json=[{"url": u} for u in urls], timeout=60)
        if tr.status_code >= 400:
            return None, f"trigger HTTP {tr.status_code}: {tr.text[:120]}"
        snap = tr.json().get("snapshot_id")
        if not snap:
            return None, "fara snapshot_id"
        # poll pana e gata (max ~3 min)
        for _ in range(60):
            pr = requests.get(f"{base}/progress/{snap}", headers=hdr, timeout=30)
            st = (pr.json() or {}).get("status")
            if st == "ready":
                break
            if st in ("failed", "error"):
                return None, f"status {st}"
            time.sleep(3)
        else:
            return None, "timeout la poll"
        dl = requests.get(f"{base}/snapshot/{snap}", params={"format": "json"},
                          headers=hdr, timeout=90)
        if dl.status_code >= 400:
            return None, f"download HTTP {dl.status_code}"
        data = dl.json()
        return (data if isinstance(data, list) else [data]), ""
    except Exception as e:
        return None, str(e)


def map_brightdata(item):
    p = {"nume": "", "url": "", "experienta": [], "educatie": [], "rol": "", "locatie": ""}
    if not isinstance(item, dict):
        return p
    p["nume"] = _prima(item, "name", "fullName", "full_name")
    p["url"] = _prima(item, "url", "input_url", "linkedin_url", "id")
    p["locatie"] = _prima(item, "city", "location", "country_code")
    for e in item.get("experience") or item.get("experiences") or []:
        if not isinstance(e, dict):
            continue
        titlu = _prima(e, "title", "position")
        comp = _prima(e, "company", "companyName", "subtitle")
        start = _prima(e, "start_date", "startDate")
        end = _prima(e, "end_date", "endDate") or ("prezent" if start else "")
        per = f"{start} - {end}" if start else _prima(e, "duration")
        parts = [x for x in [titlu, comp, per] if x]
        linie = " · ".join(dict.fromkeys(parts))
        if linie and linie not in p["experienta"]:
            p["experienta"].append(linie)
    for ed in item.get("education") or item.get("educations_details") or []:
        if not isinstance(ed, dict):
            continue
        scoala = _prima(ed, "title", "institute", "school", "schoolName")
        detaliu = _prima(ed, "degree", "field", "fieldOfStudy")
        linie = scoala + (f" · {detaliu}" if detaliu and detaliu != scoala else "")
        if scoala and linie not in p["educatie"]:
            p["educatie"].append(linie)
    if p["experienta"]:
        p["rol"] = p["experienta"][0].split(" · ")[0]
    return p


# ----------------------------- RapidAPI -----------------------------

def map_rapidapi(item):
    p = {"nume": "", "url": "", "experienta": [], "educatie": [], "rol": "", "locatie": ""}
    if not isinstance(item, dict):
        return p
    p["nume"] = _prima(item, "fullName", "name") or \
        " ".join(x for x in [item.get("firstName", ""), item.get("lastName", "")] if x).strip()
    p["url"] = _prima(item, "url", "profileURL", "linkedinUrl") or (
        f"https://www.linkedin.com/in/{item.get('username')}" if item.get("username") else "")
    geo = item.get("geo")
    p["locatie"] = _prima(item, "location", "addressWithCountry") or (
        geo.get("full") if isinstance(geo, dict) else _txt(geo))
    for e in (item.get("position") or item.get("fullPositions")
              or item.get("experiences") or item.get("experience") or []):
        if not isinstance(e, dict):
            continue
        titlu = _prima(e, "title", "role", "position")
        comp = re.sub(r"\s*·.*$", "", _prima(e, "companyName", "company"))
        parts = [x for x in [titlu, comp, _perioada_ym(e)] if x]
        linie = " · ".join(dict.fromkeys(parts))
        if linie and linie not in p["experienta"]:
            p["experienta"].append(linie)
    for ed in item.get("educations") or item.get("education") or []:
        if not isinstance(ed, dict):
            continue
        scoala = _prima(ed, "schoolName", "school", "title", "institutionName")
        detaliu = _prima(ed, "degree", "fieldOfStudy", "field", "degreeName")
        linie = scoala + (f" · {detaliu}" if detaliu and detaliu != scoala else "")
        if scoala and linie not in p["educatie"]:
            p["educatie"].append(linie)
    if p["experienta"]:
        p["rol"] = p["experienta"][0].split(" · ")[0]
    return p


def _rapidapi_endpoints():
    """Lista de API-uri LinkedIn de pe RapidAPI. Fiecare are cota GRATIS proprie,
    toate merg cu aceeasi RAPIDAPI_KEY. Cand unul ramane fara cota, trecem la urmatorul.
    Poti suprascrie din .env: RAPIDAPI_ENDPOINTS=host,path,param;host2,path2,param2"""
    raw = os.getenv("RAPIDAPI_ENDPOINTS", "")
    if raw:
        eps = []
        for part in raw.split(";"):
            bits = [b.strip() for b in part.split(",") if b.strip()]
            if len(bits) >= 2:
                eps.append((bits[0], bits[1], bits[2] if len(bits) > 2 else "url"))
        if eps:
            return eps
    # implicit: cel din .env + alte 2 API-uri LinkedIn (aboneaza-te gratis la ele pe rapidapi.com)
    return [
        (RAPIDAPI_HOST, RAPIDAPI_PATH, "url"),
        ("linkedin-api8.p.rapidapi.com", "/get-profile-data-by-url", "url"),
        ("fresh-linkedin-profile-data.p.rapidapi.com", "/get-linkedin-profile", "linkedin_url"),
    ]


def scrape_rapidapi(url):
    """Roteste prin mai multe API-uri RapidAPI; sare peste cele fara cota (429/403)."""
    if not has_rapidapi():
        return None
    for host, path, param in _rapidapi_endpoints():
        try:
            r = requests.get(
                f"https://{host}{path}",
                headers={"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": host},
                params={param: url},
                timeout=60,
            )
            if r.status_code in (429, 403):  # fara cota / neabonat -> urmatorul endpoint
                if DEBUG:
                    print(f"[rapidapi] {host} HTTP {r.status_code} -> incerc alt endpoint")
                continue
            if r.status_code >= 400:
                continue
            mp = map_rapidapi(r.json())
            if mp["experienta"] or mp["educatie"] or mp["nume"]:
                return mp
        except Exception:
            continue
    return None


# ----------------------------- ScraperAPI (HTML) -----------------------------

def fetch_scraperapi(url):
    if not has_scraperapi():
        return "", "ERR"
    for extra in ({},
                  {"render": "true"},
                  {"render": "true", "premium": "true"},
                  {"render": "true", "ultra_premium": "true"}):
        params = {"api_key": SCRAPERAPI_KEY, "url": url, "country_code": "us"}
        params.update(extra)
        try:
            r = requests.get("https://api.scraperapi.com/", params=params, timeout=120)
            if r.status_code == 200 and len(r.text) > 3000:
                return r.text, 200
        except Exception:
            continue
    return "", "ERR"


def extrage_detalii(html_text):
    """Parseaza JSON-LD-ul (si sectiunile HTML) dintr-o pagina de profil."""
    out = {"nume": "", "experienta": [], "educatie": [], "rol": "", "locatie": ""}
    if not html_text or BeautifulSoup is None:
        return out
    soup = BeautifulSoup(html_text, "html.parser")
    for sc in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(sc.string or sc.get_text() or "")
        except Exception:
            continue
        noduri = data.get("@graph", [data]) if isinstance(data, dict) else data
        if isinstance(noduri, dict):
            noduri = [noduri]
        for node in noduri:
            if not isinstance(node, dict) or node.get("@type") != "Person":
                continue
            if node.get("name"):
                out["nume"] = node["name"]
            works = node.get("worksFor", [])
            works = [works] if isinstance(works, dict) else works
            for w in works:
                t = _org_text(w)
                if t and t not in out["experienta"]:
                    out["experienta"].append(t)
            alum = node.get("alumniOf", [])
            alum = [alum] if isinstance(alum, dict) else alum
            for a in alum:
                t = _org_text(a)
                if t and t not in out["educatie"]:
                    out["educatie"].append(t)
            addr = node.get("address")
            if isinstance(addr, dict):
                out["locatie"] = addr.get("addressLocality") or addr.get("addressRegion") or ""
    if out["experienta"]:
        out["rol"] = out["experienta"][0].split(" @ ")[0]
    return out


def _org_text(w):
    if isinstance(w, str):
        return w
    if not isinstance(w, dict):
        return ""
    if "Role" in str(w.get("@type", "")) or "worksFor" in w or "startDate" in w:
        inner = w.get("worksFor") or w.get("memberOf") or w.get("alumniOf") or {}
        comp = inner.get("name", "") if isinstance(inner, dict) else str(inner)
        rol = w.get("roleName") or ""
        start = str(w.get("startDate", "") or "")[:4]
        end = str(w.get("endDate", "") or "")[:4] or ("prezent" if start else "")
        per = f" ({start}-{end})" if start else ""
        return f"{rol} @ {comp}{per}" if (rol and comp) else f"{(comp or rol)}{per}"
    return w.get("name", "")


# ----------------------------- Orchestrare -----------------------------

def _nume_din_slug(slug):
    slug = re.sub(r"-[0-9a-f]{6,}$", "", slug)
    slug = re.sub(r"-\d+$", "", slug)
    return slug.replace("-", " ").title()


def _are_date(d):
    return bool(d and (d.get("experienta") or d.get("educatie")))


def _fallback_unul(hit):
    """Pentru UN profil: RapidAPI -> ScraperAPI, pana obtine experienta/educatie.
    Returneaza (profile_url, data, sursa, raw_html)."""
    if has_rapidapi():
        mp = scrape_rapidapi(hit.profile_url)
        if _are_date(mp):
            return hit.profile_url, mp, "rapidapi", ""
    if has_scraperapi():
        html, _ = fetch_scraperapi(hit.profile_url)
        d = extrage_detalii(html)
        if _are_date(d):
            return hit.profile_url, d, "scraperapi", html
    return hit.profile_url, None, "", ""


def _index(items, mapper):
    """slug -> dict mapat, pentru item-urile care au url."""
    idx = {}
    for it in items or []:
        mp = mapper(it)
        if mp.get("url"):
            idx[_slug(mp["url"])] = mp
        # Indexeaza si dupa URL-ul original/de input pentru a tolera redirecturile de la LinkedIn
        if isinstance(it, dict):
            for k in ("input_url", "inputUrl", "id"):
                val = it.get(k)
                if isinstance(val, str) and val:
                    idx[_slug(val)] = mp
            orig_q = it.get("originalQuery")
            if isinstance(orig_q, dict):
                val = orig_q.get("url")
                if isinstance(val, str) and val:
                    idx[_slug(val)] = mp
    return idx


def _slug_hit(h):
    return canonical_key(h.profile_url).split("/in/")[-1]


def _batch(nume_sursa, hits, scrape_fn, mapper, date, partial):
    """Ruleaza un provider BATCH pe hit-urile date; completeaza `date` (cu experienta)
    si `partial` (nume/locatie chiar fara experienta). Returneaza hit-urile ramase."""
    if not hits:
        return hits
    items, err = scrape_fn([h.profile_url for h in hits])
    if err:
        print(f"[{nume_sursa}] {err}")
        return hits
    idx = _index(items, mapper)
    cu = sum(1 for mp in idx.values() if _are_date(mp))
    print(f"[{nume_sursa}] {len(items or [])} profile, {cu} cu experienta")
    if items and cu == 0:
        try:
            print(f"[{nume_sursa}] chei in primul item: {list(items[0].keys())[:20]}")
            if isinstance(items[0], dict) and "error" in items[0]:
                print(f"[{nume_sursa}] eroare item: {items[0]['error']}")
        except Exception:
            pass
    ramase = []
    for h in hits:
        mp = idx.get(_slug_hit(h))
        if mp:
            partial.setdefault(h.profile_url, mp)
        if mp and _are_date(mp):
            date[h.profile_url] = (mp, nume_sursa, "")
        else:
            ramase.append(h)
    return ramase


def enrich(hits, workers=8):
    """Ordine: Bright Data -> Apify -> RapidAPI -> ScraperAPI, pana obtine
    experienta + educatie pentru fiecare profil. Ordinea listei e pastrata."""
    date = {}      # profile_url -> (data cu experienta, sursa)
    partial = {}   # profile_url -> data (nume/locatie, chiar fara experienta)
    ramase = list(hits)

    # 1) Bright Data (batch) - primul
    if has_brightdata():
        ramase = _batch("brightdata", ramase, scrape_brightdata, map_brightdata, date, partial)

    # 2) Apify (batch)
    if has_apify() and ramase:
        ramase = _batch("apify", ramase, scrape_apify, map_apify, date, partial)
    elif not has_apify() and not has_brightdata():
        print("[scraper] fara BRIGHTDATA_TOKEN / APIFY_TOKEN")

    # 3) RapidAPI -> ScraperAPI (per-profil, in PARALEL) pentru cele ramase
    if ramase and (has_rapidapi() or has_scraperapi()):
        ok_r = ok_s = 0
        with ThreadPoolExecutor(max_workers=min(workers, len(ramase))) as ex:
            for url, d, sursa, raw_html in ex.map(_fallback_unul, ramase):
                if _are_date(d):
                    date[url] = (d, sursa, raw_html)
                    ok_r += (sursa == "rapidapi")
                    ok_s += (sursa == "scraperapi")
        print(f"[fallback] din {len(ramase)} ramase -> RapidAPI:{ok_r} ScraperAPI:{ok_s} "
              f"inca goale:{len(ramase) - ok_r - ok_s}")

    # 4) Construieste Profile in ordinea originala
    profiles = []
    for h in hits:
        if h.profile_url in date:
            data, sursa, raw_html = date[h.profile_url]
        else:
            data, sursa, raw_html = partial.get(h.profile_url, {}), "", ""
        nume = data.get("nume") or _nume_din_title(h.title) or _nume_din_slug(_slug_hit(h))
        profiles.append(Profile(
            profile_url=h.profile_url,
            name=nume,
            headline=h.title or "",
            role=data.get("rol", ""),
            experience=data.get("experienta", []),
            education=data.get("educatie", []),
            location=data.get("locatie", ""),
            source=sursa,
            raw_html=raw_html,
        ))
    cu_exp = sum(1 for p in profiles if p.experience or p.education)
    print(f"[total] {cu_exp}/{len(profiles)} profile au experienta/educatie")
    return profiles


def _nume_din_title(title):
    t = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title or "").strip()
    if " - " in t:
        return t.split(" - ", 1)[0].strip()
    return ""


# ----------------------------- HTML -----------------------------

_CSS = """
  body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin:24px; color:#000; }
  .nume { font-size:20px; font-weight:700; margin:0 0 4px; }
  .src { font-size:12px; color:#0a7d3c; margin:0 0 12px; }
  .src.gol { color:#8a6d00; }
  .camp { margin:6px 0; font-size:15px; }
  .eticheta { font-weight:700; }
  ul { margin:4px 0 0 20px; padding:0; }
  a { color:#0a66c2; }
"""


def _lista(items):
    items = items or []
    return ("<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in items) + "</ul>") if items else "—"


def _esc(s):
    import html
    return html.escape(s or "")


def render_html(profiles, out_dir="profile_html"):
    """Scrie cate un .html per profil (01 = primul). Returneaza lista de cai."""
    os.makedirs(out_dir, exist_ok=True)
    cai = []
    for i, p in enumerate(profiles, 1):
        if p.experience or p.education:
            src = f'<div class="src">✓ date din profil (sursa: {p.source})</div>'
        else:
            src = '<div class="src gol">doar din discovery (fara APIFY_TOKEN / RAPIDAPI_KEY)</div>'
        doc = f"""<!DOCTYPE html>
<html lang="ro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(p.name)}</title><style>{_CSS}</style></head>
<body>
  <div class="nume">{_esc(p.name or 'Necunoscut')}</div>
  {src}
  <div class="camp"><span class="eticheta">Rol:</span> {_esc(p.role) or _esc(p.headline) or '—'}</div>
  <div class="camp"><span class="eticheta">Experiență:</span> {_lista(p.experience)}</div>
  <div class="camp"><span class="eticheta">Educație:</span> {_lista(p.education)}</div>
  <div class="camp"><span class="eticheta">Locație:</span> {_esc(p.location) or '—'}</div>
  <div class="camp"><span class="eticheta">Profil:</span> <a href="{_esc(p.profile_url)}">{_esc(p.profile_url)}</a></div>
</body></html>"""
        slug = re.sub(r"[^a-z0-9]+", "-", (p.name or f"profil-{i}").lower()).strip("-") or f"profil-{i}"
        cale = os.path.join(out_dir, f"{i:02d}_{slug}.html")
        with open(cale, "w", encoding="utf-8") as f:
            f.write(doc)
        cai.append(cale)
        
        # Daca avem HTML original (raw) de la ScraperAPI, il salvam separat
        if getattr(p, "raw_html", ""):
            cale_raw = os.path.join(out_dir, f"{i:02d}_{slug}_raw.html")
            with open(cale_raw, "w", encoding="utf-8") as f:
                f.write(p.raw_html)
            cai.append(cale_raw)
    return cai
