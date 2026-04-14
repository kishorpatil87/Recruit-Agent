"""
Scorecard schema — the complete evaluation result for a single candidate.
This is the canonical data structure produced by the Evaluator agent and
consumed by the Ranker/Orchestrator.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


GapSeverity = Literal["blocker", "preferred", "trainable"]
Confidence = Literal["high", "medium", "low"]
RoleLevel = Literal["junior", "mid", "senior", "lead"]


class SkillGap(BaseModel):
    skill: str
    severity: GapSeverity
    notes: str = ""


class DimensionScore(BaseModel):
    dimension: str
    raw_score: float      # 0-100 normalised within dimension
    weighted_score: float # raw_score * weight * max_points  → contribution to total
    band: str             # exceptional / strong / adequate / weak / absent
    rationale: str


class GitHubProfile(BaseModel):
    username: str = ""
    profile_url: str = ""
    public_repos: int = 0
    total_commits_last_year: int = 0
    contribution_streak_days: int = 0
    top_languages: list[str] = Field(default_factory=list)
    pinned_repos: list[str] = Field(default_factory=list)
    stars_total: int = 0
    followers: int = 0
    jd_language_match: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class LinkedInProfile(BaseModel):
    profile_url: str = ""
    exists: bool = False
    headline: str = ""
    current_title: str = ""
    location: str = ""
    tenure_years: float = 0.0
    endorsements_count: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)


class ParsedResume(BaseModel):
    candidate_id: str
    raw_path: str
    full_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    skills: list[str] = Field(default_factory=list)
    total_experience_years: float = 0.0
    education: list[dict[str, str]] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[dict[str, str]] = Field(default_factory=list)
    work_history: list[dict[str, Any]] = Field(default_factory=list)
    raw_text: str = ""


class Scorecard(BaseModel):
    """Full evaluation output for one candidate."""

    # Identity
    candidate_id: str
    full_name: str = ""
    email: str = ""

    # Parsed data
    resume: ParsedResume
    github: GitHubProfile = Field(default_factory=GitHubProfile)
    linkedin: LinkedInProfile = Field(default_factory=LinkedInProfile)

    # Scores
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    total_score: float = 0.0          # 0-100
    blocker_count: int = 0

    # Gaps & flags
    missing_requirements: list[SkillGap] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)

    # Confidence
    confidence: Confidence = "medium"
    confidence_reason: str = ""
    role_level: RoleLevel = "mid"

    # Generated content
    suggested_questions: list[str] = Field(default_factory=list, max_length=3)

    # Meta
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = ""
    error: str = ""                   # non-empty if pipeline failed for this candidate
