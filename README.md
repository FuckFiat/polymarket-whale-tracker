# 🐋 NANO Polymarket Whale Tracker

Track and analyze whale wallets on Polymarket prediction markets.

## What It Does

- **Discovers** top wallets by PnL, win rate, ROI, and activity
- **Ranks** wallets using a weighted composite score
- **Identifies** whales (top 1% by performance)
- **Monitors** whale activity in real-time
- **Alerts** on significant whale trades

## Architecture

```
polymarket_whale_tracker/
├── whale_tracker.py      # Main entry point (discover/monitor/report)
├── api_client.py          # Async Polymarket API client
├── wallet_analyzer.py     # Wallet ranking & PnL analysis
├── whale_monitor.py       # Real-time whale activity monitor
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Setup

```bash
python3 -m venv /tmp/polymarket_env
source /tmp/polymarket_env/bin/activate
pip install -r requirements.txt
```

## Usage

### Discover Whales
Find and rank top wallets from Polymarket data:
```bash
python whale_tracker.py discover
```

Options:
```bash
python whale_tracker.py discover --markets 10 --top 20
```

### Monitor Whales (Real-time)
Continuously watch whale wallets for new trades:
```bash
python whale_tracker.py monitor
```

### Generate Report
Quick summary of current whale landscape:
```bash
python whale_tracker.py report
```

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `gamma-api.polymarket.com/markets` | Active markets |
| `data-api.polymarket.com/trades` | Trade history |
| `clob.polymarket.com/prices` | Current prices |
| `clob.polymarket.com/book` | Order book |

All data is **public** — Polymarket runs on Polygon blockchain.

## Scoring System

Wallets are scored on a 0-1 scale using weighted metrics:

| Metric | Weight | Description |
|--------|--------|-------------|
| PnL | 35% | Total realized profit |
| Win Rate | 25% | % of profitable trades |
| ROI | 25% | Return on investment |
| Recency | 15% | How recently active |

Whales = top 1% of ranked wallets.

## Output

Results are saved to `results/` directory:
- `whales_YYYYMMDD_HHMMSS.json` — Full results
- `whales_YYYYMMDD_HHMMSS.csv` — CSV summary
- `report_YYYYMMDD_HHMMSS.txt` — Text report

## Legal

This tool only reads **public blockchain data**. No trading, no manipulation — pure analysis and notifications.