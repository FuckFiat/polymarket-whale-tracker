#!/usr/bin/env python3
"""
NANO Polymarket Whale Tracker — Main Tracker
Discover, rank, and monitor whale wallets on Polymarket

Usage:
    python whale_tracker.py discover    # Find and rank whales
    python whale_tracker.py monitor     # Start real-time monitoring
    python whale_tracker.py report      # Generate whale report
"""

import asyncio
import argparse
import logging
import json
import sys
import os
from datetime import datetime

import numpy as np
import pandas as pd

import config as cfg
from api_client import PolymarketClient
from wallet_analyzer import WalletAnalyzer
from whale_monitor import WhaleMonitor

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("polymarket.tracker")

# Ensure results directory exists
os.makedirs(cfg.RESULTS_DIR, exist_ok=True)


def print_banner():
    print("""
╔══════════════════════════════════════════════════╗
║   🐋 NANO Polymarket Whale Tracker v1.0          ║
║   Track the smart money on prediction markets    ║
╚══════════════════════════════════════════════════╝
""")


def print_whale_table(wallets, top_n=10):
    """Pretty print top whales."""
    if not wallets:
        print("❌ No whales found!")
        return

    print(f"\n🐋 Top {min(top_n, len(wallets))} Whale Wallets")
    print("═" * 90)
    print(f"{'#':>3} {'Whale':>4} {'Address':<16} {'Trades':>6} {'Volume':>12} "
          f"{'PnL':>12} {'Win%':>6} {'ROI%':>8} {'Score':>7}")
    print("─" * 90)

    for i, ws in enumerate(wallets[:top_n], 1):
        whale_icon = "🐋" if ws.is_whale else "🐟"
        addr = f"{ws.address[:8]}...{ws.address[-6:]}"
        print(
            f"{i:>3} {whale_icon:>4} {addr:<16} {ws.total_trades:>6} "
            f"${ws.total_volume:>10,.0f} ${ws.realized_pnl:>10,.2f} "
            f"{ws.win_rate:>5.1f}% {ws.roi:>7.2f}% {ws.score:>7.3f}"
        )

    print("═" * 90)


async def discover_whales(top_markets: int = 5, top_whales: int = 10):
    """Main discovery pipeline: fetch markets, collect trades, rank wallets."""
    print_banner()
    client = PolymarketClient()
    analyzer = WalletAnalyzer()

    try:
        # Step 1: Fetch active markets
        print("📡 Step 1: Fetching active markets...")
        markets = await client.get_active_markets()
        if not markets:
            print("❌ No markets found. API may be down.")
            return None

        print(f"   ✅ Found {len(markets)} active markets")

        # Show top markets by volume
        sorted_m = sorted(markets, key=lambda m: float(m.get("volume", 0) or 0), reverse=True)
        print(f"\n📊 Top {min(5, len(sorted_m))} Markets by Volume:")
        for i, m in enumerate(sorted_m[:5], 1):
            question = m.get("question", "Unknown")[:60]
            vol = float(m.get("volume", 0) or 0)
            print(f"   {i}. {question}... (${vol:,.0f})")

        # Step 2: Collect trades from top markets
        print(f"\n📊 Step 2: Collecting trades from top {top_markets} markets...")
        trades_by_market = await client.get_top_markets_trades(sorted_m, top_n=top_markets)

        total_trades = 0
        for market_id, trades in trades_by_market.items():
            if trades:
                analyzer.ingest_trades(trades, market_id=market_id)
                total_trades += len(trades)

        print(f"   ✅ Collected {total_trades} trades from {len(trades_by_market)} markets")
        print(f"   ✅ Found {len(analyzer.wallets)} unique wallets")

        # Step 3: Also try to get trades directly from data API
        print("\n📊 Step 3: Fetching recent global trades...")
        try:
            global_trades = await client._rate_limited_get(
                f"{cfg.DATA_URL}/trades",
                params={"limit": 500}
            )
            if global_trades:
                analyzer.ingest_trades(global_trades, market_id="global")
                print(f"   ✅ Added {len(global_trades)} global trades")
        except Exception as e:
            print(f"   ⚠️  Global trades fetch failed: {e}")

        # Step 4: Compute PnL and rank
        print("\n📈 Step 4: Computing PnL and ranking wallets...")
        analyzer.compute_pnl()
        ranked = analyzer.compute_rankings()
        whales = [w for w in ranked if w.is_whale]

        print(f"   ✅ Ranked {len(ranked)} eligible wallets")
        print(f"   ✅ Identified {len(whales)} whale wallets (top {cfg.WHALE_TOP_PERCENT}%)")

        # Step 5: Display results
        print_whale_table(ranked, top_n=top_whales)

        # Step 6: Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = os.path.join(cfg.RESULTS_DIR, f"whales_{timestamp}.json")

        results = {
            "timestamp": datetime.now().isoformat(),
            "total_markets": len(markets),
            "total_trades": total_trades,
            "total_wallets": len(analyzer.wallets),
            "ranked_wallets": len(ranked),
            "whale_count": len(whales),
            "top_wallets": [
                {
                    "rank": i + 1,
                    "address": ws.address,
                    "is_whale": ws.is_whale,
                    "trades": ws.total_trades,
                    "volume": ws.total_volume,
                    "pnl": ws.realized_pnl,
                    "win_rate": ws.win_rate,
                    "roi": ws.roi,
                    "score": ws.score,
                    "markets": len(ws.markets_traded),
                    "days_active": ws.days_active,
                }
                for i, ws in enumerate(ranked[:50])
            ],
        }

        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved: {results_file}")

        # Summary DataFrame
        df = analyzer.summary_df(top_n=20)
        csv_file = os.path.join(cfg.RESULTS_DIR, f"whales_{timestamp}.csv")
        df.to_csv(csv_file, index=False)
        print(f"💾 CSV saved: {csv_file}")

        return ranked

    finally:
        await client.close()


