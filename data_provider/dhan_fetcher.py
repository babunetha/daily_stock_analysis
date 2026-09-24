# -*- coding: utf-8 -*-
"""DhanHQ v2 market-data adapter for India/NSE."""
from __future__ import annotations
import os, time
from typing import Any, Dict, Optional
import pandas as pd
import requests
from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS

DHAN_API_BASE = "https://api.dhan.co/v2"
DHAN_INSTRUMENT_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()

def is_dhan_configured() -> bool:
    return bool(_env("DHAN_CLIENT_ID") and _env("DHAN_ACCESS_TOKEN"))

def normalize_dhan_symbol(symbol: str) -> str:
    raw = (symbol or "").strip().upper()
    if raw.startswith("NSE:"): raw = raw[4:]
    if raw.endswith(".NS"): raw = raw[:-3]
    return raw

class DhanFetcher(BaseFetcher):
    name = "DhanFetcher"
    priority = -5
    allow_empty_daily_data = False

    def __init__(self, client_id: Optional[str] = None, access_token: Optional[str] = None, timeout_seconds: float = 15.0) -> None:
        self.client_id = (client_id or _env("DHAN_CLIENT_ID")).strip()
        self.access_token = (access_token or _env("DHAN_ACCESS_TOKEN")).strip()
        self.timeout_seconds = float(timeout_seconds)
        self._instrument_cache: Optional[pd.DataFrame] = None
        self._instrument_cache_ts = 0.0

    @staticmethod
    def is_available_for_request(capability: str = "") -> bool:
        return is_dhan_configured()

    def _headers(self) -> Dict[str, str]:
        if not self.access_token: raise DataFetchError("Dhan access token is not configured")
        return {"Accept":"application/json","Content-Type":"application/json","access-token":self.access_token,"client-id":self.client_id}

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(f"{DHAN_API_BASE}{path}", headers=self._headers(), json=payload, timeout=self.timeout_seconds)
        if r.status_code >= 400: raise DataFetchError(f"Dhan API {path} HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        if isinstance(data, dict) and str(data.get("status","")).lower() == "failure": raise DataFetchError(f"Dhan API {path} failed: {data}")
        return data

    def _load_instruments(self) -> pd.DataFrame:
        if self._instrument_cache is not None and time.time() - self._instrument_cache_ts < 86400: return self._instrument_cache
        r = requests.get(DHAN_INSTRUMENT_MASTER_URL, timeout=max(self.timeout_seconds,30.0))
        r.raise_for_status()
        from io import BytesIO
        self._instrument_cache = pd.read_csv(BytesIO(r.content), low_memory=False)
        self._instrument_cache_ts = time.time()
        return self._instrument_cache

    def resolve_security_id(self, stock_code: str) -> str:
        symbol = normalize_dhan_symbol(stock_code)
        frame = self._load_instruments()
        exchange_col = next((c for c in ("EXCH_ID","SEM_EXM_EXCH_ID") if c in frame.columns), None)
        segment_col = next((c for c in ("SEGMENT","SEM_SEGMENT") if c in frame.columns), None)
        candidates = frame
        if exchange_col: candidates = candidates[candidates[exchange_col].astype(str).str.upper().eq("NSE")]
        if segment_col: candidates = candidates[candidates[segment_col].astype(str).str.upper().eq("E")]
        symbol_columns = ("SEM_TRADING_SYMBOL","SM_SYMBOL_NAME","SYMBOL_NAME","SEM_CUSTOM_SYMBOL","DISPLAY_NAME")
        security_columns = ("SECURITY_ID","SEM_SMST_SECURITY_ID","securityId")
        for column in symbol_columns:
            if column not in candidates.columns: continue
            match = candidates[candidates[column].astype(str).str.upper().eq(symbol)]
            if match.empty: continue
            for sec in security_columns:
                if sec in match.columns:
                    value = str(match.iloc[0][sec]).strip()
                    if value and value.lower() != "nan": return value
        raise DataFetchError(f"Dhan securityId not found for NSE symbol {symbol}")

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        security_id = self.resolve_security_id(stock_code)
        data = self._post("/charts/historical", {"securityId":security_id,"exchangeSegment":"NSE_EQ","instrument":"EQUITY","expiryCode":0,"oi":False,"fromDate":start_date,"toDate":end_date})
        timestamps = data.get("timestamp",[])
        rows=[]
        for i, ts in enumerate(timestamps):
            rows.append({"timestamp":ts, **{k:(data.get(k,[])[i] if i < len(data.get(k,[])) else None) for k in ("open","high","low","close","volume")}})
        if not rows: raise DataFetchError(f"Dhan returned no historical rows for {stock_code}")
        return pd.DataFrame(rows)

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        out=pd.DataFrame(index=df.index)
        out["date"]=pd.to_datetime(pd.to_numeric(df["timestamp"],errors="coerce"),unit="s",errors="coerce")
        for c in ("open","high","low","close","volume"): out[c]=pd.to_numeric(df.get(c),errors="coerce")
        out["amount"]=0.0
        out["pct_chg"]=out["close"].pct_change()*100.0
        return out[STANDARD_COLUMNS].dropna(subset=["date","close","volume"])

    def get_ltp(self, stock_code: str) -> float:
        sid=self.resolve_security_id(stock_code)
        data=self._post("/marketfeed/ltp",{"NSE_EQ":[int(sid)]})
        try: return float(data["data"]["NSE_EQ"][str(sid)]["last_price"])
        except (KeyError,TypeError,ValueError) as exc: raise DataFetchError(f"Invalid Dhan LTP response for {stock_code}: {data}") from exc

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        symbol=normalize_dhan_symbol(stock_code); frame=self._load_instruments()
        for c in ("SM_SYMBOL_NAME","SYMBOL_NAME","SEM_CUSTOM_SYMBOL","DISPLAY_NAME"):
            if c in frame.columns:
                match=frame[frame[c].astype(str).str.upper().eq(symbol)]
                if not match.empty: return str(match.iloc[0][c])
        return None
