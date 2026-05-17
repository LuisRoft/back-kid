"""Tavily Search API client — used by the agent's `web_search` tool.

Only the agent layer calls this. The map never hits Tavily.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"


class TavilyError(RuntimeError):
    pass


async def search(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = True,
    topic: str = "general",
) -> dict[str, Any]:
    """Run a Tavily search.

    Returns the raw Tavily response dict (`answer`, `results`, ...) or raises
    TavilyError if the API key is missing or the upstream call fails.
    """
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        raise TavilyError("TAVILY_API_KEY is not configured")

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": include_answer,
        "topic": topic,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(TAVILY_ENDPOINT, json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TavilyError(
                f"Tavily upstream error {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise TavilyError(f"Tavily transport error: {exc}") from exc

    return r.json()
