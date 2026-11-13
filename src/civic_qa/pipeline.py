"""Download, standardize, check and write one source."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

import geopandas as gpd
import yaml

from civic_qa.download import fetch_layer
from civic_qa.evaluate import parser_accuracy
from civic_qa.qa import assert_not_empty, failing_examples, run_checks
from civic_qa.standardize import standardize

log = logging.getLogger(__name__)


def load_sources(path: str | Path | None = None) -> dict:
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = resources.files("civic_qa").joinpath("sources.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def process(raw: gpd.GeoDataFrame, key: str, config: dict) -> tuple[gpd.GeoDataFrame, dict]:
    """Standardize and check an already downloaded layer. Kept separate from run() so it can be tested offline."""
    assert_not_empty(raw, f"{key} download")
    std = standardize(raw, key, config)
    assert_not_empty(std, f"{key} standardized output")

    checks = run_checks(std, config.get("thresholds"))
    report = {
        "source": key,
        "name": config.get("name"),
        "url": config.get("url"),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(std),
        "checks": [c.to_dict() for c in checks],
        "examples": {c.name: failing_examples(std, c.name) for c in checks if not c.passed},
    }
    if config.get("mode") == "parse" and config.get("check_against"):
        report["parser"] = parser_accuracy(
            raw, config["full_address"], config["check_against"], config.get("hyphen_order", "unit-number")
        )
    return std, report


def write_outputs(std: gpd.GeoDataFrame, report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    key = report["source"]
    std.to_file(out_dir / f"{key}.gpkg", layer="civic_address", driver="GPKG")
    (out_dir / f"{key}_qa.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out_dir / f"{key}_qa.md").write_text(render_markdown(report), encoding="utf-8")
    return out_dir


def render_markdown(report: dict) -> str:
    lines = [
        f"# QA report: {report['name'] or report['source']}",
        "",
        f"Source: {report['url']}  ",
        f"Run at: {report['run_at']}  ",
        f"Rows: {report['rows']:,}",
        "",
        "| Check | Failed | Rate | Threshold | Result |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for c in report["checks"]:
        result = "pass" if c["passed"] else "**flag**"
        lines.append(f"| {c['name']} | {c['failed']:,} | {c['rate']:.2%} | {c['threshold']:.0%} | {result} |")
    for name, examples in report.get("examples", {}).items():
        if examples:
            lines += ["", f"Examples for `{name}`: " + ", ".join(f"`{e}`" for e in examples)]
    parser = report.get("parser")
    if parser:
        lines += [
            "",
            "## Parser accuracy against the source's own split fields",
            "",
            f"Rows compared: {parser['rows']:,}  ",
            f"All compared fields match: {parser['all_fields_match']:.2%}",
            "",
        ]
        lines += [f"- {field}: {acc:.2%}" for field, acc in parser["field_accuracy"].items()]
    return "\n".join(lines) + "\n"


def run(key: str, sources: dict, out_dir: Path) -> dict:
    if key not in sources:
        raise KeyError(f"Unknown source {key!r}. Known: {', '.join(sources)}")
    config = sources[key]
    log.info("Downloading %s", config["url"])
    raw = fetch_layer(config["url"], id_field=config.get("id_field", "OBJECTID"))
    std, report = process(raw, key, config)
    write_outputs(std, report, out_dir)
    return report
