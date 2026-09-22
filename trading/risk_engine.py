# -*- coding: utf-8 -*-
"""Server-side risk gate for the India equity strategy."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RiskLimits:
    capital:float=100_000.0
    max_risk_per_trade:float=500.0
    daily_loss_limit:float=1_000.0
    weekly_loss_limit:float=2_500.0
    max_trades_per_day:int=3
    max_open_positions:int=2
    min_reward_risk:float=1.5
    max_position_value:float=100_000.0

@dataclass(frozen=True)
class RiskDecision:
    approved:bool
    reasons:tuple[str,...]
    quantity:int=0
    risk_amount:float=0.0

class RiskEngine:
    def __init__(self,limits:Optional[RiskLimits]=None): self.limits=limits or RiskLimits()
    def evaluate(self,*,entry_price:float,stop_price:float,target_price:float,side:str,realized_daily_pnl:float=0.0,realized_weekly_pnl:float=0.0,trades_today:int=0,open_positions:int=0,product_type:str="INTRADAY",quantity:Optional[int]=None)->RiskDecision:
        reasons=[]; side=side.upper(); product_type=product_type.upper()
        if entry_price<=0 or stop_price<=0 or target_price<=0: reasons.append("Prices must be positive")
        if side not in {"BUY","SELL"}: reasons.append("Only BUY/SELL are supported")
        if product_type!="INTRADAY": reasons.append("Only equity INTRADAY is enabled")
        if trades_today>=self.limits.max_trades_per_day: reasons.append("Daily trade-count limit reached")
        if open_positions>=self.limits.max_open_positions: reasons.append("Maximum open positions reached")
        if side=="BUY": risk_per_share=entry_price-stop_price; reward_per_share=target_price-entry_price
        elif side=="SELL": risk_per_share=stop_price-entry_price; reward_per_share=entry_price-target_price
        else: risk_per_share=reward_per_share=0.0
        if risk_per_share<=0: reasons.append("Stop must be on the loss side of entry")
        if reward_per_share<=0: reasons.append("Target must be on the profit side of entry")
        qty=0; risk_amount=0.0
        if risk_per_share>0 and reward_per_share>0:
            rr=reward_per_share/risk_per_share
            if rr<self.limits.min_reward_risk: reasons.append(f"Reward/risk {rr:.2f} is below minimum {self.limits.min_reward_risk:.2f}")
            qty=min(int(self.limits.max_risk_per_trade//risk_per_share),int(self.limits.max_position_value//entry_price))
            if quantity is not None: qty=min(qty,int(quantity))
            risk_amount=qty*risk_per_share
        if realized_daily_pnl<=-self.limits.daily_loss_limit: reasons.append("Daily loss limit reached")
        if realized_weekly_pnl<=-self.limits.weekly_loss_limit: reasons.append("Weekly loss limit reached")
        if qty<=0: reasons.append("Position size is zero under risk limits")
        if risk_amount>self.limits.max_risk_per_trade+1e-9: reasons.append("Calculated risk exceeds per-trade limit")
        return RiskDecision(not reasons,tuple(reasons),qty if not reasons else 0,risk_amount if not reasons else 0.0)
