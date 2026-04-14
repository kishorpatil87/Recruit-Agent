"""
Pipeline Node 3 — Score
Runs EvaluatorAgent for each enriched profile in parallel.
Computes vector similarity scores before calling the LLM.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from agents import EvaluatorAgent
from tools.vector_search import composite_jd_score

log = structlog.get_logger(__name__)


async def _score_one(
    profile: dict,
    jd: dict,
    evaluator: EvaluatorAgent,
) -> dict:
    """Score a single enriched candidate profile."""
    # Compute vector similarity scores (fast, local)
    jd_text = jd.get("raw_text", " ".join(
        jd.get("required_skills", []) + jd.get("preferred_skills", [])
    ))
    resume_text = profile.get("raw_text", " ".join(profile.get("skills", [])))
    jd_skills = jd.get("required_skills", []) + jd.get("preferred_skills", [])

    similarity = composite_jd_score(jd_text, jd_skills, resume_text)

    github = profile.get("github", {})
    linkedin = profile.get("linkedin", {})

    scorecard = await evaluator.evaluate_safe(
        jd=jd,
        candidate=profile,
        github=github,
        linkedin=linkedin,
        similarity_scores=similarity,
        candidate_id=profile.get("candidate_id", ""),
    )

    # Attach identity to scorecard from profile (in case LLM missed it)
    scorecard.setdefault("candidate_id", profile.get("candidate_id", ""))
    scorecard.setdefault("full_name", profile.get("full_name", ""))
    scorecard.setdefault("email", profile.get("email", ""))
    scorecard["resume"] = {k: v for k, v in profile.items() if k not in ("github", "linkedin")}
    scorecard["github"] = github
    scorecard["linkedin"] = linkedin
    scorecard["similarity_scores"] = similarity

    return scorecard


async def score_node(state: dict) -> dict:
    """
    LangGraph node: score_rank
    Scores all enriched profiles in parallel (bounded concurrency = 5).
    """
    enriched: list[dict] = state.get("enriched_profiles", [])
    jd: dict = state.get("jd", {})
    role_level: str = state.get("role_level", "mid")

    evaluator = EvaluatorAgent(role_level=role_level)

    log.info("Scoring candidates", count=len(enriched))

    # Bound concurrency to 1 — local Ollama model handles one request at a time
    semaphore = asyncio.Semaphore(1)

    async def _bounded(profile: dict) -> dict:
        async with semaphore:
            return await _score_one(profile, jd, evaluator)

    tasks = [_bounded(p) for p in enriched]
    scorecards = await asyncio.gather(*tasks)

    log.info("Scoring complete", count=len(scorecards))
    return {**state, "scorecards": list(scorecards)}
