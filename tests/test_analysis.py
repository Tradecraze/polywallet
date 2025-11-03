from datetime import datetime, timezone
from decimal import Decimal

from polywallet.analysis import TradeAnalyzer, align_prices_with_trades
from polywallet.models import Trade


def make_trade(minute: int, side: str = "buy", size: str = "1") -> Trade:
    timestamp = datetime(2024, 1, 1, 12, minute, tzinfo=timezone.utc)
    return Trade.from_api(
        {
            "id": f"trade-{minute}",
            "market": "market-1",
            "outcome": "yes",
            "side": side,
            "price": "0.5",
            "size": size,
            "cost": str(Decimal(size) * Decimal("0.5")),
            "fee": "0.01",
            "timestamp": timestamp.timestamp(),
        }
    )


def test_volume_share_first_minutes():
    trades = [make_trade(minute) for minute in (0, 1, 10, 30)]
    analyzer = TradeAnalyzer(trades)
    share = analyzer.volume_share_first_minutes(minutes=5)
    assert share == Decimal("0.5")


def test_net_position():
    trades = [make_trade(0, "buy", "2"), make_trade(5, "sell", "1")]
    analyzer = TradeAnalyzer(trades)
    assert analyzer.net_position() == Decimal("1")


def test_align_prices_with_trades():
    trades = [make_trade(0)]
    prices = [
        {"timestamp": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc), "price": Decimal("43000")},
        {"timestamp": datetime(2024, 1, 1, 12, 5, tzinfo=timezone.utc), "price": Decimal("43100")},
    ]
    aligned = align_prices_with_trades(trades, prices)
    assert aligned[0]["price"] == Decimal("43000")
