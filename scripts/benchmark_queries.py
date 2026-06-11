"""
Benchmark script for Voyager metrics collection.

Runs diverse queries through the collaborative graph and writes per-session
records to metrics/sessions.jsonl.  After completion, prints a summary with
the article-ready metrics.

Usage:
    python scripts/benchmark_queries.py                       # full mode, all 25 queries
    python scripts/benchmark_queries.py --mode baseline       # skip refinement rounds
    python scripts/benchmark_queries.py --mode compare        # run each query in both modes
    python scripts/benchmark_queries.py --limit 3             # smoke test (first 3 queries)
    python scripts/benchmark_queries.py --summary             # print summary of past runs
    python scripts/benchmark_queries.py --dry-run             # list queries without running

Requires ANTHROPIC_API_KEY in environment or .env file.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

QUERIES = [
    # Beach / relaxation
    "Greece under $2000, beaches and local food, summer 2026, flying from NYC",
    "Maldives honeymoon for 2, $5000 budget, snorkeling and luxury resorts, March 2026",
    "Bali for solo traveler, $1500 budget, beaches and yoga, July 2026 from LA",
    "Thailand beaches, $1800 for couple, mix of island hopping and street food, October 2026",
    "Portugal Algarve, $2200, beach holiday with wine tasting, September 2026 from London",

    # City / culture
    "Tokyo city break, $3000 for couple, food and tech culture, April 2026 from SFO",
    "Rome art and food trip, $2500, 7 days, June 2026 from Chicago",
    "Istanbul cultural exploration, $1800 solo, historical sites and cuisine, May 2026",
    "Barcelona architecture and nightlife, $2000, 5 days, August 2026 from NYC",
    "Seoul K-culture and food, $2200 couple, winter 2026 from LAX",

    # Adventure / active
    "New Zealand South Island, $4000, hiking and bungee jumping, November 2026",
    "Costa Rica eco-adventure, $2500, zip-lining and wildlife, February 2026 from Miami",
    "Nepal trekking Annapurna, $2000 solo, October 2026, 14 days",
    "Iceland Northern Lights and hot springs, $3500 couple, January 2026",
    "Patagonia hiking Torres del Paine, $4500, 12 days, December 2026",

    # Budget constrained
    "Vietnam on $800, backpacking 10 days, street food and culture, April 2026",
    "Eastern Europe city hop Prague + Budapest, $1200, 8 days, September 2026",
    "Morocco Marrakech and Sahara, $1000 solo, 7 days, March 2026",
    "Mexico City food and culture, $900 solo, 5 days, any month 2026",
    "Cambodia Angkor Wat + beaches, $1100, 10 days, November 2026",

    # Family / specific needs
    "Disney World Orlando family of 4, $6000, 7 days, June 2026",
    "Safari Kenya family of 3, $8000, 10 days, July 2026",
    "Swiss Alps ski holiday family, $7000, 7 days, February 2026",
    "Hawaii family beach vacation, $5000, 10 days, August 2026 from Seattle",
    "Japan family with kids, $4500, cherry blossom season 2026, 10 days from NYC",
]


async def run_query(
    query: str,
    idx: int,
    total: int,
    enable_refinement: bool,
) -> bool:
    from graph.travel_graph import run_collaborative_travel_query
    mode_label = "full" if enable_refinement else "baseline"
    print(f"  [{idx+1}/{total}] [{mode_label}] {query[:65]}...")
    try:
        await run_collaborative_travel_query(query, enable_refinement=enable_refinement)
        print("           ✓")
        return True
    except Exception as e:
        print(f"           ✗ {e}")
        return False


async def run_batch(queries: list[str], enable_refinement: bool) -> None:
    ok = 0
    for i, q in enumerate(queries):
        success = await run_query(q, i, len(queries), enable_refinement)
        if success:
            ok += 1
    mode = "full" if enable_refinement else "baseline"
    print(f"\n  {mode} mode: {ok}/{len(queries)} queries succeeded")


async def run_compare(queries: list[str]) -> None:
    """Run each query in both modes back-to-back for paired comparison."""
    print(f"\nRunning {len(queries)} queries × 2 modes (full then baseline)\n")
    ok = 0
    for i, q in enumerate(queries):
        print(f"  [{i+1}/{len(queries)}] {q[:65]}...")
        for enable_ref, label in ((True, "full"), (False, "baseline")):
            from graph.travel_graph import run_collaborative_travel_query
            try:
                await run_collaborative_travel_query(q, enable_refinement=enable_ref)
                print(f"           [{label}] ✓")
                ok += 1
            except Exception as e:
                print(f"           [{label}] ✗ {e}")
    print(f"\n  compare mode: {ok}/{len(queries)*2} total runs succeeded")


def main() -> None:
    parser = argparse.ArgumentParser(description="Voyager metrics benchmark")
    parser.add_argument(
        "--mode",
        choices=["full", "baseline", "compare"],
        default="full",
        help="full: run with refinement; baseline: skip rounds 2/3; compare: run both",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print queries without running")
    parser.add_argument("--summary", action="store_true", help="Print summary of existing runs")
    parser.add_argument("--limit", type=int, default=None, help="Run only first N queries")
    args = parser.parse_args()

    if args.summary:
        from metrics.collector import print_summary
        print_summary()
        return

    queries = QUERIES[:args.limit] if args.limit else QUERIES

    if args.dry_run:
        print(f"\n{len(queries)} queries (mode={args.mode}):\n")
        for i, q in enumerate(queries, 1):
            print(f"  {i:2}. {q}")
        return

    mode_desc = {
        "full": "with refinement (Rounds 1-3)",
        "baseline": "without refinement (Round 1 only)",
        "compare": "both modes back-to-back",
    }
    print(f"\nRunning {len(queries)} queries — {mode_desc[args.mode]}")
    print("Metrics → metrics/sessions.jsonl\n")

    async def _run() -> None:
        if args.mode == "compare":
            await run_compare(queries)
        else:
            await run_batch(queries, enable_refinement=(args.mode == "full"))

        print("\nGenerating summary...\n")
        from metrics.collector import print_summary
        print_summary()

    asyncio.run(_run())


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    main()
