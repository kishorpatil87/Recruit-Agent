"""
LangGraph pipeline state definition.
All nodes receive and return this typed dict.
"""
from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────────────────────────
    mode: str                        # "single" | "batch"
    jd: dict                         # JobDescription dict
    resume_files: list[str]          # absolute paths
    role_level: str                  # junior | mid | senior | lead
    top_n: int
    output_dir: str
    webhook_url: str
    run_id: str

    # ── Stage 1: Ingest ───────────────────────────────────────────────────────
    parsed_resumes: list[dict]       # list of ParsedResume dicts (heuristic)

    # ── Stage 2: Enrich ───────────────────────────────────────────────────────
    enriched_profiles: list[dict]    # parsed_resume + github + linkedin merged

    # ── Stage 3: Score ────────────────────────────────────────────────────────
    scorecards: list[dict]           # list of raw Scorecard dicts from Evaluator

    # ── Stage 4: Rank ─────────────────────────────────────────────────────────
    leaderboard: dict                # full Leaderboard dict

    # ── Stage 5: Output ───────────────────────────────────────────────────────
    output_paths: dict[str, str]     # json_path, csv_path, pdf_path
    webhook_delivered: bool

    # ── Meta ──────────────────────────────────────────────────────────────────
    errors: list[str]
