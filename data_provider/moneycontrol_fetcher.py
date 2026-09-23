# -*- coding: utf-8 -*-
"""Moneycontrol market-news adapter used for Indian-market context."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MONEYCONTROL_MARKET_NEWS = "https://www.moneycontrol.com/news/tags/market-news.html/news/"


class MoneycontrolFetcher:
    name = "MoneycontrolFetcher"

    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout

    def get_market_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        response = requests.get(
            MONEYCONTROL_MARKET_NEWS,
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/153.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results: List[Dict[str, Any]] = []
        seen = set()

        for anchor in soup.select("a[href]"):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            href = str(anchor.get("href") or "").strip()
            if len(title) < 30 or "moneycontrol.com" not in href:
                continue
            key = (title, href)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "title": title,
                    "url": href,
                    "source": "Moneycontrol",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if len(results) >= max(1, int(limit)):
                break

        return results


def get_moneycontrol_market_news(limit: int = 10) -> List[Dict[str, Any]]:
    """Convenience wrapper for local/offline DSA consumers."""
    try:
        return MoneycontrolFetcher().get_market_news(limit=limit)
    except Exception as exc:
        logger.warning("[Moneycontrol] market news unavailable: %s", exc)
        return []
