import pandas as pd

from data_provider.nse_mcp_fetcher import (
    NSEMCPFetcher,
    is_india_stock_symbol,
    normalize_nse_symbol,
)


def test_normalize_nse_symbol():
    assert normalize_nse_symbol("NSE:RELIANCE") == "RELIANCE"
    assert normalize_nse_symbol("RELIANCE.NS") == "RELIANCE"


def test_india_symbol_detection():
    assert is_india_stock_symbol("RELIANCE")
    assert is_india_stock_symbol("NSE:TCS")
    assert not is_india_stock_symbol("^NSEI")


def test_nse_history_normalization():
    fetcher = NSEMCPFetcher()
    raw = pd.DataFrame(
        [
            {
                "date": "2026-09-21",
                "open": "100",
                "high": "105",
                "low": "99",
                "close": "104",
                "volume": "100000",
                "turnover": "10400000",
                "pctChange": "4.00",
            }
        ]
    )
    normalized = fetcher._normalize_data(raw, "RELIANCE")
    assert list(normalized.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "pct_chg",
    ]
    assert normalized.iloc[0]["close"] == "104"
    assert normalized.iloc[0]["amount"] == "10400000"


def test_nse_fetcher_tool_argument_mapping():
    class Tool:
        inputSchema = {
            "properties": {
                "query": {},
                "start_date": {},
                "end_date": {},
            }
        }

    args = __import__(
        "data_provider.nse_mcp_fetcher",
        fromlist=["_build_tool_arguments"],
    )._build_tool_arguments(
        Tool(), "RELIANCE", "2026-09-01", "2026-09-21"
    )
    assert args == {
        "query": "RELIANCE",
        "start_date": "2026-09-01",
        "end_date": "2026-09-21",
    }
