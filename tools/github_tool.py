"""
GitHub enrichment tool — robust, fast, works without a token.
Strategy:
  - Public REST API for user profile (no auth needed)
  - GraphQL contributions calendar (requires GITHUB_TOKEN)
  - Repo language stats via REST (no auth)
  - Commit count estimated from events API (avoids per-repo rate limiting)
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

_BASE = "https://api.github.com"


def _auth_headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def _extract_username(url: str) -> str | None:
    """Extract GitHub username from URL or bare username."""
    if not url:
        return None
    url = url.strip().rstrip("/")
    # Handle full URLs
    m = re.search(r"github\.com/([A-Za-z0-9\-_]+)", url, re.IGNORECASE)
    if m:
        username = m.group(1)
        # Skip known non-user paths
        if username.lower() not in ("login", "signup", "features", "about", "pricing"):
            return username
    # Bare username (no slashes, no dots)
    if "/" not in url and "." not in url and url:
        return url
    return None


async def _safe_get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> Any:
    """GET with error isolation — never raises."""
    try:
        resp = await client.get(
            url,
            params=params,
            headers=_auth_headers(),
            timeout=10,
        )
        if resp.status_code in (404, 403, 401):
            return None
        if resp.status_code == 202:   # GitHub computing stats, retry once
            await asyncio.sleep(2)
            resp = await client.get(url, params=params, headers=_auth_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[WARN] GitHub GET {url} failed: {e}")
        return None


async def _get_contributions_via_graphql(client: httpx.AsyncClient, username: str) -> tuple[int, int]:
    """
    Returns (total_commits_last_year, streak_days).
    Requires GITHUB_TOKEN. Returns (0, 0) without token.
    """
    if not settings.github_token:
        return 0, 0

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          contributionCalendar {
            weeks {
              contributionDays {
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    try:
        resp = await client.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"login": username}},
            headers=_auth_headers(),
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        collection = (
            data.get("data", {})
            .get("user", {})
            .get("contributionsCollection", {})
        )
        total_commits = collection.get("totalCommitContributions", 0)
        weeks = collection.get("contributionCalendar", {}).get("weeks", [])

        # Flatten days, compute streak (consecutive days with >0 contributions, from end)
        all_days = [
            day["contributionCount"]
            for week in weeks
            for day in week.get("contributionDays", [])
        ]
        streak = 0
        for count in reversed(all_days):
            if count > 0:
                streak += 1
            else:
                break

        return total_commits, streak
    except Exception as e:
        print(f"[WARN] GitHub GraphQL failed for {username}: {e}")
        return 0, 0


async def _estimate_commits_from_events(client: httpx.AsyncClient, username: str) -> int:
    """
    Estimate commits from public events API (no token needed, max ~90 days).
    Counts PushEvent payloads. Fast alternative to per-repo commit scanning.
    """
    try:
        events = await _safe_get(
            client,
            f"{_BASE}/users/{username}/events/public",
            params={"per_page": 100},
        )
        if not isinstance(events, list):
            return 0
        count = 0
        for event in events:
            if event.get("type") == "PushEvent":
                payload = event.get("payload", {})
                count += payload.get("size", len(payload.get("commits", [])))
        return count
    except Exception:
        return 0


async def fetch_github_profile(github_url: str, jd_languages: list[str] | None = None) -> dict:
    """
    Fetch GitHub profile. Works without a token (unauthenticated REST API).
    Token enables GraphQL contributions data (much richer).
    """
    jd_languages = [s.lower() for s in (jd_languages or [])]
    username = _extract_username(github_url)

    if not username:
        print(f"[INFO] GitHub: no username found in '{github_url}'")
        return {}

    print(f"[INFO] Fetching GitHub profile for: {username}")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Basic profile
        user_data = await _safe_get(client, f"{_BASE}/users/{username}")
        if not user_data or not isinstance(user_data, dict):
            print(f"[WARN] GitHub: user '{username}' not found")
            return {"username": username, "exists": False}

        # 2. Repos (first page — fast, no pagination needed for language stats)
        repos_data = await _safe_get(
            client,
            f"{_BASE}/users/{username}/repos",
            params={"per_page": 100, "sort": "pushed"},
        ) or []
        if not isinstance(repos_data, list):
            repos_data = []

        # 3. Language stats (weighted by star count)
        lang_counts: dict[str, int] = {}
        for repo in repos_data:
            lang = repo.get("language")
            if lang:
                weight = repo.get("stargazers_count", 0) + 1
                lang_counts[lang] = lang_counts.get(lang, 0) + weight
        top_languages = sorted(lang_counts, key=lang_counts.get, reverse=True)[:5]  # type: ignore

        # 4. Contributions: GraphQL (with token) or events estimate (without)
        if settings.github_token:
            total_commits, streak = await _get_contributions_via_graphql(client, username)
        else:
            total_commits = await _estimate_commits_from_events(client, username)
            streak = 0  # streak needs GraphQL

        # 5. Total stars
        stars = sum(r.get("stargazers_count", 0) for r in repos_data)

        # 6. JD language match
        jd_match = any(lang.lower() in jd_languages for lang in top_languages)

    result = {
        "username": username,
        "profile_url": f"https://github.com/{username}",
        "exists": True,
        "public_repos": user_data.get("public_repos", 0),
        "followers": user_data.get("followers", 0),
        "total_commits_last_year": total_commits,
        "contribution_streak_days": streak,
        "top_languages": top_languages,
        "stars_total": stars,
        "jd_language_match": jd_match,
        "account_age_years": _account_age(user_data.get("created_at", "")),
        "bio": user_data.get("bio", "") or "",
    }

    print(
        f"[INFO] GitHub fetched: {username} | "
        f"repos={result['public_repos']} commits={total_commits} "
        f"streak={streak} langs={top_languages}"
    )
    return result


def _account_age(created_at: str) -> float:
    """Years since account was created."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return round((datetime.now(timezone.utc) - dt).days / 365.25, 1)
    except Exception:
        return 0.0
