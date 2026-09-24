# -*- coding: utf-8 -*-
"""Chartink-style India equity scanner on normalized DSA OHLCV frames."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List
import pandas as pd

@dataclass(frozen=True)
class ScanCandidate:
    symbol:str
    score:float
    reasons:tuple[str,...]
    entry:float
    stop:float
    target:float
    reward_risk:float

class IndiaScanner:
    def scan(self, symbol_frames:Iterable[tuple[str,pd.DataFrame]])->List[ScanCandidate]:
        out=[]
        for symbol,df in symbol_frames:
            if df is None or len(df)<30: continue
            d=df.copy()
            close=pd.to_numeric(d["close"],errors="coerce")
            volume=pd.to_numeric(d["volume"],errors="coerce")
            high=pd.to_numeric(d["high"],errors="coerce")
            low=pd.to_numeric(d["low"],errors="coerce")
            ema10=close.ewm(span=10,adjust=False).mean()
            ema30=close.ewm(span=30,adjust=False).mean()
            vwap=((close*volume).rolling(20).sum()/volume.rolling(20).sum()).iloc[-1]
            delta=close.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
            rs=gain/loss.replace(0,pd.NA); rsi=float((100-(100/(1+rs))).iloc[-1])
            vol_ratio=float(volume.iloc[-1]/volume.iloc[-6:-1].mean()) if volume.iloc[-6:-1].mean() else 0.0
            px=float(close.iloc[-1])
            atr=float((high-low).rolling(14).mean().iloc[-1])
            if not all(pd.notna(x) for x in (ema10.iloc[-1],ema30.iloc[-1],vwap,rsi,atr)): continue
            reasons=[]
            score=0.0
            if ema10.iloc[-1]>ema30.iloc[-1]: score+=30; reasons.append("EMA10>EMA30")
            if px>vwap: score+=20; reasons.append("above VWAP proxy")
            if 50<=rsi<=70: score+=15; reasons.append("RSI 50-70")
            if vol_ratio>=1.5: score+=20; reasons.append("volume expansion")
            if px>=float(close.rolling(20).max().iloc[-2])*0.98: score+=15; reasons.append("near 20D high")
            if score<60: continue
            stop=max(0.01,px-1.2*atr); target=px+2.0*(px-stop); rr=(target-px)/(px-stop)
            out.append(ScanCandidate(symbol,score,tuple(reasons),px,stop,target,rr))
        return sorted(out,key=lambda x:(x.score,x.reward_risk),reverse=True)
