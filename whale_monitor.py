"""
NANO Polymarket Whale Tracker — Real-time Whale Monitor
Monitor whale activity and generate alerts
"""

import asyncio
import logging
import json
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import config as cfg
from api_client import PolymarketClient
from wallet_analyzer import WalletAnalyzer, WalletStats

logger = logging.getLogger("polymarket.monitor")


@dataclass
class WhaleAlert:
    """An alert triggered by whale activity."""
    timestamp: str
    whale_address: str
    market: str
    action: str  # "BUY" or "SELL"
    size: float
    price: float
    value_usd: float
    whale_score: float
    whale_pnl: float
    message: str


class WhaleMonitor:
    """Monitor whale wallets for new trades and generate alerts."""

    def __init__(self, known_whales: List[WalletStats] = None):
        self.client = PolymarketClient()
        self.whale_addresses: Dict[str, WalletStats] = {}
        self.seen_trades: set = set()
        self.alerts: List[WhaleAlert] = []
        self._alert_callbacks: List[Callable] = []
        self.running = False

        if known_whales:
            for w in known_whales:
                self.whale_addresses[w.address] = w

    def add_alert_callback(self, callback: Callable[[WhaleAlert], None]):
        """Add a callback for whale alerts (e.g., Telegram notification)."""
        self._alert_callbacks.append(callback)

    def set_whales(self, whales: List[WalletStats]):
        """Set the list of whales to monitor."""
        for w in whales:
            self.whale_addresses[w.address] = w
        logger.info(f"Monitoring {len(self.whale_addresses)} whale wallets")

    async def _fire_alert(self, alert: WhaleAlert):
        """Trigger all alert callbacks."""
        self.alerts.append(alert)
        logger.info(f"🐋 WHALE ALERT: {alert.message}")
        for cb in self._alert_callbacks:
            try:
                cb(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    async def check_whale_activity(self):
        """Single pass: check all whale wallets for new trades."""
        if not self.whale_addresses:
            logger.warning("No whales to monitor!")
            return

        tasks = []
        addresses = list(self.whale_addresses.keys())

        for addr in addresses:
            tasks.append(self.client.get_wallet_trades(addr, limit=20))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for addr, trades in zip(addresses, results):
            if isinstance(trades, Exception) or not trades:
                continue

            ws = self.whale_addresses[addr]

            for trade in trades:
                trade_id = trade.get("id") or trade.get("trade_id") or (
                    f"{trade.get('timestamp','')}-{trade.get('side','')}-"
                    f"{trade.get('size','')}-{trade.get('price','')}"
                )

                if trade_id in self.seen_trades:
                    continue

                self.seen_trades.add(trade_id)

                # Only alert on recent trades (last hour)
                ts = trade.get("timestamp") or trade.get("created_at", "")
                if ts:
                    try:
                        trade_time = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                        if datetime.utcnow() - trade_time > timedelta(hours=1):
                            continue
                    except (ValueError, TypeError):
                        pass

                side = trade.get("side", "UNKNOWN")
                size = float(trade.get("size", 0) or 0)
                price = float(trade.get("price", 0) or 0)
                value_usd = size * price
                market = trade.get("market") or trade.get("asset") or "unknown"

                # Only alert on significant trades (> $100)
                if value_usd < 100:
                    continue

                alert = WhaleAlert(
                    timestamp=ts or datetime.utcnow().isoformat(),
                    whale_address=addr,
                    market=market,
                    action=side,
                    size=size,
                    price=price,
                    value_usd=value_usd,
                    whale_score=ws.score,
                    whale_pnl=ws.realized_pnl,
                    message=(
                        f"🐋 Whale {addr[:8]}...{addr[-4:]} "
                        f"{side} {size:.2f} @ ${price:.4f} "
                        f"(${value_usd:,.0f}) "
                        f"[Score: {ws.score:.2f}, PnL: ${ws.realized_pnl:,.0f}]"
                    ),
                )
                await self._fire_alert(alert)

    async def run(self, interval: int = None):
        """Run continuous whale monitoring loop."""
        interval = interval or cfg.WHALE_MONITOR_INTERVAL
        self.running = True
        logger.info(f"🟢 Whale monitor started (interval: {interval}s)")

        while self.running:
            try:
                await self.check_whale_activity()
            except Exception as e:
                logger.error(f"Monitor cycle error: {e}")

            await asyncio.sleep(interval)

        logger.info("🔴 Whale monitor stopped")

    def stop(self):
        """Stop the monitoring loop."""
        self.running = False

    def format_alert_telegram(self, alert: WhaleAlert) -> str:
        """Format alert for Telegram notification."""
        emoji = "🟢" if alert.action in ("BUY", "BUY_FROM_AMM") else "🔴"
        return (
            f"{emoji} **Whale Alert** 🐋\n\n"
            f"**Wallet:** `{alert.whale_address[:8]}...{alert.whale_address[-4:]}`\n"
            f"**Action:** {alert.action}\n"
            f"**Size:** {alert.size:.2f} @ ${alert.price:.4f}\n"
            f"**Value:** ${alert.value_usd:,.0f}\n"
            f"**Market:** {alert.market}\n"
            f"**Whale Stats:** Score {alert.whale_score:.2f} | PnL ${alert.whale_pnl:,.0f}\n"
            f"**Time:** {alert.timestamp}"
        )