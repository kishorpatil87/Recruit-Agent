"""
Leaderboard schema — ranked output of a full batch evaluation run.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .scorecard import Scorecard


class LeaderboardEntry(BaseModel):
    rank: int
    candidate_id: str
    full_name: str
    total_score: float
    blocker_count: int
    delta_to_next: float = 0.0      # score gap to next-ranked candidate
    confidence: str = "medium"
    top_skills: list[str] = Field(default_factory=list)
    red_flag_count: int = 0


class Leaderboard(BaseModel):
    """Final ranked batch output — ready for dashboard or export."""
    run_id: str
    jd_title: str
    jd_company: str = ""
    role_level: str = "mid"

    total_candidates: int

    entries: list[LeaderboardEntry] = Field(default_factory=list)
    scorecards: list[Scorecard] = Field(default_factory=list)   # full detail

    weights_used: dict[str, float] = Field(default_factory=dict)

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    output_paths: dict[str, str] = Field(default_factory=dict)
