"""
Command Line Interface for DIDI Media Collectors.
Commands:
  list                  Show configured open sources
  probe <source_id>     Verify robots.txt, sitemaps, and sample extraction
  run                   Harvest articles incrementally or for a backfill window
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer

from .config import load_registry
from .discovery import parse_date
from .pipeline import probe as probe_source, run_source

app = typer.Typer(add_completion=False, help="DIDI open media collectors")


def _date(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    d = parse_date(s)
    if d is None:
        raise typer.BadParameter(f"Unparseable date: {s}")
    return d


@app.callback()
def main(verbose: bool = typer.Option(False, "-v", "--verbose")):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command("list")
def list_sources(config: Optional[Path] = typer.Option(None, help="Path to sources.yaml")):
    """List configured open sources."""
    reg = load_registry(config)
    for s in reg.sources:
        flag = "on " if s.enabled else "off"
        print(f"{flag} T{s.tier} {s.language:5} {s.id:20} {s.name}")


@app.command()
def probe(source: str, config: Optional[Path] = typer.Option(None)):
    """Probe a source configuration: robots permissions, sitemaps, test extraction."""
    reg = load_registry(config)
    src = reg.get(source)
    res = probe_source(src, reg)
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))


@app.command()
def run(
    source: Optional[List[str]] = typer.Option(None, "--source", "-s", help="Source ID(s) to collect"),
    language: Optional[str] = typer.Option(None, help="Filter by language: it | de | multi"),
    since: Optional[str] = typer.Option(None, help="Backfill start date (YYYY-MM-DD)"),
    until: Optional[str] = typer.Option(None, help="End date (default: now)"),
    data_dir: Path = typer.Option(Path("data"), envvar="DIDI_DATA_DIR"),
    limit: Optional[int] = typer.Option(None, help="Max candidate articles to process"),
    max_pages: int = typer.Option(2000, help="Cap per run per source"),
    dry_run: bool = typer.Option(False, help="Only list discovered candidate URLs"),
    config: Optional[Path] = typer.Option(None),
):
    """Harvest open articles."""
    reg = load_registry(config)
    sources = reg.select(source or None, language=language)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results, failed = [], []

    for s in sources:
        try:
            res = run_source(
                src=s,
                reg=reg,
                data_dir=data_dir,
                run_id=run_id,
                since=_date(since),
                until=_date(until),
                limit=limit,
                max_pages=max_pages,
                dry_run=dry_run,
            )
            results.append(res)
        except Exception as e:
            logging.exception("[%s] run failed", s.id)
            failed.append({"source": s.id, "error": repr(e)})

    report = {"run_id": run_id, "results": results, "failed": failed}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if failed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

