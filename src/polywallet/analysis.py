"""Higher-level analytics for understanding Polymarket trading behaviour."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping, Optional

from .models import Redemption, Trade


@dataclass
class MarketMetadata:
    """Minimal metadata required to reason about a market."""

    market_id: str
    slug: str
    question: str
    underlying: Optional[str] = None
    cadence_minutes: Optional[int] = None  # 60 for hourly, 15 for 15-min markets


def infer_cadence(question: str) -> Optional[int]:
    question_lower = question.lower()
    if "15 min" in question_lower or "15min" in question_lower:
        return 15
    if "hour" in question_lower:
        return 60
    return None


def infer_underlying(question: str) -> Optional[str]:
    for symbol in ("BTC", "ETH", "SOL", "XRP"):
        if symbol.lower() in question.lower():
            return symbol
    return None


class TradeAnalyzer:
    """Compute descriptive statistics for a collection of trades."""

    def __init__(
        self,
        trades: Iterable[Trade],
        market_metadata: Optional[Mapping[str, MarketMetadata]] = None,
    ) -> None:
        self.trades = list(trades)
        self.market_metadata = market_metadata or {}

    def _get_market_cadence(self, market_id: str) -> Optional[int]:
        metadata = self.market_metadata.get(market_id)
        if metadata and metadata.cadence_minutes:
            return metadata.cadence_minutes
        question = metadata.question if metadata else ""
        if not question:
            return None
        return infer_cadence(question)

    def distribution_by_minute(self, market_id: Optional[str] = None) -> Dict[int, Decimal]:
        """Aggregate trade sizes by minute offset from the market window start."""

        relevant_trades = [t for t in self.trades if market_id is None or t.market_id == market_id]
        buckets: Dict[int, Decimal] = defaultdict(lambda: Decimal("0"))

        for trade in relevant_trades:
            cadence = self._get_market_cadence(trade.market_id) or 60
            bucket_minutes = cadence
            window_start = trade.timestamp.replace(minute=0, second=0, microsecond=0)
            if cadence == 15:
                minute_block = (trade.timestamp.minute // 15) * 15
                window_start = trade.timestamp.replace(minute=minute_block, second=0, microsecond=0)
            offset = trade.timestamp - window_start
            minute_index = int(offset.total_seconds() // 60)
            buckets[minute_index] += trade.size

        return dict(sorted(buckets.items(), key=lambda item: item[0]))

    def volume_share_first_minutes(
        self,
        minutes: int = 5,
        market_id: Optional[str] = None,
    ) -> Decimal:
        """Share of traded volume occurring within the first *minutes* of each window."""

        relevant_trades = [t for t in self.trades if market_id is None or t.market_id == market_id]
        if not relevant_trades:
            return Decimal("0")

        volume_first = Decimal("0")
        total_volume = Decimal("0")
        for trade in relevant_trades:
            cadence = self._get_market_cadence(trade.market_id) or 60
            window_start = trade.timestamp.replace(minute=0, second=0, microsecond=0)
            if cadence == 15:
                minute_block = (trade.timestamp.minute // 15) * 15
                window_start = trade.timestamp.replace(minute=minute_block, second=0, microsecond=0)
            offset_minutes = (trade.timestamp - window_start).total_seconds() / 60
            total_volume += trade.size
            if offset_minutes <= minutes:
                volume_first += trade.size

        if total_volume == 0:
            return Decimal("0")
        return volume_first / total_volume

    def side_distribution(self, market_id: Optional[str] = None) -> Dict[str, Decimal]:
        """Return net volume bought vs sold."""

        counter: Dict[str, Decimal] = {"buy": Decimal("0"), "sell": Decimal("0")}
        for trade in self.trades:
            if market_id and trade.market_id != market_id:
                continue
            counter[trade.side] += trade.size
        return counter

    def net_position(self, market_id: Optional[str] = None) -> Decimal:
        """Aggregate signed position for the given market(s)."""

        position = Decimal("0")
        for trade in self.trades:
            if market_id and trade.market_id != market_id:
                continue
            position += trade.signed_size
        return position

    def realised_pnl(self, redemptions: Iterable[Redemption]) -> Decimal:
        """Compute realised PnL from trades and redemption payouts."""

        redemption_map: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for redemption in redemptions:
            key = f"{redemption.market_id}:{redemption.outcome_id}"
            redemption_map[key] += redemption.payout - redemption.amount

        pnl = Decimal("0")
        for trade in self.trades:
            key = f"{trade.market_id}:{trade.outcome_id}"
            if key in redemption_map:
                pnl += redemption_map[key] * (trade.signed_size / trade.size if trade.size else Decimal("0"))
        return pnl

    def turnover_by_market(self) -> Dict[str, Decimal]:
        turnover: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for trade in self.trades:
            turnover[trade.market_id] += trade.notional
        return dict(turnover)

    def trade_count_by_market(self) -> Mapping[str, int]:
        counter: Counter[str] = Counter()
        for trade in self.trades:
            counter[trade.market_id] += 1
        return dict(counter)

    def build_summary(self) -> Dict[str, object]:
        markets = sorted({trade.market_id for trade in self.trades})
        summary = {
            "total_trades": len(self.trades),
            "turnover": self.turnover_by_market(),
            "market_trade_counts": self.trade_count_by_market(),
            "volume_share_first_5m": {},
            "net_positions": {},
        }
        for market_id in markets:
            summary["volume_share_first_5m"][market_id] = self.volume_share_first_minutes(5, market_id)
            summary["net_positions"][market_id] = self.net_position(market_id)
        summary["overall_volume_share_first_5m"] = self.volume_share_first_minutes(5)
        summary["overall_net_position"] = self.net_position()
        return summary


def align_prices_with_trades(
    trades: Iterable[Trade],
    prices: Iterable[Dict[str, Decimal]],
    tolerance: timedelta = timedelta(minutes=5),
) -> List[Dict[str, object]]:
    """Attach nearest price observations to each trade."""

    price_list = sorted(prices, key=lambda item: item["timestamp"])
    aligned = []
    for trade in trades:
        closest = None
        min_diff = None
        for entry in price_list:
            diff = abs(entry["timestamp"] - trade.timestamp)
            if min_diff is None or diff < min_diff:
                closest = entry
                min_diff = diff
        if closest and min_diff <= tolerance:
            aligned.append(
                {
                    "trade": trade,
                    "price": closest["price"],
                    "price_timestamp": closest["timestamp"],
                    "timedelta_seconds": min_diff.total_seconds(),
                }
            )
    return aligned
