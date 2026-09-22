# -*- coding: utf-8 -*-
"""Deterministic paper broker used before any live Dhan execution."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from .risk_engine import RiskEngine

@dataclass
class PaperOrder:
    order_id:str
    symbol:str
    side:str
    quantity:int
    entry_price:float
    stop_price:float
    target_price:float
    status:str="PAPER_PENDING"

class PaperBroker:
    def __init__(self,risk_engine:RiskEngine|None=None):
        self.risk_engine=risk_engine or RiskEngine()
        self.orders:Dict[str,PaperOrder]={}
        self._counter=0
    def submit(self,*,symbol:str,side:str,entry_price:float,stop_price:float,target_price:float,trades_today:int=0,open_positions:int=0,quantity:int|None=None)->PaperOrder:
        decision=self.risk_engine.evaluate(entry_price=entry_price,stop_price=stop_price,target_price=target_price,side=side,trades_today=trades_today,open_positions=open_positions,quantity=quantity)
        if not decision.approved: raise ValueError("Paper order rejected: "+"; ".join(decision.reasons))
        self._counter+=1
        order=PaperOrder(f"PAPER-{self._counter:06d}",symbol,side.upper(),decision.quantity,entry_price,stop_price,target_price)
        self.orders[order.order_id]=order
        return order
    def list_orders(self)->List[PaperOrder]: return list(self.orders.values())
