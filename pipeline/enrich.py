"""
Pipeline Node 2 — Enrich
For each parsed resume:
  1. Fetch GitHub profile
  2. Fetch LinkedIn profile
  3. Run Analyst LLM for structured extraction
  4. Merge all into enriched_profiles
"""
from __future__ import annotations

import asyncio
import json

import structlog

from agents import AnalystAgent
from tools.cache import cached_github, set_cached_github, cached_linkedin, set_cached_linkedin
from tools.github_tool import fetch_github_profile
from tools.linkedin_tool import fetch_linkedin_profile

log = structlog.get_logger(__name__)


async def _enrich_one(resume: dict, analyst: AnalystAgent, jd: dict) -> dict:
    candidate_id = resume.get("candidate_id", "")
    name = resume.get("full_name") or candidate_id
    raw_text = resume.get("raw_text", "")

    # Pre-extract hidden hyperlink URLs from PDF/DOCX link metadata block
    # (handles "GitHub" / "LinkedIn" text with embedded URLs)
    from agents.analyst import _pre_extract_urls
    pre_github, pre_linkedin = _pre_extract_urls(raw_text)

    github_url = (resume.get("github_url") or pre_github or "").strip()
    linkedin_url = (resume.get("linkedin_url") or pre_linkedin or "").strip()

    # Language hints from JD (improves GitHub language match scoring)
    jd_skills = jd.get("required_skills", []) + jd.get("preferred_skills", [])

    print(f"\n[ENRICH] {name}")
    print(f"  GitHub URL  : {github_url or '(none found in resume)'}")
    print(f"  LinkedIn URL: {linkedin_url or '(none found in resume)'}")

    # ── 1. GitHub ──────────────────────────────────────────────────────────────
    github_data = {}
    if github_url:
        from urllib.parse import urlparse
        cache_key = github_url.rstrip("/").split("/")[-1].lower()
        github_data = cached_github(cache_key) or {}
        if not github_data:
            github_data = await fetch_github_profile(github_url, jd_skills)
            if github_data:
                set_cached_github(cache_key, github_data)
    else:
        print(f"  [SKIP] GitHub enrichment — no URL")

    # ── 2. LinkedIn ────────────────────────────────────────────────────────────
    linkedin_data = {}
    if linkedin_url:
        linkedin_data = cached_linkedin(linkedin_url) or {}
        if not linkedin_data:
            linkedin_data = await fetch_linkedin_profile(linkedin_url)
            if linkedin_data:
                set_cached_linkedin(linkedin_url, linkedin_data)
    else:
        print(f"  [SKIP] LinkedIn enrichment — no URL")

    # ── 3. Analyst LLM extraction ──────────────────────────────────────────────
    llm_extracted = await analyst.extract_and_normalise(
        raw_text=raw_text,
        github_raw=github_data,
        linkedin_raw=linkedin_data,
        candidate_id=candidate_id,
    )

    # ── 4. Merge (LLM result overrides heuristic parse where available) ────────
    merged = {**resume}
    if llm_extracted:
        for field in [
            "full_name", "email", "phone", "linkedin_url", "github_url",
            "skills", "total_experience_years", "education",
            "certifications", "projects", "work_history", "summary",
        ]:
            val = llm_extracted.get(field)
            if val not in (None, "", [], {}):
                merged[field] = val

        # If LLM found a GitHub/LinkedIn URL the heuristic missed, try to enrich
        if not github_url and llm_extracted.get("github_url"):
            print(f"  [RETRY] LLM found GitHub URL: {llm_extracted['github_url']}")
            github_data = await fetch_github_profile(llm_extracted["github_url"], jd_skills)
            merged["github_url"] = llm_extracted["github_url"]

        if not linkedin_url and llm_extracted.get("linkedin_url"):
            print(f"  [RETRY] LLM found LinkedIn URL: {llm_extracted['linkedin_url']}")
            linkedin_data = await fetch_linkedin_profile(llm_extracted["linkedin_url"])
            merged["linkedin_url"] = llm_extracted["linkedin_url"]

    merged["github"] = github_data
    merged["linkedin"] = linkedin_data

    print(
        f"  [DONE] skills={len(merged.get('skills', []))} "
        f"exp={merged.get('total_experience_years', 0)}yr "
        f"github={'✓' if github_data.get('exists') else '✗'} "
        f"linkedin={'✓' if linkedin_data.get('exists') else '✗'}"
    )
    return merged


async def enrich_node(state: dict) -> dict:
    parsed_resumes: list[dict] = state.get("parsed_resumes", [])
    jd: dict = state.get("jd", {})

    analyst = AnalystAgent()

    print(f"\n{'='*50}")
    print(f"ENRICH NODE: {len(parsed_resumes)} candidates")
    print(f"{'='*50}")

    # Limit concurrency to 1 — local Ollama model handles one request at a time
    semaphore = asyncio.Semaphore(1)

    async def _bounded(r: dict) -> dict:
        async with semaphore:
            return await _enrich_one(r, analyst, jd)

    tasks = [_bounded(r) for r in parsed_resumes]
    enriched = await asyncio.gather(*tasks, return_exceptions=False)

    print(f"\n[ENRICH] Complete: {len(enriched)} profiles enriched")
    return {**state, "enriched_profiles": list(enriched)}
