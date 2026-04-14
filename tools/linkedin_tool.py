"""
LinkedIn enrichment tool.
Strategy (in order):
  1. Proxycurl API (if PROXYCURL_API_KEY set) — accurate, paid
  2. LinkedIn oEmbed API — free, returns name + headline for public profiles
  3. httpx scrape of public profile page — best-effort meta tag extraction
  4. Return empty if all fail (scored 0 by evaluator — correct behaviour)
"""
from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

_PROXYCURL_ENDPOINT = "https://nubela.co/proxycurl/api/v2/linkedin"


def _normalise_url(url: str) -> str:
    """Ensure URL is a full linkedin.com/in/... URL."""
    if not url:
        return ""
    url = url.strip().rstrip("/")
    if url.startswith("http"):
        return url
    if "linkedin.com" in url:
        return "https://" + url.lstrip("/")
    # Bare slug like "johndoe"
    return f"https://www.linkedin.com/in/{url}"


def _extract_slug(url: str) -> str:
    m = re.search(r"linkedin\.com/in/([A-Za-z0-9\-_%]+)", url, re.IGNORECASE)
    return m.group(1) if m else ""


# ── Proxycurl (paid, accurate) ────────────────────────────────────────────────

async def _proxycurl_fetch(linkedin_url: str) -> dict | None:
    if not settings.proxycurl_api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _PROXYCURL_ENDPOINT,
                params={"url": linkedin_url, "use_cache": "if-present"},
                headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"[WARN] Proxycurl: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"[WARN] Proxycurl failed: {e}")
        return None


def _parse_proxycurl(data: dict, url: str) -> dict:
    """Parse Proxycurl response into our schema."""
    import datetime
    experiences = data.get("experiences") or []
    total_months = 0
    for exp in experiences:
        start = exp.get("starts_at") or {}
        end = exp.get("ends_at")
        if start.get("year"):
            sy, sm = start.get("year", 2000), start.get("month", 1)
            if end and end.get("year"):
                ey, em = end["year"], end.get("month", 1)
            else:
                now = datetime.datetime.utcnow()
                ey, em = now.year, now.month
            total_months += max(0, (ey - sy) * 12 + (em - sm))

    return {
        "profile_url": url,
        "exists": True,
        "source": "proxycurl",
        "headline": data.get("headline") or "",
        "current_title": data.get("occupation") or "",
        "location": data.get("city") or data.get("country_full_name") or "",
        "tenure_years": round(total_months / 12, 1),
        "connections": data.get("connections") or 0,
        "summary": (data.get("summary") or "")[:400],
    }


# ── oEmbed (free, limited but public) ────────────────────────────────────────

async def _oembed_fetch(linkedin_url: str) -> dict | None:
    """
    LinkedIn oEmbed returns basic public info without auth.
    Returns title (usually "Name - Title at Company | LinkedIn").
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                "https://www.linkedin.com/oembed",
                params={"url": linkedin_url, "format": "json"},
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[WARN] oEmbed fetch failed: {e}")
    return None


def _parse_oembed(data: dict, url: str) -> dict:
    """
    oEmbed title format: "Name - Title at Company | LinkedIn"
    or just "Name | LinkedIn"
    """
    title = data.get("title") or ""
    author = data.get("author_name") or ""

    # Extract headline from title: "Name - HEADLINE | LinkedIn"
    headline = ""
    current_title = ""
    if " - " in title:
        parts = title.split(" - ", 1)
        rest = parts[1].split(" | ")[0].strip()
        headline = rest
        # "Senior Engineer at Acme" → title
        if " at " in rest:
            current_title = rest.split(" at ")[0].strip()
        else:
            current_title = rest

    return {
        "profile_url": url,
        "exists": bool(title),
        "source": "oembed",
        "headline": headline or title.replace(" | LinkedIn", ""),
        "current_title": current_title or author,
        "location": "",
        "tenure_years": 0.0,
        "connections": 0,
        "summary": "",
    }


# ── httpx meta scrape (last resort, free) ─────────────────────────────────────

async def _meta_scrape(linkedin_url: str) -> dict | None:
    """
    Scrape Open Graph / meta tags from LinkedIn public profile page.
    Works on truly public profiles without login.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(linkedin_url, headers=headers, timeout=12)
            if resp.status_code not in (200, 999):   # 999 = LinkedIn anti-bot but often has content
                print(f"[WARN] LinkedIn scrape: HTTP {resp.status_code}")
                return None
            html = resp.text

        # Try og:title first
        og_title_m = re.search(r'<meta property="og:title"\s+content="([^"]+)"', html)
        desc_m = re.search(r'<meta name="description"\s+content="([^"]+)"', html)

        title = og_title_m.group(1) if og_title_m else ""
        desc = desc_m.group(1) if desc_m else ""

        if not title and not desc:
            return None

        return {"title": title, "description": desc}
    except Exception as e:
        print(f"[WARN] LinkedIn meta scrape failed: {e}")
        return None


def _parse_meta(data: dict, url: str) -> dict:
    title = data.get("title", "")
    desc = data.get("description", "")

    headline = ""
    current_title = ""
    if " | " in title:
        headline = title.split(" | ")[0].strip()
    if " at " in headline:
        current_title = headline.split(" at ")[0].strip()

    return {
        "profile_url": url,
        "exists": bool(headline or title),
        "source": "meta_scrape",
        "headline": headline or title,
        "current_title": current_title,
        "location": "",
        "tenure_years": 0.0,
        "connections": 0,
        "summary": desc[:300],
    }


# ── Public entry point ────────────────────────────────────────────────────────

async def fetch_linkedin_profile(linkedin_url: str) -> dict:
    """
    Fetch LinkedIn profile. Tries 3 methods in order of quality.
    Always returns a dict — never raises.
    """
    if not linkedin_url:
        return {}

    url = _normalise_url(linkedin_url)
    slug = _extract_slug(url)

    if not slug:
        print(f"[WARN] LinkedIn: could not extract slug from '{linkedin_url}'")
        return {}

    print(f"[INFO] Fetching LinkedIn profile: {url}")

    # 1. Proxycurl (best quality, paid)
    if settings.proxycurl_api_key:
        data = await _proxycurl_fetch(url)
        if data:
            result = _parse_proxycurl(data, url)
            print(f"[INFO] LinkedIn (Proxycurl): {result.get('current_title')} | tenure={result.get('tenure_years')}yr")
            return result

    # 2. oEmbed (free, public profiles only, gives name + headline)
    data = await _oembed_fetch(url)
    if data and data.get("title"):
        result = _parse_oembed(data, url)
        print(f"[INFO] LinkedIn (oEmbed): headline='{result.get('headline')}'")
        return result

    # 3. Meta tag scrape (last resort)
    data = await _meta_scrape(url)
    if data:
        result = _parse_meta(data, url)
        print(f"[INFO] LinkedIn (meta scrape): headline='{result.get('headline')}'")
        return result

    print(f"[INFO] LinkedIn: no data found for {url} (profile may be private or login-walled)")
    return {
        "profile_url": url,
        "exists": False,
        "source": "none",
        "headline": "",
        "current_title": "",
        "location": "",
        "tenure_years": 0.0,
        "connections": 0,
        "summary": "",
    }
