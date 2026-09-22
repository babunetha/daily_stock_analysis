# -*- coding: utf-8 -*-
"""
===================================
数据源策略层 - 包初始化
===================================

This package keeps the upstream provider architecture and adds an India/NSE
provider backed by the official NSE Market Data MCP interface.
"""

from .base import BaseFetcher, DataFetcherManager
from .efinance_fetcher import EfinanceFetcher
from .tencent_fetcher import TencentFetcher
from .akshare_fetcher import AkshareFetcher, is_hk_stock_code
from .tushare_fetcher import TushareFetcher
from .pytdx_fetcher import PytdxFetcher
from .baostock_fetcher import BaostockFetcher
from .yfinance_fetcher import YfinanceFetcher
from .longbridge_fetcher import LongbridgeFetcher
from .finnhub_fetcher import FinnhubFetcher
from .alphavantage_fetcher import AlphaVantageFetcher
from .us_index_mapping import (
    is_us_index_code,
    is_us_stock_code,
    get_us_index_yf_symbol,
    US_INDEX_MAPPING,
)
from .nse_mcp_fetcher import NSEMCPFetcher, is_india_stock_symbol
from .india_nse_integration import install_india_nse_integration

__all__ = [
    "BaseFetcher",
    "DataFetcherManager",
    "EfinanceFetcher",
    "TencentFetcher",
    "AkshareFetcher",
    "TushareFetcher",
    "PytdxFetcher",
    "BaostockFetcher",
    "YfinanceFetcher",
    "LongbridgeFetcher",
    "FinnhubFetcher",
    "AlphaVantageFetcher",
    "NSEMCPFetcher",
    "is_india_stock_symbol",
    "is_us_index_code",
    "is_us_stock_code",
    "is_hk_stock_code",
    "get_us_index_yf_symbol",
    "US_INDEX_MAPPING",
]
