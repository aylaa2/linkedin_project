import sys
import asyncio
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from discovery.pipeline import discover  # noqa: E402


def main() -> None:
    """Usage:
    python scripts/run.py                       # data/sample_jd.txt
    python scripts/run.py path/to/jd.txt        # your own JD
    python scripts/run.py --dry-run             # no keys (mock Serper + heuristic LLM)
    python scripts/run.py path/to/jd.txt --json # raw JSON output
    """
    args = sys.argv[1:]
    mock = "--dry-run" in args
    as_json = "--json" in args
    file_arg = next((a for a in args if not a.startswith("--")), "data/sample_jd.txt")

    jd = pathlib.Path(file_arg).read_text(encoding="utf-8")
    res = asyncio.run(discover(jd, mock=mock))

    if as_json:
        print(res.model_dump_json(indent=2))
        return

    s = res.signals
    src = "heuristic" if not s.role_titles and not s.seniority else "llm"
    print(f"\n=== LLM #1 (source: {src}) ===")
    print("Role titles :", ", ".join(s.role_titles) or "—")
    print("Must have   :", ", ".join(s.must_have) or "—")
    print("Locations   :", ", ".join(s.locations) or "(remote/none)")
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
