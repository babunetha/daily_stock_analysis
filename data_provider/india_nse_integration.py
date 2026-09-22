# -*- coding: utf-8 -*-
"""Install the India/NSE routing into the existing provider manager."""
from __future__ import annotations

from typing import Optional

from .base import DataFetcherManager
from .nse_mcp_fetcher import NSEMCPFetcher, is_india_stock_symbol


def install_india_nse_integration() -> None:
    if getattr(DataFetcherManager, "_india_nse_integration_installed", False):
        return

    original_init = DataFetcherManager._init_default_fetchers
    original_daily = DataFetcherManager.get_daily_data

    def init_with_nse(self) -> None:
        original_init(self)
        if self._get_fetcher_by_name("NSEMCPFetcher") is None:
            self.add_fetcher(NSEMCPFetcher())

    def daily_with_nse(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
    ):
        if is_india_stock_symbol(stock_code):
            fetcher = self._get_fetcher_by_name("NSEMCPFetcher", capability="daily_data")
            if fetcher is None:
                fetcher = NSEMCPFetcher()
            frame = self._call_fetcher_method(
                fetcher,
                "get_daily_data",
                stock_code,
                start_date=start_date,
                end_date=end_date,
                days=days,
            )
            return frame, fetcher.name
        return original_daily(
            self,
            stock_code,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )

    DataFetcherManager._init_default_fetchers = init_with_nse
    DataFetcherManager.get_daily_data = daily_with_nse
    DataFetcherManager._india_nse_integration_installed = True


install_india_nse_integration()
