"""
Evaluator Agent — Ollama local model (zero API cost).
Scores candidates against a JD on a comprehensive 100-point rubric.
Evaluates: JD Match, Education, Technical Skills, Projects,
Experience, GitHub Activity, and LinkedIn Presence.
"""
from __future__ import annotations

import json
from typing import Any

from config.settings import get_settings
from .base_agent import BaseAgent

settings = get_settings()

_SYSTEM = """\
Score a candidate against a job description on 7 dimensions. Return ONLY valid JSON.

Dimensions (max points):
1. "JD Match" (25) — skills overlap, keyword match
2. "Education" (10) — degree relevance, GPA
3. "Technical Skills" (15) — depth, breadth, JD alignment
4. "Project Quality" (10) — complexity, techstack, impact
5. "Experience" (15) — years, role relevance
6. "GitHub Activity" (15) — repos, commits, languages
7. "LinkedIn Presence" (10) — title match, completeness

Bands: exceptional | strong | adequate | weak | absent
If GitHub/LinkedIn data is missing, score 0 (absent).
total_score = sum of all weighted_scores (max 100).

Return this JSON:
{"dimension_scores": [{"dimension": "name", "raw_score": 0, "weighted_score": 0, "band": "weak", "rationale": "reason"}], "total_score": 0, "blocker_count": 0, "missing_requirements": [{"skill": "X", "severity": "blocker"}], "red_flags": [], "confidence": "high", "confidence_reason": "reason", "suggested_questions": ["Q1?", "Q2?"]}
"""

_USER_TMPL = """\
=== JOB DESCRIPTION ===
Title: {title}
Required Skills: {required_skills}
Preferred Skills: {preferred_skills}
Min Experience: {min_exp} years
Domain: {domain}

=== CANDIDATE ===
Name: {name}
Email: {email}
Skills: {skills}
Experience: {exp_years} years
Education: {education}
Work History: {work}
Projects: {projects}
Certifications: {certifications}

=== GITHUB (if any) ===
{github}

=== LINKEDIN (if any) ===
{linkedin}

=== SIMILARITY PRE-SCORES ===
Keyword Overlap: {keyword:.0%}  |  TF-IDF Similarity: {semantic:.0%}  |  Composite: {composite:.0%}

Score this candidate now. Return the JSON only.
"""


