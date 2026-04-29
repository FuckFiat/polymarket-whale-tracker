#!/usr/bin/env python3
"""
🐋 NANO Polymarket Whale Monitor — Telegram Alerts
Monitors top whale wallets and sends Telegram alerts when they make moves.
"""

import asyncio
import aiohttp
import json
import time
import os
from datetime import datetime

# Config
WHALE_ADDRESSES = {
    "0x2a2c": {"name": "🐋 Кит #1 — Геополитик-контрариан", "volume": "$26.3M"},
    "0xdc87": {"name": "🐋 Кит #2 — Mega Whale", "volume": "$20.2M"},
    "0xe90b": {"name": "🐈 Кит #3 — Крипто-оракул", "volume": "$12.1M"},
    "0x0197": {"name": "🐋 Кит #4 — majorexploiter", "volume": "$6.9M"},
    "0x0222": {"name": "🐋 Кит #5 — HorizonSplendidView", "volume": "$6.5M"},
    "0x07b8": {"name": "🐋 Кит #6 — joosangyoo", "volume": "$5.5M"},
    "0xb904": {"name": "🐋 Кит #7 — MinorKey4", "volume": "$5.1M"},
    "0xc2e7": {"name": "🐠 Кит #8 — beachboy4", "volume": "$3.5M"},
    "0xb45a": {"name": "🐠 Кит #9 — bcda", "volume": "$3.2M"},
    "0x916f": {"name": "🐠 Кит #10 — WoofMaster", "volume": "$1.5M"},
}

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CHECK_INTERVAL = 300  # 5 minutes
STATE_FILE = os.path.join(os.path.dirname(__file__), "results", "whale_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_trades": {}, "last_check": 0, "alerts_sent": 0}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def match_whale(address):
    """Check if address matches any tracked whale (partial match)."""
    addr_lower = address.lower()
    for prefix, info in WHALE_ADDRESSES.items():
        if addr_lower.startswith(prefix.lower()):
            return info
    return None

def format_trade_alert(whale_info, trade):
    """Format a trade as a Telegram-friendly alert message."""
    side = trade.get("side", "?")
    size = float(trade.get("size", 0) or 0)
    price = float(trade.get("price", 0) or 0)
    vol = size * price
    title = trade.get("title", "Unknown market")[:50]
    outcome = trade.get("outcome", "?")
    slug = trade.get("slug", "")
    pseudo = trade.get("pseudonym", "anon")

    side_emoji = "🟢" if side == "BUY" else "🔴"
    side_text = "КУПИЛ" if side == "BUY" else "ПРОДАЛ"

    alert = f"""🐋 WHALE ALERT!
═══════════════════════════════════

{whale_info['name']}
📊 Volume: {whale_info['volume']}

{side_emoji} {side_text}: {side_emoji}
💰 ${vol:,.0f} ({size:.0f} shares @ {price:.2f}¢)
📈 Market: {title}
🎯 Outcome: {outcome}
👤 Pseudonym: {pseudo}

🔗 https://polymarket.com/event/{slug}

═══════════════════════════════════
⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"""
    return alert

def format_cluster_alert(trades, market_title):
    """Format a cluster signal when multiple whales trade the same market."""
    whales = set()
    total_vol = 0
    for t in trades:
        w = match_whale(t.get("proxyWallet", ""))
        if w:
            whales.add(w["name"])
        total_vol += float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)

    alert = f"""🔥 CLUSTER SIGNAL!
═══════════════════════════════════

{len(whales)} КИТОВ в одном рынке за 2ч!

📈 Market: {market_title[:50]}
💰 Combined volume: ${total_vol:,.0f}
🐋 Whales: {len(whales)}

⚠️ Это сильный Consensus-сигнал!
🔗 Проверь дашборд: https://fuckfiat.github.io/polymarket-whale-tracker/

═══════════════════════════════════
⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"""
    return alert


