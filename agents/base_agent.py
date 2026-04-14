"""
Base agent — Ollama only (100% local inference, zero API cost).
Uses Ollama's /api/chat REST endpoint via httpx (already in deps).
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from config.settings import get_settings

settings = get_settings()

# Longer timeout for local inference (7B models can take 30-120s per call)
_OLLAMA_TIMEOUT = httpx.Timeout(300.0, connect=10.0)

# Max retries for transient Ollama errors (OOM, temporary overload)
_MAX_RETRIES = 2
_RETRY_DELAY = 3.0  # seconds between retries


class BaseAgent:
    def __init__(self, model_name: str, temperature: float = 0.1):
        self.model_name = model_name
        self.temperature = temperature

    # ── Ollama (localhost — /api/chat) ──────────────────────────────────────────

    async def _ollama_chat(self, system: str, user: str) -> str:
        """Call Ollama's chat completion endpoint (OpenAI-style messages).
        
        Key sizing: num_ctx is the TOTAL context window (input + output).
        num_predict is the max OUTPUT tokens. num_predict must be < num_ctx
        minus the prompt tokens, otherwise Ollama returns 500.
        """
        url = f"{settings.ollama_base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                # num_predict = max output tokens (JSON responses ~500-800 tokens)
                # With num_ctx=4096, this leaves ~3000 tokens for prompt input
                "num_predict": 1024,
                "num_ctx": settings.ollama_num_ctx,
            },
        }

        last_err = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
                    resp = await client.post(url, json=payload)

                # Surface the actual Ollama error instead of generic HTTP 500
                if resp.status_code != 200:
                    try:
                        err_body = resp.json()
                        err_msg = err_body.get("error", resp.text[:500])
                    except Exception:
                        err_msg = resp.text[:500]
                    
                    # Log the full error for debugging
                    print(f"[ERROR] Ollama HTTP {resp.status_code}: {err_msg}")
                    
                    # Retry on 500 (often transient OOM or model loading issue)
                    if resp.status_code == 500 and attempt < _MAX_RETRIES:
                        print(f"[RETRY] Attempt {attempt + 1}/{_MAX_RETRIES} after {_RETRY_DELAY}s...")
                        await asyncio.sleep(_RETRY_DELAY)
                        continue
                    
                    raise RuntimeError(
                        f"Ollama error (HTTP {resp.status_code}): {err_msg}"
                    )

                data = resp.json()
                # Ollama returns { "message": { "content": "..." }, ... }
                content = data.get("message", {}).get("content", "")
                return content

            except httpx.ConnectError:
                raise  # Don't retry connection errors
            except RuntimeError:
                raise  # Don't retry our own RuntimeErrors (already retried above)
            except Exception as e:
                last_err = e
                if attempt < _MAX_RETRIES:
                    print(f"[RETRY] Attempt {attempt + 1}/{_MAX_RETRIES} for {type(e).__name__}: {e}")
                    await asyncio.sleep(_RETRY_DELAY)
                    continue
                raise

        raise last_err or RuntimeError("Ollama call failed after retries")

    # ── Public interface ───────────────────────────────────────────────────────

    async def _chat_json(self, system: str, user: str) -> dict | list:
        """Call Ollama and return parsed JSON. Raises on failure."""
        try:
            raw = await self._ollama_chat(system, user)
            result = self._parse_json(raw)
            if result:
                return result
            raise ValueError(f"Ollama returned empty/unparseable JSON.\nRaw: {raw[:400]}")
        except httpx.ConnectError:
            raise RuntimeError(
                "Cannot connect to Ollama. Make sure Ollama is running:\n"
                "  1. Install: https://ollama.com/download\n"
                "  2. Pull model: ollama pull mistral:7b-instruct-q4_K_M\n"
                "  3. Start server: ollama serve"
            )
        except Exception as e:
            print(f"[ERROR] Ollama call failed (model={self.model_name}): {e}")
            raise

    # ── JSON parsing ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict | list:
        """Strip markdown fences and parse JSON robustly."""
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        # Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Find first complete JSON block by depth-matching brackets
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            idx = raw.find(start_char)
            if idx == -1:
                continue
            depth = 0
            for i, ch in enumerate(raw[idx:], idx):
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[idx:i+1])
                        except Exception:
                            break

        print(f"[ERROR] JSON parse failed. Raw preview:\n{raw[:500]}")
        return {}
