# India/NSE + Dhan integration

NSE official MCP is the primary India research/history source. DhanHQ is the broker-aware data/execution adapter. Yahoo Finance is not used for India routing.

Server-only environment:
- DHAN_CLIENT_ID
- DHAN_ACCESS_TOKEN
- DHAN_LIVE_TRADING_ENABLED=false

Initial release is paper/simulation-first. Even if the environment flag is enabled, each live order requires explicit confirm_live=True after the server-side risk gate and operator approval.

Risk policy:
- capital ₹100,000
- max risk/trade ₹500
- daily loss limit ₹1,000
- weekly loss limit ₹2,500
- max 3 trades/day
- max 2 open positions
- minimum R:R 1.5R
- equity intraday only
- derivatives disabled

Dhan order placement/modification/cancellation currently requires static IP whitelisting. Dhan orders use exchange-standard securityId. The adapter resolves NSE symbols through Dhan's instrument master.

Market-hours logic should use an exchange calendar; NSE normal equity trading is 09:15-15:30 IST.

AI agents must never call Dhan directly. Intended path:
candidate -> evidence -> backtest -> risk gate -> paper order -> explicit approval -> Dhan broker -> reconciliation.
