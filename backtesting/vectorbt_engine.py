# -*- coding: utf-8 -*-
"""VectorBT strategy backtesting boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Optional
import pandas as pd

@dataclass(frozen=True)
class BacktestResult:
    total_return: float
    max_drawdown: float
    trades: int
    raw: Any

class VectorBTBacktester:
    def __init__(self, initial_cash: float=100_000.0, fees: float=0.0003, slippage: float=0.0002):
        self.initial_cash=initial_cash; self.fees=fees; self.slippage=slippage
    def run(self, close: pd.Series, entries: pd.Series, exits: pd.Series, size: Optional[pd.Series]=None)->BacktestResult:
        try:
            import vectorbt as vbt
        except ImportError as exc:
            raise RuntimeError("VectorBT is required for backtesting") from exc
        kwargs={"init_cash":self.initial_cash,"fees":self.fees,"slippage":self.slippage}
        if size is not None: kwargs["size"]=size
        pf=vbt.Portfolio.from_signals(close, entries, exits, **kwargs)
        stats=pf.stats()
        total_return=float(stats.get("Total Return [%]",0.0))/100.0
        max_dd=float(stats.get("Max Drawdown [%]",0.0))/100.0
        trades=int(stats.get("Total Trades",0))
        return BacktestResult(total_return,max_dd,trades,pf)
