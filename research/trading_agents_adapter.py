# -*- coding: utf-8 -*-
"""Research-only adapter for an external TradingAgents service."""
from __future__ import annotations
import os
from typing import Any, Dict
import requests

class TradingAgentsAdapter:
    def __init__(self,url=None,token=None,timeout_seconds:float=45.0):
        self.url=(url or os.getenv("TRADINGAGENTS_SERVICE_URL") or "").strip().rstrip("/")
        self.token=(token or os.getenv("TRADINGAGENTS_SERVICE_TOKEN") or "").strip()
        self.timeout_seconds=timeout_seconds
    @property
    def configured(self)->bool: return bool(self.url and self.token)
    def research(self,symbol:str,context:Dict[str,Any])->Dict[str,Any]:
        if not self.configured: return {"status":"unconfigured","symbol":symbol}
        r=requests.post(f"{self.url}/research",json={"symbol":symbol,"market":"NSE","context":context},headers={"Authorization":f"Bearer {self.token}"},timeout=self.timeout_seconds)
        r.raise_for_status()
        return r.json()
