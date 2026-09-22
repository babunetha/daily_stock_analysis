# -*- coding: utf-8 -*-
"""Fail-closed DhanHQ v2 broker boundary."""
from __future__ import annotations
import os, uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests

DHAN_API_BASE="https://api.dhan.co/v2"

class LiveTradingDisabled(RuntimeError): pass

@dataclass(frozen=True)
class OrderIntent:
    symbol:str
    side:str
    quantity:int
    order_type:str="MARKET"
    product_type:str="INTRADAY"
    price:Optional[float]=None
    trigger_price:Optional[float]=None
    security_id:Optional[str]=None
    correlation_id:Optional[str]=None

class DhanBroker:
    def __init__(self, client_id:Optional[str]=None, access_token:Optional[str]=None, live_enabled:Optional[bool]=None, timeout_seconds:float=15.0):
        self.client_id=(client_id or os.getenv("DHAN_CLIENT_ID") or "").strip()
        self.access_token=(access_token or os.getenv("DHAN_ACCESS_TOKEN") or "").strip()
        env_enabled=(os.getenv("DHAN_LIVE_TRADING_ENABLED") or "").strip().lower() in {"1","true","yes","on"}
        self.live_enabled=env_enabled if live_enabled is None else bool(live_enabled)
        self.timeout_seconds=float(timeout_seconds)
    @property
    def configured(self)->bool: return bool(self.client_id and self.access_token)
    def _headers(self)->Dict[str,str]:
        if not self.configured: raise RuntimeError("Dhan credentials are not configured")
        return {"Accept":"application/json","Content-Type":"application/json","access-token":self.access_token,"client-id":self.client_id}
    def _request(self,method:str,path:str,**kwargs:Any)->Any:
        r=requests.request(method,f"{DHAN_API_BASE}{path}",headers=self._headers(),timeout=self.timeout_seconds,**kwargs)
        if r.status_code>=400: raise RuntimeError(f"Dhan {method} {path} HTTP {r.status_code}: {r.text[:500]}")
        return r.json()
    def get_orders(self)->Any: return self._request("GET","/orders")
    def get_trades(self)->Any: return self._request("GET","/trades")
    def get_positions(self)->Any: return self._request("GET","/positions")
    def get_holdings(self)->Any: return self._request("GET","/holdings")
    def get_fund_limits(self)->Any: return self._request("GET","/fundlimit")
    def cancel_order(self,order_id:str,*,confirm_live:bool=False)->Any:
        self._require_live_gate(confirm_live); return self._request("DELETE",f"/orders/{order_id}")
    def place_order(self,intent:OrderIntent,*,confirm_live:bool=False)->Any:
        self._require_live_gate(confirm_live)
        if intent.side.upper() not in {"BUY","SELL"}: raise ValueError("Order side must be BUY or SELL")
        if intent.quantity<=0: raise ValueError("Order quantity must be positive")
        if not intent.security_id: raise ValueError("Dhan security_id is required for order placement")
        cid=(intent.correlation_id or f"DSA-{uuid.uuid4().hex[:20]}")[:30]
        payload={"dhanClientId":self.client_id,"correlationId":cid,"transactionType":intent.side.upper(),"exchangeSegment":"NSE_EQ","productType":intent.product_type,"orderType":intent.order_type,"validity":"DAY","securityId":str(intent.security_id),"quantity":int(intent.quantity),"disclosedQuantity":0,"price":float(intent.price or 0),"triggerPrice":float(intent.trigger_price or 0),"afterMarketOrder":False,"amoTime":"","boProfitValue":0,"boStopLossValue":0}
        return self._request("POST","/orders",json=payload)
    def _require_live_gate(self,confirm_live:bool)->None:
        if not self.live_enabled or not confirm_live:
            raise LiveTradingDisabled("Live Dhan trading is fail-closed; risk gate and explicit approval are required.")
