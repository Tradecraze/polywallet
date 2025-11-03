"""Command line entry-point for running the polywallet analysis."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .analysis import MarketMetadata, TradeAnalyzer, align_prices_with_trades, infer_cadence, infer_underlying
from .clients import CoinGeckoClient, PolymarketClient
from .models import Trade


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def run_cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Analyse Polymarket wallet activity")
    parser.add_argument("wallet", help="Wallet address to analyse")
    parser.add_argument("--start", dest="start", help="Start timestamp (ISO 8601)")
    parser.add_argument("--end", dest="end", help="End timestamp (ISO 8601)")
    parser.add_argument("--limit", dest="limit", type=int, default=500, help="Page size for API requests")
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=50)
    parser.add_argument("--export", dest="export_path", type=Path, help="Optional path to export raw trades JSON")
    parser.add_argument("--coin", dest="coin_id", default="bitcoin", help="CoinGecko coin identifier")
    parser.add_argument("--prices", dest="export_prices", type=Path, help="Optional path to export price series JSON")
    args = parser.parse_args(argv)

    client = PolymarketClient()
    start = _parse_datetime(args.start)
    end = _parse_datetime(args.end)

    trades = client.get_all_trades(
        wallet_address=args.wallet,
        limit=args.limit,
        start=start,
        end=end,
        max_pages=args.max_pages,
    )

    if not trades:
        print("No trades returned by the Polymarket API. Check wallet address or timeframe.")
        return 1

    if args.export_path:
        data = [trade.__dict__ for trade in trades]
        args.export_path.write_text(json.dumps(data, default=str, indent=2))
        print(f"Exported {len(trades)} trades to {args.export_path}")

    metadata = {}
    for trade in trades:
        if trade.market_id not in metadata:
            question = trade.market_id
            metadata[trade.market_id] = MarketMetadata(
                market_id=trade.market_id,
                slug=trade.market_id,
                question=question,
                underlying=infer_underlying(question) or "Unknown",
                cadence_minutes=infer_cadence(question) or 60,
            )

    analyzer = TradeAnalyzer(trades, metadata)
    summary = analyzer.build_summary()

    print("Summary metrics:")
    print(json.dumps(summary, indent=2, default=str))

    price_client = CoinGeckoClient()
    first_trade = min(trades, key=lambda t: t.timestamp)
    last_trade = max(trades, key=lambda t: t.timestamp)
    price_series = price_client.get_price_series(args.coin_id, first_trade.timestamp, last_trade.timestamp)

    if args.export_prices:
        args.export_prices.write_text(json.dumps(price_series, default=str, indent=2))
        print(f"Exported {len(price_series)} price points to {args.export_prices}")

    aligned = align_prices_with_trades(trades, price_series)
    print(f"Aligned {len(aligned)} trades with underlying price observations.")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(run_cli())
