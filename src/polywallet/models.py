"""Data models used by the polywallet analytics toolkit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional


def _parse_decimal(value: Any) -> Decimal:
    """Safely convert a Polymarket numeric value to :class:`~decimal.Decimal`."""

    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _parse_timestamp(value: Any) -> datetime:
    """Convert seconds (int/float/str) into a timezone-aware UTC datetime."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if value is None:
        raise ValueError("timestamp value cannot be None")
    seconds = float(value)
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


@dataclass(frozen=True)
class Trade:
    """Represents a single fill from the Polymarket CLOB."""

    id: str
    market_id: str
    outcome_id: str
    side: str
    price: Decimal
    size: Decimal
    cost: Decimal
    fee: Decimal
    timestamp: datetime
    tx_hash: Optional[str] = None
    maker: Optional[str] = None
    taker: Optional[str] = None

    @classmethod
    def from_api(cls, payload: Dict[str, Any]) -> "Trade":
        """Create a :class:`Trade` instance from a raw API response."""

        required_fields = [
            "id",
            "market",
            "outcome",
            "side",
            "price",
            "size",
            "cost",
            "fee",
            "timestamp",
        ]
        for field in required_fields:
            if field not in payload:
                raise KeyError(f"Missing field '{field}' in trade payload: {payload}")

        return cls(
            id=str(payload["id"]),
            market_id=str(payload["market"]),
            outcome_id=str(payload["outcome"]),
            side=str(payload["side"]).lower(),
            price=_parse_decimal(payload["price"]),
            size=_parse_decimal(payload["size"]),
            cost=_parse_decimal(payload["cost"]),
            fee=_parse_decimal(payload["fee"]),
            timestamp=_parse_timestamp(payload["timestamp"]),
            tx_hash=str(payload.get("transactionHash") or payload.get("txHash") or ""),
            maker=payload.get("maker"),
            taker=payload.get("taker"),
        )

    @property
    def signed_size(self) -> Decimal:
        """Return the signed size where buys are positive and sells are negative."""

        if self.side == "buy":
            return self.size
        if self.side == "sell":
            return -self.size
        raise ValueError(f"Unexpected trade side: {self.side}")

    @property
    def notional(self) -> Decimal:
        """Return the notional amount (price * size)."""

        return self.price * self.size


@dataclass(frozen=True)
class Redemption:
    """Represents a redemption record for a settled Polymarket market."""

    market_id: str
    outcome_id: str
    amount: Decimal
    payout: Decimal
    timestamp: datetime

    @classmethod
    def from_api(cls, payload: Dict[str, Any]) -> "Redemption":
        required_fields = ["market", "outcome", "amount", "payout", "timestamp"]
        for field in required_fields:
            if field not in payload:
                raise KeyError(f"Missing field '{field}' in redemption payload: {payload}")

        return cls(
            market_id=str(payload["market"]),
            outcome_id=str(payload["outcome"]),
            amount=_parse_decimal(payload["amount"]),
            payout=_parse_decimal(payload["payout"]),
            timestamp=_parse_timestamp(payload["timestamp"]),
        )