async def monitor_whales():
    """Start real-time whale monitoring."""
    print_banner()
    print("🔴 Whale Monitor Mode")
    print("   Discovering whales first, then monitoring...\n")

    # First discover whales
    ranked = await discover_whales(top_markets=10, top_whales=20)
    if not ranked:
        print("❌ Cannot start monitor without whales")
        return

    whales = [w for w in ranked if w.is_whale]
    if not whales:
        # If no official whales, use top 5
        whales = ranked[:5]
        print(f"⚠️  No whales in top 1%, using top 5 wallets instead")

    # Start monitor
    monitor = WhaleMonitor(known_whales=whales)
    monitor.set_whales(whales)

    print(f"\n🟢 Monitoring {len(whales)} whale wallets...")
    print("   Press Ctrl+C to stop\n")

    try:
        await monitor.run(interval=cfg.WHALE_MONITOR_INTERVAL)
    except KeyboardInterrupt:
        monitor.stop()
        print(f"\n🔴 Monitor stopped. {len(monitor.alerts)} alerts generated.")


async def generate_report():
    """Generate a summary report of recent whale activity."""
    print_banner()
    print("📋 Generating Whale Report...\n")

    client = PolymarketClient()
    analyzer = WalletAnalyzer()

    try:
        # Quick discovery
        markets = await client.get_active_markets()
        if markets:
            sorted_m = sorted(markets, key=lambda m: float(m.get("volume", 0) or 0), reverse=True)
            trades_by_market = await client.get_top_markets_trades(sorted_m, top_n=10)

            for mid, trades in trades_by_market.items():
                if trades:
                    analyzer.ingest_trades(trades, market_id=mid)

        analyzer.compute_pnl()
        ranked = analyzer.compute_rankings()
        whales = [w for w in ranked if w.is_whale]

        # Generate report
        print("=" * 60)
        print("🐋 POLYMARKET WHALE REPORT")
        print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        print(f"\n📊 Market Overview:")
        print(f"   Active Markets: {len(markets) if markets else 0}")
        print(f"   Total Wallets Analyzed: {len(analyzer.wallets)}")
        print(f"   Ranked Wallets: {len(ranked)}")
        print(f"   Whale Wallets: {len(whales)}")

        if whales:
            print(f"\n🐋 Whale Summary:")
            total_whale_volume = sum(w.total_volume for w in whales)
            total_whale_pnl = sum(w.realized_pnl for w in whales)
            avg_win_rate = np.mean([w.win_rate for w in whales])
            avg_roi = np.mean([w.roi for w in whales])

            print(f"   Total Whale Volume: ${total_whale_volume:,.0f}")
            print(f"   Total Whale PnL: ${total_whale_pnl:,.2f}")
            print(f"   Average Win Rate: {avg_win_rate:.1f}%")
            print(f"   Average ROI: {avg_roi:.2f}%")

        print_whale_table(ranked, top_n=15)

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(cfg.RESULTS_DIR, f"report_{timestamp}.txt")
        with open(report_file, "w") as f:
            f.write(f"Polymarket Whale Report - {datetime.now().isoformat()}\n")
            f.write(f"Whales found: {len(whales)}\n")
            for i, w in enumerate(ranked[:20], 1):
                f.write(
                    f"#{i} {w.address} | Trades: {w.total_trades} | "
                    f"Vol: ${w.total_volume:,.0f} | PnL: ${w.realized_pnl:,.2f} | "
                    f"Win: {w.win_rate:.1f}% | ROI: {w.roi:.2f}%\n"
                )
        print(f"\n💾 Report saved: {report_file}")

    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="NANO Polymarket Whale Tracker")
    parser.add_argument(
        "command",
        choices=["discover", "monitor", "report"],
        help="Command: discover (find whales), monitor (watch whales), report (summary)",
    )
    parser.add_argument("--markets", type=int, default=5, help="Number of top markets to scan")
    parser.add_argument("--top", type=int, default=10, help="Number of top whales to show")

    args = parser.parse_args()

    if args.command == "discover":
        asyncio.run(discover_whales(top_markets=args.markets, top_whales=args.top))
    elif args.command == "monitor":
        asyncio.run(monitor_whales())
    elif args.command == "report":
        asyncio.run(generate_report())


if __name__ == "__main__":
    main()