class EvaluatorAgent(BaseAgent):
    def __init__(self, role_level: str = "mid"):
        super().__init__(model_name=settings.ollama_model, temperature=0.0)
        self.role_level = role_level

    async def evaluate_safe(
        self,
        jd: dict,
        candidate: dict,
        github: dict,
        linkedin: dict,
        similarity_scores: dict,
        candidate_id: str = "",
    ) -> dict[str, Any]:
        """Evaluate candidate — returns fallback scorecard on error."""
        try:
            result = await self._evaluate(jd, candidate, github, linkedin, similarity_scores)
            result["candidate_id"] = candidate_id or candidate.get("candidate_id", "")
            result["full_name"] = result.get("full_name") or candidate.get("full_name", "Unknown")
            result["email"] = result.get("email") or candidate.get("email", "")
            result["role_level"] = self.role_level
            result["error"] = ""
            return result
        except Exception as e:
            err_msg = str(e)
            print(f"[ERROR] Evaluation failed for {candidate_id}: {err_msg}")
            return self._fallback(candidate, candidate_id, err_msg)

    async def _evaluate(self, jd, candidate, github, linkedin, similarity_scores):
        # Build education string with degree + institution + percentage/GPA
        education_entries = candidate.get("education") or []
        edu_parts = []
        for e in education_entries[:3]:
            parts = []
            if e.get("degree"):
                parts.append(e["degree"])
            if e.get("institution"):
                parts.append(f"@ {e['institution']}")
            if e.get("percentage"):
                parts.append(f"({e['percentage']}%)")
            elif e.get("gpa"):
                parts.append(f"(GPA: {e['gpa']})")
            if e.get("year"):
                parts.append(f"[{e['year']}]")
            edu_parts.append(" ".join(parts))
        education_str = "; ".join(edu_parts) if edu_parts else "Not specified"

        # Build projects string with techstack info
        project_entries = candidate.get("projects") or []
        proj_parts = []
        for p in project_entries[:3]:
            desc = p.get("description", p.get("name", ""))[:60]
            techstack = p.get("techstack", p.get("technologies", ""))
            if isinstance(techstack, list):
                techstack = ", ".join(techstack)
            if techstack:
                proj_parts.append(f"{desc} [Tech: {techstack}]")
            else:
                proj_parts.append(desc)
        projects_str = "; ".join(proj_parts) if proj_parts else "None listed"

        # Build certifications string
        certs = candidate.get("certifications") or []
        certs_str = ", ".join(certs[:5]) if certs else "None"

        user = _USER_TMPL.format(
            title=jd.get("title", ""),
            required_skills=", ".join(jd.get("required_skills", [])),
            preferred_skills=", ".join(jd.get("preferred_skills", [])),
            min_exp=jd.get("min_experience_years", 0),
            domain=jd.get("domain", ""),
            name=candidate.get("full_name", "Unknown"),
            email=candidate.get("email", ""),
            skills=", ".join(candidate.get("skills", [])[:20]),
            exp_years=round(float(candidate.get("total_experience_years", 0) or 0), 1),
            education=education_str,
            work="; ".join(
                f"{w.get('title','')} at {w.get('company','')}"
                for w in (candidate.get("work_history") or [])[:3]
            ) or "Not specified",
            projects=projects_str,
            certifications=certs_str,
            github=json.dumps({
                k: v for k, v in github.items()
                if k in ("username", "public_repos", "total_commits_last_year",
                          "contribution_streak_days", "top_languages", "jd_language_match",
                          "stars_total", "followers")
            }, default=str) if github and github.get("exists") else "No GitHub data",
            linkedin=json.dumps({
                k: v for k, v in linkedin.items()
                if k in ("exists", "headline", "current_title", "tenure_years", "connections")
            }, default=str) if linkedin and linkedin.get("exists") else "No LinkedIn data",
            keyword=similarity_scores.get("keyword_score", 0),
            semantic=similarity_scores.get("semantic_score", 0),
            composite=similarity_scores.get("composite_score", 0),
        )

        raw = await self._chat_json(_SYSTEM, user)
        if not raw:
            raise ValueError("LLM returned empty response")
        return self._process(raw)

    def _process(self, raw: dict) -> dict:
        _dim_max = {
            "JD Match": 25,
            "Education": 10,
            "Technical Skills": 15,
            "Project Quality": 10,
            "Experience": 15,
            "GitHub Activity": 15,
            "LinkedIn Presence": 10,
        }
        total = 0.0
        for dim in raw.get("dimension_scores", []):
            cap = _dim_max.get(dim.get("dimension", ""), 15)
            ws = max(0.0, min(float(dim.get("weighted_score") or 0), float(cap)))
            dim["weighted_score"] = round(ws, 2)
            total += ws

        raw["total_score"] = round(min(100.0, max(0.0, total)), 2)

        raw["blocker_count"] = len([
            g for g in raw.get("missing_requirements", [])
            if g.get("severity") == "blocker"
        ])
        raw.setdefault("suggested_questions", [])
        raw.setdefault("red_flags", [])
        raw.setdefault("missing_requirements", [])
        raw.setdefault("confidence", "medium")
        raw.setdefault("confidence_reason", "")

        print(f"[INFO] Scored: {raw.get('full_name','?')} → {raw['total_score']}/100")
        return raw

    def _fallback(self, candidate: dict, candidate_id: str, error: str) -> dict:
        return {
            "candidate_id": candidate_id,
            "full_name": candidate.get("full_name", "Unknown"),
            "email": candidate.get("email", ""),
            "total_score": 0.0,
            "blocker_count": 0,
            "dimension_scores": [],
            "missing_requirements": [],
            "red_flags": [f"Evaluation error: {error[:200]}"],
            "confidence": "low",
            "confidence_reason": f"Evaluation failed: {error[:100]}",
            "suggested_questions": [],
            "role_level": self.role_level,
            "error": error,
        }
