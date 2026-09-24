import pytest
from broker.dhan_broker import DhanBroker, LiveTradingDisabled, OrderIntent
from trading.risk_engine import RiskEngine
from data_provider.dhan_fetcher import is_dhan_configured, normalize_dhan_symbol

def test_dhan_symbol_normalization():
    assert normalize_dhan_symbol("NSE:RELIANCE")=="RELIANCE"
    assert normalize_dhan_symbol("RELIANCE.NS")=="RELIANCE"

def test_dhan_configuration_is_env_only(monkeypatch):
    monkeypatch.delenv("DHAN_CLIENT_ID",raising=False); monkeypatch.delenv("DHAN_ACCESS_TOKEN",raising=False)
    assert not is_dhan_configured()

def test_live_broker_is_fail_closed_by_default(monkeypatch):
    monkeypatch.delenv("DHAN_LIVE_TRADING_ENABLED",raising=False)
    broker=DhanBroker(client_id="x",access_token="y")
    with pytest.raises(LiveTradingDisabled):
        broker.place_order(OrderIntent(symbol="RELIANCE",side="BUY",quantity=1,security_id="1333"),confirm_live=True)

def test_risk_engine_enforces_project_limits():
    d=RiskEngine().evaluate(entry_price=100,stop_price=99,target_price=102,side="BUY")
    assert d.approved and d.quantity==500 and d.risk_amount==500
    blocked=RiskEngine().evaluate(entry_price=100,stop_price=99.5,target_price=100.5,side="BUY")
    assert not blocked.approved
    assert any("Reward/risk" in x for x in blocked.reasons)
