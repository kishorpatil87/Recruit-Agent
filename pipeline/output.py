"""
Pipeline output node — JSON + CSV + Markdown outputs.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import structlog

from config.settings import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


def _write_json(leaderboard: dict, output_dir: Path) -> str:
    run_id = leaderboard.get("run_id", "run")[:8]
    path = output_dir / f"leaderboard_{run_id}.json"
    path.write_text(json.dumps(leaderboard, indent=2, default=str), encoding="utf-8")
    log.info("JSON written", path=str(path))
    return str(path)


def _write_csv(leaderboard: dict, output_dir: Path) -> str:
    run_id = leaderboard.get("run_id", "run")[:8]
    path = output_dir / f"shortlist_{run_id}.csv"
    entries = leaderboard.get("entries", [])
    fields = [
        "rank", "full_name", "email", "total_score",
        "confidence", "blocker_count", "red_flag_count",
        "top_skills", "suggested_questions",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for e in entries:
            row = dict(e)
            row["top_skills"] = "; ".join(e.get("top_skills", []))
            row["suggested_questions"] = " | ".join(e.get("suggested_questions", []))
            writer.writerow(row)
    log.info("CSV written", path=str(path))
    return str(path)


def _write_markdown(leaderboard: dict, output_dir: Path) -> str:
    run_id = leaderboard.get("run_id", "run")[:8]
    path = output_dir / f"report_{run_id}.md"
    lines = [
        f"# Recruitment Report — {leaderboard.get('jd_title', '')}",
        f"Generated: {leaderboard.get('generated_at', '')}",
        "",
        "## Summary",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Candidates | {leaderboard.get('total_candidates', 0)} |",
        "",
        "## Ranked Candidates",
        "",
        "| Rank | Name | Score /100 | Confidence | Skill Gaps |",
        "|------|------|------------|------------|------------|",
    ]
    for e in leaderboard.get("entries", []):
        lines.append(
            f"| {e['rank']} | {e['full_name']} | {e['total_score']:.1f} | "
            f"{e['confidence']} | {e['blocker_count']} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Markdown written", path=str(path))
    return str(path)


async def output_node(state: dict) -> dict:
    leaderboard: dict = state.get("leaderboard", {})
    output_dir = Path(state.get("output_dir", settings.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "json":     _write_json(leaderboard, output_dir),
        "csv":      _write_csv(leaderboard, output_dir),
        "markdown": _write_markdown(leaderboard, output_dir),
    }
    leaderboard["output_paths"] = paths
    log.info("Output complete", paths=list(paths.keys()))
    return {**state, "leaderboard": leaderboard, "output_paths": paths}
