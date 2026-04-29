"""
NANO Polymarket Whale Tracker — Wallet Analyzer
Rank wallets by PnL, Win Rate, ROI, and recency
Uses FIFO buy/sell matching for accurate PnL calculation
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np
import pandas as pd

import config as cfg

logger = logging.getLogger("polymarket.analyzer")


@dataclass
class WalletStats:
    """Statistics for a single wallet."""
    address: str
    pseudonym: str = ""
    total_trades: int = 0
    total_volume: float = 0.0
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    roi: float = 0.0
    avg_trade_size: float = 0.0
    first_trade: Optional[str] = None
    last_trade: Optional[str] = None
    days_active: int = 0
    markets_traded: set = field(default_factory=set)
    score: float = 0.0
    is_whale: bool = False
    # Per-asset positions for unrealized PnL
    positions: dict = field(default_factory=dict)


class WalletAnalyzer:
    """Analyze and rank wallets by performance using FIFO PnL calculation."""

    def __init__(self):
        self.wallets: Dict[str, WalletStats] = {}
        self._raw_trades: Dict[str, List[Dict]] = defaultdict(list)

    def ingest_trades(self, trades: List[Dict], market_id: str = ""):
        """Process trades and accumulate per-wallet stats."""
        for trade in trades:
            maker = trade.get("proxyWallet") or trade.get("maker") or trade.get("maker_address", "")
            if not maker:
                continue

            self._raw_trades[maker].append(trade)

            if maker not in self.wallets:
                self.wallets[maker] = WalletStats(address=maker)

            ws = self.wallets[maker]
            ws.total_trades += 1

            # Store pseudonym if available
            if trade.get("pseudonym") and not ws.pseudonym:
                ws.pseudonym = trade.get("pseudonym", "")
            if trade.get("name") and not ws.pseudonym:
                ws.pseudonym = trade.get("name", "")

            if market_id:
                ws.markets_traded.add(market_id)

            # Parse trade values
            size = float(trade.get("size", 0) or 0)
            price = float(trade.get("price", 0) or 0)
            ws.total_volume += size * price
            ws.avg_trade_size = ws.total_volume / ws.total_trades

            # Track timing
            timestamp = trade.get("timestamp")
            if timestamp:
                # Timestamp can be unix int or ISO string
                ts_str = ""
                if isinstance(timestamp, (int, float)):
                    ts_str = datetime.utcfromtimestamp(timestamp).isoformat()
                elif isinstance(timestamp, str):
                    ts_str = timestamp

                if ts_str:
                    if ws.first_trade is None or ts_str < ws.first_trade:
                        ws.first_trade = ts_str
                    if ws.last_trade is None or ts_str > ws.last_trade:
                        ws.last_trade = ts_str

    def compute_pnl(self):
        """Compute PnL using FIFO matching per asset per wallet.

        For each wallet:
        - Group trades by asset (token_id)
        - Match BUYs with SELLs using FIFO
        - Calculate realized PnL from closed positions
        - Estimate unrealized PnL from open positions at current prices
        """
        for addr, trades in self._raw_trades.items():
            ws = self.wallets[addr]
            if ws.total_trades < 2:
                continue

            # Group trades by asset (token/condition)
            by_asset = defaultdict(list)
            for t in trades:
                asset_id = t.get("asset") or t.get("conditionId") or "unknown"
                by_asset[asset_id].append(t)

            total_realized = 0.0
            total_unrealized = 0.0
            total_winning = 0
            total_losing = 0
            positions = {}

            for asset_id, asset_trades in by_asset.items():
                # Sort by timestamp
                def get_ts(t):
                    ts = t.get("timestamp", 0)
                    if isinstance(ts, (int, float)):
                        return ts
                    if isinstance(ts, str):
                        try:
                            return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
                        except (ValueError, TypeError):
                            return 0
                    return 0

                sorted_trades = sorted(asset_trades, key=get_ts)

                # FIFO inventory tracking
                inventory = []  # list of (size, price) tuples
                asset_realized = 0.0
                last_price = 0.0

                for t in sorted_trades:
                    side = t.get("side", "").upper()
                    size = float(t.get("size", 0) or 0)
                    price = float(t.get("price", 0) or 0)

                    if not size or not price:
                        continue

                    last_price = price

                    if side == "BUY" or side == "BUY_FROM_AMM":
                        # Add to inventory
                        inventory.append((size, price))
                    elif side in ("SELL", "SELL_TO_AMM"):
                        # FIFO: sell from oldest purchases first
                        remaining = size
                        while remaining > 0 and inventory:
                            inv_size, inv_price = inventory[0]
                            sell_from_this = min(remaining, inv_size)
                            profit = (price - inv_price) * sell_from_this
                            asset_realized += profit
                            if profit > 0:
                                total_winning += 1
                            elif profit < 0:
                                total_losing += 1

                            remaining -= sell_from_this
                            if sell_from_this >= inv_size:
                                inventory.pop(0)
                            else:
                                inventory[0] = (inv_size - sell_from_this, inv_price)

                # Calculate unrealized PnL for open positions
                asset_unrealized = 0.0
                open_size = 0.0
                for inv_size, inv_price in inventory:
                    open_size += inv_size
                    # Unrealized = current_price - avg_cost for each lot
                    asset_unrealized += (last_price - inv_price) * inv_size

                total_realized += asset_realized
                total_unrealized += asset_unrealized

                if open_size > 0 or asset_realized != 0:
                    positions[asset_id] = {
                        "open_size": open_size,
                        "last_price": last_price,
                        "realized": asset_realized,
                        "unrealized": asset_unrealized,
                    }

            ws.realized_pnl = total_realized
            ws.unrealized_pnl = total_unrealized
            ws.total_pnl = total_realized + total_unrealized
            ws.winning_trades = total_winning
            ws.losing_trades = total_losing
            ws.positions = positions

    def compute_rankings(self):
        """Compute derived metrics and rank wallets."""
        if not self.wallets:
            return []

        # Compute win rates and ROI
        for ws in self.wallets.values():
            closed = ws.winning_trades + ws.losing_trades
            ws.win_rate = (ws.winning_trades / closed * 100) if closed > 0 else 0.0
            ws.roi = (ws.realized_pnl / ws.total_volume * 100) if ws.total_volume > 0 else 0.0

            # Days active
            if ws.first_trade and ws.last_trade:
                try:
                    fmt = "%Y-%m-%dT%H:%M:%S"
                    first = datetime.strptime(ws.first_trade[:19], fmt)
                    last = datetime.strptime(ws.last_trade[:19], fmt)
                    ws.days_active = max(1, (last - first).days)
                except (ValueError, TypeError):
                    ws.days_active = 1

        # Filter: minimum trades and volume
        eligible = [
            ws for ws in self.wallets.values()
            if ws.total_trades >= cfg.MIN_TRADES_FOR_RANKING
            and ws.total_volume >= cfg.MIN_VOLUME_USD
        ]

        if not eligible:
            logger.warning(f"No wallets meet minimum criteria ({cfg.MIN_TRADES_FOR_RANKING} trades, ${cfg.MIN_VOLUME_USD} vol)")
            # Lower the bar: show all wallets with any trades
            eligible = [ws for ws in self.wallets.values() if ws.total_trades >= 2]
            if not eligible:
                logger.warning("No wallets with >=2 trades found")
                return []

        # Normalize metrics for scoring
        df = pd.DataFrame([
            {
                "address": ws.address,
                "pseudonym": ws.pseudonym,
                "pnl": ws.total_pnl,
                "win_rate": ws.win_rate,
                "roi": ws.roi,
                "volume": ws.total_volume,
                "recency": ws.days_active,
                "trades": ws.total_trades,
            }
            for ws in eligible
        ])

        # Normalize to 0-1 range
        for col in ["pnl", "win_rate", "roi", "volume"]:
            if df[col].max() != df[col].min():
                df[f"{col}_norm"] = (df[col] - df[col].min()) / (df[col].max() - df[col].min())
            else:
                df[f"{col}_norm"] = 0.5

        # Recency: more recent activity = higher score (inverse of days)
        if df["recency"].max() != df["recency"].min():
            df["recency_norm"] = 1 - (df["recency"] - df["recency"].min()) / (df["recency"].max() - df["recency"].min())
        else:
            df["recency_norm"] = 0.5

        # Weighted composite score
        w = cfg.SCORE_WEIGHTS
        df["score"] = (
            w["pnl"] * df["pnl_norm"]
            + w["win_rate"] * df["win_rate_norm"]
            + w["roi"] * df["roi_norm"]
            + w["recency"] * df["recency_norm"]
            + 0.10 * df["volume_norm"]  # bonus for volume
        )

        # Sort by score descending
        df = df.sort_values("score", ascending=False).reset_index(drop=True)

        # Assign scores back to wallet objects
        whale_threshold = max(1, int(len(eligible) * cfg.WHALE_TOP_PERCENT / 100))
        score_map = dict(zip(df["address"], df["score"]))
        whale_addrs = set(df["address"].head(whale_threshold))

        for ws in eligible:
            ws.score = score_map.get(ws.address, 0.0)
            ws.is_whale = ws.address in whale_addrs

        # Return sorted by score
        result = sorted(eligible, key=lambda w: w.score, reverse=True)
        return result

    def get_whales(self) -> List[WalletStats]:
        """Return only whale wallets."""
        ranked = self.compute_rankings()
        return [w for w in ranked if w.is_whale]

    def get_top_wallets(self, n: int = 10) -> List[WalletStats]:
        """Return top N wallets by score."""
        ranked = self.compute_rankings()
        return ranked[:n]

    def summary_df(self, top_n: int = 20) -> pd.DataFrame:
        """Return a summary DataFrame."""
        ranked = self.compute_rankings()
        rows = []
        for i, ws in enumerate(ranked[:top_n], 1):
            name = ws.pseudonym or f"{ws.address[:8]}...{ws.address[-6:]}"
            rows.append({
                "Rank": i,
                "Whale": "🐋" if ws.is_whale else "🐟",
                "Name/Address": name,
                "Trades": ws.total_trades,
                "Volume": f"${ws.total_volume:,.0f}",
                "Realized PnL": f"${ws.realized_pnl:,.2f}",
                "Total PnL": f"${ws.total_pnl:,.2f}",
                "Win%": f"{ws.win_rate:.1f}%",
                "ROI%": f"{ws.roi:.2f}%",
                "Markets": len(ws.markets_traded),
                "Days": ws.days_active,
                "Score": f"{ws.score:.3f}",
            })
        return pd.DataFrame(rows)