class WhaleMonitor:
    def __init__(self):
        self.state = load_state()
        self.session = None

    async def init_session(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def close(self):
        if self.session:
            await self.session.close()

    async def fetch_top_markets(self):
        """Get top markets by volume."""
        url = f"{GAMMA_API}/markets?limit=30&order=volume24hr&ascending=false&closed=false"
        async with self.session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return []

    async def fetch_trades(self, slug="", limit=200):
        """Fetch recent trades."""
        url = f"{DATA_API}/trades?limit={limit}&order=desc"
        if slug:
            url += f"&slug={slug}"
        async with self.session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return []

    def is_new_trade(self, trade):
        """Check if this trade is new (not seen before)."""
        addr = trade.get("proxyWallet", "")
        ts = trade.get("timestamp", "")
        key = f"{addr}:{ts}"
        return key not in self.state["last_trades"]

    def record_trade(self, trade):
        """Mark trade as seen."""
        addr = trade.get("proxyWallet", "")
        ts = trade.get("timestamp", "")
        key = f"{addr}:{ts}"
        self.state["last_trades"][key] = time.time()
        # Keep only last 1000 entries
        if len(self.state["last_trades"]) > 1000:
            sorted_keys = sorted(self.state["last_trades"].keys(), 
                               key=lambda k: self.state["last_trades"][k])
            for k in sorted_keys[:200]:
                del self.state["last_trades"][k]

    async def check_whales(self):
        """Main check loop - look for whale trades."""
        alerts = []

        # Get top markets
        markets = await self.fetch_top_markets()
        if not markets:
            return alerts

        # Fetch global trades
        all_trades = await self.fetch_trades(limit=500)

        # Also fetch per-market for top 5
        for m in markets[:5]:
            slug = m.get("slug", "")
            trades = await self.fetch_trades(slug=slug, limit=200)
            all_trades.extend(trades)

        # Find whale trades
        whale_trades = []
        for t in all_trades:
            addr = t.get("proxyWallet", "")
            whale_info = match_whale(addr)

            if whale_info and self.is_new_trade(t):
                vol = float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)
                if vol > 100:  # Only alert on trades > $100
                    alert = format_trade_alert(whale_info, t)
                    alerts.append(alert)
                    whale_trades.append(t)
                    self.record_trade(t)
                    self.state["alerts_sent"] += 1

        # Check for cluster signals (same market, multiple whales within 2h)
        market_whales = {}
        for t in whale_trades:
            slug = t.get("slug", "")
            if slug not in market_whales:
                market_whales[slug] = []
            market_whales[slug].append(t)

        for slug, trades in market_whales.items():
            unique_whales = set(t.get("proxyWallet", "")[:6] for t in trades)
            if len(unique_whales) >= 3:
                title = trades[0].get("title", slug) if trades else slug
                alert = format_cluster_alert(trades, title)
                alerts.append(alert)

        self.state["last_check"] = time.time()
        save_state(self.state)

        return alerts

    async def run(self, callback=None):
        """Run the monitor loop."""
        await self.init_session()
        print(f"🐋 Whale Monitor started. Checking every {CHECK_INTERVAL}s")
        print(f"📋 Tracking {len(WHALE_ADDRESSES)} whale addresses")

        try:
            while True:
                try:
                    alerts = await self.check_whales()
                    if alerts:
                        for alert in alerts:
                            print(alert)
                            if callback:
                                await callback(alert)
                    else:
                        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No whale activity detected")
                except Exception as e:
                    print(f"Error: {e}")

                await asyncio.sleep(CHECK_INTERVAL)
        finally:
            await self.close()


if __name__ == "__main__":
    monitor = WhaleMonitor()
    asyncio.run(monitor.run())
# --once mode for cron runs
import sys

class OnceRunner:
    def __init__(self, monitor):
        self.monitor = monitor

    async def run_once(self):
        await self.monitor.init_session()
        try:
            alerts = await self.monitor.check_whales()
            if alerts:
                for alert in alerts:
                    print(alert)
            else:
                print("NO_WHALE_ACTIVITY")
        finally:
            await self.monitor.close()

if __name__ == "__main__" and "--once" in sys.argv:
    monitor = WhaleMonitor()
    asyncio.run(OnceRunner(monitor).run_once())
