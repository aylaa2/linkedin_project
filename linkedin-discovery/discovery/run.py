import sys
import asyncio
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from discovery.pipeline import discover  # noqa: E402


def main() -> None:
    """Usage:
    python scripts/run.py data/sample_jd.txt "Bucharest"
    python scripts/run.py path/to/jd.txt                # JD file, no location
    python scripts/run.py "Senior React dev..." "Iasi"  # literal JD text works too
    python scripts/run.py data/sample_jd.txt "London" --urls   # plain list of links
    python scripts/run.py data/sample_jd.txt "London" --json   # raw JSON output
    python scripts/run.py data/sample_jd.txt --max=20          # how many profiles
    python scripts/run.py data/sample_jd.txt --dry-run         # no keys (mock Serper)
    """
    args = sys.argv[1:]
    mock = "--dry-run" in args
    as_json = "--json" in args
    urls_only = "--urls" in args
    max_hits = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--max=")), 50)
    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        print(main.__doc__)
        sys.exit(1)

    # first positional: a JD file path if it exists, otherwise literal JD text
    jd_arg = pathlib.Path(positional[0])
    jd = jd_arg.read_text(encoding="utf-8") if jd_arg.is_file() else positional[0]
    location = positional[1] if len(positional) > 1 else ""

    res = asyncio.run(discover(jd, location, mock=mock, max_hits=max_hits))

    if urls_only:
        # plain list of links: prints to terminal, or `> links.txt` to save to a file
        for h in res.hits:
            print(h.profile_url)
        return

    if as_json:
        print(res.model_dump_json(indent=2))
        return

    s = res.signals
    src = "heuristic" if not s.role_titles and not s.seniority else "llm"
    print(f"\n=== LLM #1 (source: {src}) ===")
    print("Role titles :", ", ".join(s.role_titles) or "—")
    print("Must have   :", ", ".join(s.must_have) or "—")
    print("Seniority   :", s.seniority or "—")
    print("Location    :", s.location or "(none)")
    print("\nQueries:")
    for i, q in enumerate(s.boolean_queries, 1):
        print(f"  {i}. {q}")

    st = res.stats
    print(f"\n=== Hits ({st['hits']} unique from {st['raw']} raw) ===")
    for i, h in enumerate(res.hits, 1):
        print(f"\n[{i}] {h.profile_url}  <{h.source}>")
        print(f"    {h.title}")
    print("")


if __name__ == "__main__":
    main()
