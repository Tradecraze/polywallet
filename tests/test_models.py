from datetime import datetime, timezone
from decimal import Decimal

import pytest

from polywallet.models import Redemption, Trade


def test_trade_from_api_parses_fields():
    payload = {
        "id": "trade-1",
        "market": "market-abc",
        "outcome": "yes",
        "side": "BUY",
        "price": "0.52",
        "size": "10",
        "cost": "5.2",
        "fee": "0.01",
        "timestamp": 1700000000,
        "transactionHash": "0xdeadbeef",
    }
    trade = Trade.from_api(payload)
    assert trade.id == "trade-1"
    assert trade.side == "buy"
    assert trade.price == Decimal("0.52")
    assert trade.size == Decimal("10")
    assert trade.timestamp == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    assert trade.tx_hash == "0xdeadbeef"
    assert trade.signed_size == Decimal("10")
    assert trade.notional == Decimal("5.2")


def test_redemption_from_api():
    payload = {
        "market": "market-abc",
        "outcome": "yes",
        "amount": "10",
        "payout": "12",
        "timestamp": 1700003600,
    }
    redemption = Redemption.from_api(payload)
    assert redemption.market_id == "market-abc"
    assert redemption.amount == Decimal("10")
    assert redemption.payout == Decimal("12")


@pytest.mark.parametrize(
    "side,expected",
    [("buy", Decimal("5")), ("sell", Decimal("-5"))],
)
def test_trade_signed_size(side, expected):
    trade = Trade.from_api(
        {
            "id": "t",
            "market": "m",
            "outcome": "o",
            "side": side,
            "price": "0.5",
            "size": "5",
            "cost": "2.5",
            "fee": "0",
            "timestamp": 1700000000,
        }
    )
    assert trade.signed_size == expected
