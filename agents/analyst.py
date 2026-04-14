"""
Analyst Agent — Ollama local model (fast extraction, zero API cost).
Extracts structured resume data including education GPA/percentage,
project techstacks, certifications, and resolves embedded hyperlinks
(e.g. the word 'GitHub' that hides a URL).
"""
from __future__ import annotations

import json
import re
from typing import Any

from config.settings import get_settings
from .base_agent import BaseAgent

settings = get_settings()

_SYSTEM = """\
Extract structured info from the resume. Return ONLY valid JSON, no markdown.

Check "--- EXTRACTED LINKS ---" section first for GitHub/LinkedIn URLs.

{"full_name": "string or null", "email": "string or null", "phone": "string or null", "linkedin_url": "full URL or null", "github_url": "full URL or null", "skills": ["skill1", "skill2"], "total_experience_years": 0.0, "education": [{"degree": "e.g. B.Tech CS", "institution": "name", "year": "2024", "gpa": "8.2", "percentage": "85.5"}], "certifications": ["cert name"], "projects": [{"name": "name", "description": "what it does", "techstack": ["Python", "React"]}], "work_history": [{"company": "", "title": "", "start_date": "Mon YYYY", "end_date": "Mon YYYY or Present", "is_current": false, "description": "brief"}], "summary": "one line summary"}

Rules: Normalize skills (JS→JavaScript, k8s→Kubernetes). Deduplicate. Return null for missing fields.
"""


def _pre_extract_urls(raw_text: str) -> tuple[str | None, str | None]:
    """
    Pre-scan the EXTRACTED LINKS section for GitHub and LinkedIn URLs.
    Resumes often have 'GitHub' or 'LinkedIn' as clickable text where
    the actual URL is only accessible via hyperlink metadata.
    The PDF/DOCX parser appends these as '--- EXTRACTED LINKS ---\\nURL1\\nURL2'.
    Returns (github_url, linkedin_url) or (None, None) if not found.
    """
    github_url = None
    linkedin_url = None

    # Find the extracted links block
    links_block_match = re.search(
        r"---\s*EXTRACTED LINKS\s*---\s*([\s\S]+?)(?:\n\n|\Z)",
        raw_text,
        re.IGNORECASE,
    )
    if links_block_match:
        block = links_block_match.group(1)
        for line in block.splitlines():
            url = line.strip()
            if not url:
                continue
            if not github_url and re.search(r"github\.com/[A-Za-z0-9\-_]+", url, re.IGNORECASE):
                user = re.search(r"github\.com/([A-Za-z0-9\-_]+)", url, re.IGNORECASE)
                if user and user.group(1).lower() not in ("login", "signup", "features", "about"):
                    github_url = f"https://github.com/{user.group(1)}"
            if not linkedin_url and re.search(r"linkedin\.com/in/[A-Za-z0-9\-_%]+", url, re.IGNORECASE):
                slug = re.search(r"linkedin\.com/in/([A-Za-z0-9\-_%]+)", url, re.IGNORECASE)
                if slug and slug.group(1).lower() not in ("feed", "jobs", "messaging"):
                    linkedin_url = f"https://www.linkedin.com/in/{slug.group(1)}"

    return github_url, linkedin_url


class AnalystAgent(BaseAgent):
    def __init__(self):
        # Use the same model for extraction (single model = less RAM on 8GB system)
        super().__init__(model_name=settings.ollama_model_analyst, temperature=0.0)

    async def extract_and_normalise(
        self,
        raw_text: str,
        github_raw: dict | None = None,
        linkedin_raw: dict | None = None,
        candidate_id: str = "",
    ) -> dict[str, Any]:
        # Step 1: Pre-extract hidden hyperlink URLs from extracted links block
        pre_github, pre_linkedin = _pre_extract_urls(raw_text)

        context = f"RESUME TEXT:\n{raw_text[:3000]}"
        if github_raw:
            context += f"\n\nGITHUB DATA:\n{json.dumps(github_raw, default=str)[:300]}"
        if linkedin_raw:
            context += f"\n\nLINKEDIN DATA:\n{json.dumps(linkedin_raw, default=str)[:300]}"

        try:
            result = await self._chat_json(_SYSTEM, context)
            if isinstance(result, dict) and result:
                # Step 2: Override with pre-extracted URLs if LLM missed them
                if pre_github and not result.get("github_url"):
                    result["github_url"] = pre_github
                    print(f"[INFO] Analyst: injected github_url from embedded link: {pre_github}")
                if pre_linkedin and not result.get("linkedin_url"):
                    result["linkedin_url"] = pre_linkedin
                    print(f"[INFO] Analyst: injected linkedin_url from embedded link: {pre_linkedin}")

                print(
                    f"[INFO] Analyst: {candidate_id} → "
                    f"{len(result.get('skills', []))} skills | "
                    f"github={bool(result.get('github_url'))} | "
                    f"linkedin={bool(result.get('linkedin_url'))}"
                )
                return result
        except Exception as e:
            print(f"[WARN] Analyst extraction failed for {candidate_id}: {e}")

        # Fallback: return at least the pre-extracted URLs
        fallback: dict[str, Any] = {}
        if pre_github:
            fallback["github_url"] = pre_github
        if pre_linkedin:
            fallback["linkedin_url"] = pre_linkedin
        return fallback

    async def normalise_github(self, github_raw: dict) -> dict:
        return github_raw or {}

    async def normalise_linkedin(self, linkedin_raw: dict) -> dict:
        if not linkedin_raw:
            return {}
        if not linkedin_raw.get("current_title") and linkedin_raw.get("headline"):
            h = linkedin_raw["headline"]
            linkedin_raw["current_title"] = h.split(" | ")[0].split(" at ")[0].strip()
        return linkedin_raw
