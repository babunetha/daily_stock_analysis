# -*- coding: utf-8 -*-
"""NSE India market-data adapter.

Uses the public NSE web/API surface for quotes and index/market snapshots.
Historical equity endpoints are attempted but may be unavailable; the normal
DSA provider chain can fall back to another historical source in that case.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import requests

try:
    # Avoid importing data_provider.base while it is still initializing. The NSE
    # adapter is loaded lazily by DataFetcherManager, so a lightweight fallback
    # keeps module import acyclic while preserving the adapter interface.
    from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
except ImportError:  # pragma: no cover - only hit during circular initialization
    class BaseFetcher:
        pass

    class DataFetchError(Exception):
        pass

    STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote, safe_float, safe_int

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
NSE_HOME = f"{NSE_BASE}/market-data/live-equity-market"


class NSEFetcher(BaseFetcher):
    name = "NSEFetcher"
    priority = 0

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/153.0 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": NSE_HOME,
                "Connection": "keep-alive",
            }
        )
        self._bootstrapped = False

    def is_available(self) -> bool:
        return True

    def _bootstrap(self) -> None:
        if self._bootstrapped:
            return
        response = self._session.get(NSE_HOME, timeout=self.timeout)
        response.raise_for_status()
        self._bootstrapped = True

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            self._bootstrap()
            response = self._session.get(
                f"{NSE_BASE}{path}",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise DataFetchError(f"NSE returned unexpected payload for {path}")
            return payload
        except Exception as exc:
            self._bootstrapped = False
            raise DataFetchError(f"NSE request failed: {path}: {exc}") from exc

    @staticmethod
    def _symbol(stock_code: str) -> str:
        code = (stock_code or "").strip().upper()
        code = re.sub(r"^NSE[:.]?", "", code)
        if code.endswith(".NS"):
            code = code[:-3]
        return code

    @staticmethod
    def _row_from_quote(data: Dict[str, Any], symbol: str) -> UnifiedRealtimeQuote:
        price_info = data.get("priceInfo") or {}
        metadata = data.get("metadata") or {}
        security_info = data.get("securityInfo") or {}
        trade_info = data.get("preOpenMarket") or {}

        last_price = safe_float(price_info.get("lastPrice"))
        previous_close = safe_float(price_info.get("previousClose"))
        change = safe_float(price_info.get("change"))
        change_pct = safe_float(price_info.get("pChange"))
        open_price = safe_float(price_info.get("open"))
        high = safe_float(price_info.get("intraDayHighLow", {}).get("max"))
        low = safe_float(price_info.get("intraDayHighLow", {}).get("min"))
        volume = safe_int(trade_info.get("totalTradedVolume") or data.get("totalTradedVolume"))
        amount = safe_float(trade_info.get("totalTradedValue") or data.get("totalTradedValue"))
        if amount is not None and amount < 1000000:
            # NSE may return value in lakhs/crores in some widgets; preserve the
            # raw provider value rather than inventing a conversion.
            amount = amount

        if high is None:
            high = safe_float(price_info.get("intraDayHighLow", {}).get("max"))
        if low is None:
            low = safe_float(price_info.get("intraDayHighLow", {}).get("min"))

        amplitude = None
        if high is not None and low is not None and previous_close:
            amplitude = ((high - low) / previous_close) * 100

        name = (
            str(metadata.get("companyName") or metadata.get("symbol") or symbol).strip()
        )

        missing = [
            key
            for key, value in {
                "price": last_price,
                "previous_close": previous_close,
                "volume": volume,
            }.items()
            if value is None
        ]

        return UnifiedRealtimeQuote(
            code=symbol,
            name=name,
            source=RealtimeSource.NSE,
            market="in",
            currency="INR",
            data_quality="partial" if missing else "ok",
            missing_fields=missing or None,
            price=last_price,
            change_pct=change_pct,
            change_amount=change,
            volume=volume,
            amount=amount,
            amplitude=amplitude,
            open_price=open_price,
            high=high,
            low=low,
            pre_close=previous_close,
        )

    def get_realtime_quote(self, stock_code: str, source: str = "nse") -> Optional[UnifiedRealtimeQuote]:
        symbol = self._symbol(stock_code)
        if not symbol or symbol in {"NIFTY", "BANKNIFTY"}:
            return None
        payload = self._get_json("/api/quote-equity", {"symbol": symbol})
        data = payload.get("priceInfo") and payload or None
        if not data:
            return None
        return self._row_from_quote(data, symbol)

    def get_main_indices(self, region: str = "in"):
        if region != "in":
            return None
        payload = self._get_json("/api/allIndices")
        rows = payload.get("data") or []
        wanted = {
            "NIFTY 50": "NIFTY50",
            "NIFTY BANK": "BANKNIFTY",
            "NIFTY IT": "NIFTYIT",
            "NIFTY MIDCAP 50": "NIFTYMIDCAP50",
        }
        results = []
        for row in rows:
            name = str(row.get("index") or "").strip()
            if name not in wanted:
                continue
            results.append(
                {
                    "code": wanted[name],
                    "name": name,
                    "current": safe_float(row.get("last")),
                    "change": safe_float(row.get("variation")),
                    "change_pct": safe_float(row.get("percentChange")),
                    "open": safe_float(row.get("open")),
                    "high": safe_float(row.get("dayHigh")),
                    "low": safe_float(row.get("dayLow")),
                    "prev_close": safe_float(row.get("previousClose")),
                    "volume": safe_int(row.get("volume")),
                    "amount": safe_float(row.get("turnover")),
                    "amplitude": safe_float(row.get("perChange")),
                }
            )
        return results or None

    def get_market_stats(self):
        payload = self._get_json("/api/equity-stockIndices", {"index": "NIFTY 500"})
        rows = payload.get("data") or []
        up = down = flat = 0
        for row in rows:
            pct = safe_float(row.get("pChange"))
            if pct is None:
                continue
            if pct > 0:
                up += 1
            elif pct < 0:
                down += 1
            else:
                flat += 1
        return {
            "up_count": up,
            "down_count": down,
            "flat_count": flat,
            "limit_up_count": None,
            "limit_down_count": None,
            "total_amount": None,
        }

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        symbol = self._symbol(stock_code)
        # NSE removed/changed this endpoint in 2026 in some environments.
        # Keep the attempt explicit so the provider chain can fall back cleanly.
        payload = self._get_json(
            "/api/historical/cm/equity",
            {
                "symbol": symbol,
                "series": '["EQ"]',
                "from": datetime.strptime(start_date, "%Y-%m-%d").strftime("%d-%m-%Y"),
                "to": datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%m-%Y"),
            },
        )
        return pd.DataFrame(payload.get("data") or [])

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)
        out = df.copy()
        rename = {
            "CH_TIMESTAMP": "date",
            "mTIMESTAMP": "date",
            "OPEN": "open",
            "HIGH": "high",
            "LOW": "low",
            "CLOSE": "close",
            "VOLUME": "volume",
            "TOTTRDQTY": "volume",
            "TOTALTRADERS": "amount",
            "TOTTRDVAL": "amount",
            "PERCENTCHANGE": "pct_chg",
        }
        out = out.rename(columns=rename)
        for col in STANDARD_COLUMNS:
            if col not in out.columns:
                out[col] = None
        return out[STANDARD_COLUMNS]
