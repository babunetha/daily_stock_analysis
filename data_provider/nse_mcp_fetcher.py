# -*- coding: utf-8 -*-
"""
NSE India MCP data provider.

Uses the official NSE Market Data MCP endpoints through the Python MCP
streamable-HTTP client. This provider intentionally does not use Yahoo Finance.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

import pandas as pd

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS

logger = logging.getLogger(__name__)

NSE_BHAVCOPY_MCP_URL = "https://mcp.nseindia.in/bhavcopy/cm/mcp"
NSE_CM_MARKET_MCP_URL = "https://mcp.nseindia.in/cmmkt/mcp"

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9&-]{0,19}$")


def normalize_nse_symbol(value: str) -> str:
    raw = (value or "").strip().upper()
    for prefix in ("NSE:", "BSE:"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    if raw.endswith(".NS"):
        raw = raw[:-3]
    return raw


def is_india_stock_symbol(value: str) -> bool:
    raw = (value or "").strip().upper()
    if raw.startswith(("NSE:", "BSE:")) or raw.endswith(".NS"):
        return True
    # The India project uses NSE symbols as its canonical stock identifiers.
    return bool(_SYMBOL_RE.fullmatch(raw)) and not raw.startswith((".", "$", "^"))


def _json_from_result(result: Any) -> Any:
    content = getattr(result, "content", None) or []
    texts = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            texts.append(text)
    if not texts:
        return None
    payload = "\n".join(texts).strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        # Some MCP servers return a JSON string wrapped in text.
        return payload


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("data", "results", "rows", "history", "quotes", "records", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]

    # Some responses nest data one level deeper.
    for value in payload.values():
        if isinstance(value, dict):
            rows = _rows_from_payload(value)
            if rows:
                return rows
    return []


def _property_names(tool: Any) -> set[str]:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return set(props) if isinstance(props, dict) else set()


def _build_tool_arguments(tool: Any, symbol: str, start_date: str, end_date: str) -> Dict[str, Any]:
    props = _property_names(tool)
    args: Dict[str, Any] = {}

    symbol_keys = {"symbol", "stock_symbol", "stock", "ticker", "code", "symbol_code", "security"}
    start_keys = {"start_date", "from_date", "from", "start", "begin_date"}
    end_keys = {"end_date", "to_date", "to", "end", "finish_date"}
    date_keys = {"date", "trade_date", "trading_date"}

    for key in props:
        lowered = key.lower()
        if lowered in symbol_keys or "symbol" in lowered or lowered.endswith("_ticker"):
            args[key] = symbol
        elif lowered in start_keys or "start" in lowered:
            args[key] = start_date
        elif lowered in end_keys or lowered.startswith("end_"):
            args[key] = end_date
        elif lowered in date_keys:
            args[key] = end_date

    return args


class NSEMCPFetcher(BaseFetcher):
    """Official NSE India MCP-backed daily data fetcher."""

    name = "NSEMCPFetcher"
    priority = -10
    allow_empty_daily_data = False

    def __init__(
        self,
        bhavcopy_url: str = NSE_BHAVCOPY_MCP_URL,
        market_url: str = NSE_CM_MARKET_MCP_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.bhavcopy_url = bhavcopy_url
        self.market_url = market_url
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def is_available_for_request(capability: str = "") -> bool:
        # Availability is determined by the MCP endpoint when the request runs.
        return True

    async def _call_tool_async(self, url: str, tool_name: str, **hints: Any) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise DataFetchError(
                "NSEMCPFetcher requires the 'mcp' package. Install project requirements first."
            ) from exc

        async with streamable_http_client(url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools = getattr(tools_result, "tools", []) or []
                tool = next((t for t in tools if getattr(t, "name", "") == tool_name), None)
                if tool is None:
                    available = ", ".join(getattr(t, "name", "") for t in tools)
                    raise DataFetchError(
                        f"NSE MCP tool '{tool_name}' not found. Available tools: {available}"
                    )

                args = _build_tool_arguments(
                    tool,
                    hints.get("symbol", ""),
                    hints.get("start_date", ""),
                    hints.get("end_date", ""),
                )
                # Pass through explicitly known hints only when the server schema
                # exposes the corresponding property.
                result = await session.call_tool(tool_name, arguments=args)
                return _json_from_result(result)

    def _call_tool(self, url: str, tool_name: str, **hints: Any) -> Any:
        return asyncio.run(self._call_tool_async(url, tool_name, **hints))

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        symbol = normalize_nse_symbol(stock_code)
        payload = self._call_tool(
            self.bhavcopy_url,
            "get_stock_history",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        rows = _rows_from_payload(payload)
        if not rows:
            raise DataFetchError(f"NSE returned no historical rows for {symbol}")
        return pd.DataFrame(rows)

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)

        aliases = {
            "date": ("date", "Date", "trade_date", "trading_date"),
            "open": ("open", "Open", "OPEN_PRICE", "open_price"),
            "high": ("high", "High", "HIGH_PRICE", "high_price"),
            "low": ("low", "Low", "LOW_PRICE", "low_price"),
            "close": ("close", "Close", "CLOSE_PRICE", "close_price", "ltp"),
            "volume": ("volume", "Volume", "TOTTRDQTY", "total_traded_quantity", "qty"),
            "amount": (
                "amount",
                "Amount",
                "TOTTRDVAL",
                "total_traded_value",
                "turnover",
                "value",
            ),
            "pct_chg": (
                "pct_chg",
                "pctChange",
                "change_pct",
                "percent_change",
                "changePercent",
            ),
        }

        normalized = pd.DataFrame(index=df.index)
        columns_lower = {str(c).strip().lower(): c for c in df.columns}

        for target, candidates in aliases.items():
            source = None
            for candidate in candidates:
                if candidate in df.columns:
                    source = candidate
                    break
                source = columns_lower.get(candidate.lower())
                if source is not None:
                    break
            if source is not None:
                normalized[target] = df[source]

        if "date" not in normalized:
            # Try to find a date-like column before failing.
            for column in df.columns:
                if "date" in str(column).lower():
                    normalized["date"] = df[column]
                    break

        if "pct_chg" not in normalized and {"close", "open"} <= set(normalized.columns):
            normalized["pct_chg"] = (
                pd.to_numeric(normalized["close"], errors="coerce")
                / pd.to_numeric(normalized["open"], errors="coerce")
                - 1.0
            ) * 100.0

        for column in STANDARD_COLUMNS:
            if column not in normalized:
                normalized[column] = 0.0 if column not in {"date"} else pd.NaT

        normalized = normalized[STANDARD_COLUMNS]
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        return normalized.dropna(subset=["date"])

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        symbol = normalize_nse_symbol(stock_code)
        payload = self._call_tool(
            self.bhavcopy_url,
            "nse_lookup_symbol",
            symbol=symbol,
        )
        if isinstance(payload, dict):
            names = payload.get("names") or payload.get("results") or []
            if isinstance(names, list) and names:
                first = names[0]
                if isinstance(first, dict):
                    return first.get("name") or first.get("company_name")
            return payload.get("name") or payload.get("company_name")
        return None
