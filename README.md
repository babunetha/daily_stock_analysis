<div align="center">

# 📈 股票智能分析系统

> Hosted India-market research dashboard: https://daily-stock-analysis.hatchable.site

The hosted build currently provides an online research dashboard, NSE scanner, quote/technical indicators, neutral AI research, and Supabase-backed watchlist/analysis persistence. Broker execution and live trading are disabled.

[![CI](https://github.com/babunetha/daily_stock_analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/babunetha/daily_stock_analysis/actions/workflows/ci.yml)

</div>

## Hosted deployment

The reference implementation remains in this repository. The current online deployment uses:

- **GitHub** — source of truth and CI.
- **Supabase** — hosted persistence for watchlist and analysis history.
- **Hatchable** — web/API runtime.
- **Yahoo Finance** — best-effort market-data source for the hosted research endpoints.
- **Hatchable AI** — neutral research summaries from supplied market data.

### Safety state

The hosted deployment is **research-only**. It does not place broker orders and does not enable Dhan/live trading. Market data may be delayed or unavailable.

### Local development

See the existing project documentation and apps/dsa-web for the full React/Vite workspace.

## Upstream project documentation

The original multi-market analysis, data-provider, AI-agent, notification, backtesting, and deployment capabilities remain documented in the repository.
