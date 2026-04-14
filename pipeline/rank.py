"""
Pipeline Node 4 — Rank
Sorts candidates by total_score and adds justification strings.
No decision tiers — pure score-based ranking.
"""
from __future__ import annotations

import uuid

import structlog

from agents import OrchestratorAgent

log = structlog.get_logger(__name__)


async def rank_node(state: dict) -> dict:
    scorecards: list[dict] = state.get("scorecards", [])
    jd: dict = state.get("jd", {})
    run_id: str = state.get("run_id", str(uuid.uuid4()))
    top_n: int = state.get("top_n", 10)

    orchestrator = OrchestratorAgent()

    log.info("Building leaderboard", candidates=len(scorecards))
    leaderboard = await orchestrator.build_leaderboard(scorecards, jd, run_id)

    # Top-N candidates by rank (pure score order)
    entries = leaderboard.get("entries", [])
    shortlisted = entries[:top_n]

    # Add justification string to each top-N entry
    for entry in shortlisted:
        score = entry.get("total_score", 0)
        conf = entry.get("confidence", "medium")
        blockers = entry.get("blocker_count", 0)
        entry["justification"] = (
            f"Score: {score}/100 | Confidence: {conf} | Blockers: {blockers}"
        )

    leaderboard["shortlisted"] = shortlisted

    log.info(
        "Ranking complete",
        total=len(entries),
        top_n=len(shortlisted),
        top_score=entries[0]["total_score"] if entries else 0,
    )
    return {**state, "leaderboard": leaderboard}
