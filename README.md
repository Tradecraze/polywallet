# polywallet

Utilities for downloading and analysing Polymarket trading activity for a given wallet. The toolkit focuses on hourly and 15-minute crypto prediction markets so you can inspect trade timing, volume distribution, and how trades relate to the underlying crypto price moves.

## Features

- Minimal client for the public Polymarket CLOB API (trades and redemptions)
- CoinGecko integration for fetching historical crypto price ranges
- Analysis helpers to understand trade timing, net positioning, and realised PnL
- CLI that downloads trades for a wallet, prints summary metrics, and optionally exports raw data

> **Note**: Direct network requests from this execution environment are blocked. The HTTP clients are nevertheless fully implemented; run them from your local machine where outbound internet access is available.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Alternatively, install dependencies manually:

```bash
pip install requests pytest
```

## Usage

Fetch and analyse trades for the provided wallet:

```bash
python -m polywallet.cli 0xca85f4b9e472b542e1df039594eeaebb6d466bf2 \
  --start 2024-01-01T00:00:00 \
  --end 2024-02-01T00:00:00 \
  --coin bitcoin \
  --export trades.json \
  --prices btc_prices.json
```

Environment variables `POLYMARKET_CF_ACCESS_CLIENT_ID` and `POLYMARKET_CF_ACCESS_CLIENT_SECRET` are honoured if your Polymarket account requires Cloudflare Access credentials.

After fetching the data, you can import the package in Python to run custom analysis:

```python
from polywallet import PolymarketClient, CoinGeckoClient, TradeAnalyzer

client = PolymarketClient()
trades = client.get_all_trades("0xca85f4b9e472b542e1df039594eeaebb6d466bf2")

analyzer = TradeAnalyzer(trades)
summary = analyzer.build_summary()
print(summary)
```

## Tests

The included unit tests rely on mocked data and therefore run offline:

```bash
pytest
```
