"""Command line entry point: civic-qa run thunder_bay --out data/"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from civic_qa.pipeline import load_sources, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="civic-qa", description=__doc__)
    parser.add_argument("--config", help="sources YAML (defaults to the bundled sources.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list configured sources")

    run_p = sub.add_parser("run", help="download, standardize and check one or more sources")
    run_p.add_argument("sources", nargs="+")
    run_p.add_argument("--out", default="data", help="output folder (default: data)")
    run_p.add_argument("--strict", action="store_true", help="exit with code 1 if any check is flagged")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sources = load_sources(args.config)

    if args.command == "list":
        for key, cfg in sources.items():
            print(f"{key:15s} {cfg.get('name', '')}")
        return 0

    flagged = False
    for key in args.sources:
        report = run(key, sources, Path(args.out))
        failed = [c["name"] for c in report["checks"] if not c["passed"]]
        flagged = flagged or bool(failed)
        status = "flags: " + ", ".join(failed) if failed else "all checks passed"
        print(f"{key}: {report['rows']:,} rows, {status}")
        if "parser" in report:
            print(f"  parser matched the source's split fields on {report['parser']['all_fields_match']:.2%} of rows")
    return 1 if (args.strict and flagged) else 0
