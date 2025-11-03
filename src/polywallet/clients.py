"""HTTP clients for interacting with the Polymarket and price data APIs."""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

import requests

from .models import Redemption, Trade

DEFAULT_USER_AGENT = "polywallet/0.1 (+https://github.com/polymarket/polywallet)"


class APIError(RuntimeError):
    """Raised when an external API returns an unexpected response."""


class PolymarketClient:
    """Minimal client for the public Polymarket CLOB API."""

    def __init__(
        self,
        base_url: str = "https://clob.polymarket.com",
        session: Optional[requests.Session] = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", user_agent)
        self.session.headers.setdefault("Accept", "application/json")

        cf_client_id = os.getenv("POLYMARKET_CF_ACCESS_CLIENT_ID")
        cf_client_secret = os.getenv("POLYMARKET_CF_ACCESS_CLIENT_SECRET")
        if cf_client_id and cf_client_secret:
            self.session.headers.setdefault("CF-Access-Client-Id", cf_client_id)
            self.session.headers.setdefault("CF-Access-Client-Secret", cf_client_secret)

    def _get(self, path: str, **params) -> Dict:
        url = f"{self.base_url}/{path.lstrip('/') }"
        response = self.session.get(url, params=params, timeout=30)
        if response.status_code != 200:
            raise APIError(
                f"Polymarket API request to {url} failed with status {response.status_code}: {response.text}"
            )
        return response.json()

    def get_trades(
        self,
        wallet_address: str,
        limit: int = 500,
        before: Optional[str] = None,
        markets: Optional[Iterable[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Trade]:
        """Fetch trades for a wallet using cursor-based pagination."""

        params: Dict[str, object] = {
            "address": wallet_address,
            "limit": limit,
        }
        if before:
            params["before"] = before
        if markets:
            params["market"] = ",".join(markets)
        if start:
            params["startTime"] = int(start.timestamp())
        if end:
            params["endTime"] = int(end.timestamp())

        data = self._get("trades", **params)
        raw_trades = data.get("trades") or data.get("data") or []
        trades = [Trade.from_api(item) for item in raw_trades]
        return trades

    def get_all_trades(
        self,
        wallet_address: str,
        limit: int = 500,
        markets: Optional[Iterable[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        max_pages: int = 100,
    ) -> List[Trade]:
        """Fetch trades across multiple pages until the API cursor is exhausted."""

        trades: List[Trade] = []
        cursor: Optional[str] = None
        for _ in range(max_pages):
            batch = self.get_trades(
                wallet_address=wallet_address,
                limit=limit,
                before=cursor,
                markets=markets,
                start=start,
                end=end,
            )
            if not batch:
                break
            trades.extend(batch)
            last_trade = batch[-1]
            cursor = last_trade.id
            if len(batch) < limit:
                break
        return trades

    def get_redemptions(
        self,
        wallet_address: str,
        limit: int = 500,
        before: Optional[str] = None,
        markets: Optional[Iterable[str]] = None,
    ) -> List[Redemption]:
        params: Dict[str, object] = {
            "address": wallet_address,
            "limit": limit,
        }
        if before:
            params["before"] = before
        if markets:
            params["market"] = ",".join(markets)

        data = self._get("redemptions", **params)
        raw_redemptions = data.get("redemptions") or data.get("data") or []
        return [Redemption.from_api(item) for item in raw_redemptions]


class CoinGeckoClient:
    """Fetch historical price data for crypto assets using the CoinGecko API."""

    def __init__(
        self,
        base_url: str = "https://api.coingecko.com/api/v3",
        session: Optional[requests.Session] = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", user_agent)
        self.session.headers.setdefault("Accept", "application/json")

    def _get(self, path: str, **params) -> Dict:
        url = f"{self.base_url}/{path.lstrip('/') }"
        response = self.session.get(url, params=params, timeout=30)
        if response.status_code != 200:
            raise APIError(
                f"CoinGecko API request to {url} failed with status {response.status_code}: {response.text}"
            )
        return response.json()

    def get_price_series(
        self,
        coin_id: str,
        start: datetime,
        end: datetime,
        vs_currency: str = "usd",
    ) -> List[Dict[str, Decimal]]:
        """Return a list of prices with timestamps in seconds."""

        params = {
            "vs_currency": vs_currency,
            "from": int(start.timestamp()),
            "to": int(end.timestamp()),
        }
        data = self._get(f"coins/{coin_id}/market_chart/range", **params)
        series = []
        for timestamp_ms, price in data.get("prices", []):
            series.append(
                {
                    "timestamp": datetime.fromtimestamp(timestamp_ms / 1000, tz=start.tzinfo or None),
                    "price": Decimal(str(price)),
                }
            )
        return series
