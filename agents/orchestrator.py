"""
Orchestrator Agent — builds ranked leaderboard from scorecards.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog

from config.settings import get_settings
from .base_agent import BaseAgent

log = structlog.get_logger(__name__)
settings = get_settings()


class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_name=settings.ollama_model, temperature=0.0)

    async def build_leaderboard(
        self,
        scorecards: list[dict],
        jd: dict,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or str(uuid.uuid4())

        # Sort purely by total_score descending, break ties by fewer blockers
        sorted_cards = sorted(
            scorecards,
            key=lambda sc: (-sc.get("total_score", 0), sc.get("blocker_count", 0)),
        )
        entries = []

        for i, sc in enumerate(sorted_cards):
            next_score = sorted_cards[i + 1]["total_score"] if i + 1 < len(sorted_cards) else sc.get("total_score", 0)
            delta = round(max(0.0, sc.get("total_score", 0) - next_score), 2)

            resume = sc.get("resume", sc)
            top_skills = resume.get("skills", [])[:5]

            entries.append({
                "rank":               i + 1,
                "candidate_id":       sc.get("candidate_id", f"cand_{i}"),
                "full_name":          sc.get("full_name", "Unknown"),
                "email":              sc.get("email", "") or resume.get("email", ""),
                "total_score":        sc.get("total_score", 0.0),
                "blocker_count":      sc.get("blocker_count", 0),
                "delta_to_next":      delta,
                "confidence":         sc.get("confidence", "medium"),
                "confidence_reason":  sc.get("confidence_reason", ""),
                "top_skills":         top_skills,
                "red_flag_count":     len(sc.get("red_flags", [])),
                "red_flags":          sc.get("red_flags", []),
                "missing_requirements": sc.get("missing_requirements", []),
                "suggested_questions":  sc.get("suggested_questions", []),
                "dimension_scores":   sc.get("dimension_scores", []),
                "error":              sc.get("error", ""),
            })

        return {
            "run_id":            run_id,
            "jd_title":         jd.get("title", ""),
            "jd_company":       jd.get("company", ""),
            "role_level":       settings.role_level,
            "total_candidates": len(entries),
            "entries":          entries,
            "scorecards":       sorted_cards,
            "weights_used":     settings.weights,
            "generated_at":     datetime.utcnow().isoformat(),
        }

