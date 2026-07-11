import sys
import pathlib
import asyncio

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from discovery.pipeline import discover        # noqa: E402
from discovery.scraper import enrich, render_html  # noqa: E402


def main() -> None:
    """Discovery (Serper/ddgs) -> Scraper (Apify/RapidAPI/ScraperAPI) -> HTML.

    Usage:
      python scripts/scrape.py data/sample_jd.txt "Bucharest" --max=10
      python scripts/scrape.py "Senior React dev, Node.js" "Iasi"
      python scripts/scrape.py data/sample_jd.txt --out=rezultate
      python scripts/scrape.py data/sample_jd.txt --dry-run   # fara chei (mock)
    """
    args = sys.argv[1:]
    mock = "--dry-run" in args
    max_hits = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--max=")), 10)
    # workers se scaleaza cu numarul de profile (max 20), sau il fixezi cu --workers=N
    workers = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--workers=")),
                   min(20, max(8, max_hits)))
    out = next((a.split("=", 1)[1] for a in args if a.startswith("--out=")), "profile_html")
    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        print(main.__doc__)
        sys.exit(1)

    jd_arg = pathlib.Path(positional[0])
    jd = jd_arg.read_text(encoding="utf-8") if jd_arg.is_file() else positional[0]
    location = positional[1] if len(positional) > 1 else ""

    # A) DISCOVERY: JD + locatie -> URL-uri de profile
    res = asyncio.run(discover(jd, location, mock=mock, max_hits=max_hits))
    print(f"Discovery: {len(res.hits)} profile gasite. Extrag datele...")

    # B) SCRAPER: URL-uri -> profile structurate (Apify -> RapidAPI -> ScraperAPI, in paralel)
    profiles = enrich(res.hits, workers=workers)
    render_html(profiles, out)

    print(f"\n{len(profiles)} profile:\n")
    for i, p in enumerate(profiles, 1):
        print(f"{i}. {p.name}")
        print(f"   {p.profile_url}")
    print(f"\nGata. Cate un HTML per profil in '{out}/'.")


if __name__ == "__main__":
    main()
