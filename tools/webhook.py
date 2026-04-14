"""
Webhook / ATS delivery tool.
Pushes the final leaderboard JSON to a configured endpoint (Greenhouse, Lever, custom).
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


async def push_to_webhook(payload: dict[str, Any], webhook_url: str | None = None) -> bool:
    """
    POST leaderboard payload to ATS webhook.
    Returns True on success, False on failure.
    """
    url = webhook_url or settings.webhook_url
    if not url:
        log.info("No webhook URL configured; skipping delivery")
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "X-Source": "recruitment-agent"},
                timeout=30,
            )
            resp.raise_for_status()
            log.info("Webhook delivered", url=url, status=resp.status_code)
            return True
    except httpx.HTTPStatusError as e:
        log.error("Webhook HTTP error", url=url, status=e.response.status_code, body=e.response.text[:200])
        return False
    except Exception as e:
        log.error("Webhook delivery failed", url=url, error=str(e))
        return False


def format_ats_payload(leaderboard_dict: dict) -> dict:
    """
    Transform internal leaderboard dict into an ATS-friendly payload schema.
    """
    entries = leaderboard_dict.get("entries", [])
    scores = [e.get("total_score", 0) for e in entries]
    return {
        "source": "recruitment-agent",
        "run_id": leaderboard_dict.get("run_id", ""),
        "job_title": leaderboard_dict.get("jd_title", ""),
        "company": leaderboard_dict.get("jd_company", ""),
        "generated_at": leaderboard_dict.get("generated_at", ""),
        "summary": {
            "total": leaderboard_dict.get("total_candidates", 0),
            "top_score": round(scores[0], 1) if scores else 0,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        },
        "candidates": [
            {
                "rank":          e.get("rank"),
                "name":          e.get("full_name"),
                "score":         e.get("total_score"),
                "confidence":    e.get("confidence"),
                "blocker_count": e.get("blocker_count"),
            }
            for e in entries
        ],
    }

