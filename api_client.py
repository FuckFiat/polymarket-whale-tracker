"""
NANO Polymarket Whale Tracker — API Client
Async client for Polymarket REST APIs
"""

import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

import config as cfg

logger = logging.getLogger("polymarket.api")


class PolymarketClient:
    """Async client for Polymarket APIs (CLOB, Data, Gamma)."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._request_semaphore = asyncio.Semaphore(cfg.MAX_CONCURRENT)
        self._last_request = 0.0

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _rate_limited_get(self, url: str, params: Dict = None) -> Any:
        """GET with rate limiting and retry."""
        await self._ensure_session()
        async with self._request_semaphore:
            await asyncio.sleep(cfg.REQUEST_DELAY)
            for attempt in range(3):
                try:
                    async with self.session.get(url, params=params) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        elif resp.status == 429:
                            wait = 2 ** attempt
                            logger.warning(f"Rate limited, waiting {wait}s...")
                            await asyncio.sleep(wait)
                        else:
                            logger.error(f"API error {resp.status}: {url}")
                            return None
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Request failed (attempt {attempt+1}): {e}")
                    await asyncio.sleep(2 ** attempt)
            return None

    # ── Markets ──────────────────────────────────────────────

    async def get_active_markets(self, limit: int = None) -> List[Dict]:
        """Fetch all active markets from Gamma API."""
        limit = limit or cfg.MARKETS_LIMIT
        all_markets = []
        offset = 0
        batch = 100

        while True:
            params = {
                "closed": "false",
                "active": "true",
                "limit": batch,
                "offset": offset,
            }
            data = await self._rate_limited_get(f"{cfg.GAMMA_URL}/markets", params)
            if not data:
                break
            all_markets.extend(data)
            if len(data) < batch:
                break
            offset += batch
            if len(all_markets) >= limit:
                break

        logger.info(f"Fetched {len(all_markets)} active markets")
        return all_markets[:limit]

    async def get_market_info(self, condition_id: str) -> Optional[Dict]:
        """Get detailed info for a single market."""
        return await self._rate_limited_get(
            f"{cfg.GAMMA_URL}/markets/{condition_id}"
        )

    # ── Trades ───────────────────────────────────────────────

    async def get_market_trades(self, market_slug: str, limit: int = None) -> List[Dict]:
        """Get trades for a specific market."""
        limit = limit or cfg.TRADES_PER_MARKET
        params = {"market": market_slug, "limit": limit}
        data = await self._rate_limited_get(f"{cfg.DATA_URL}/trades", params)
        # Also try slug parameter if market param returns empty
        if not data:
            params = {"slug": market_slug, "limit": limit}
            data = await self._rate_limited_get(f"{cfg.DATA_URL}/trades", params)
        return data or []

    async def get_wallet_trades(self, wallet_address: str, limit: int = None) -> List[Dict]:
        """Get all trades for a wallet address."""
        limit = limit or cfg.WALLET_TRADES_LIMIT
        all_trades = []
        offset = 0

        while True:
            params = {"proxyWallet": wallet_address, "limit": min(limit, 100), "offset": offset}
            data = await self._rate_limited_get(f"{cfg.DATA_URL}/trades", params)
            if not data or len(data) == 0:
                break
            all_trades.extend(data)
            offset += len(data)
            if len(data) < 100 or len(all_trades) >= limit:
                break

        return all_trades

    # ── Prices / Orderbook ───────────────────────────────────

    async def get_token_prices(self, token_id: str) -> Optional[Dict]:
        """Get current prices for a token."""
        params = {"token_id": token_id}
        return await self._rate_limited_get(f"{cfg.CLOB_URL}/prices", params)

    async def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """Get order book for a token."""
        params = {"token_id": token_id}
        return await self._rate_limited_get(f"{cfg.CLOB_URL}/book", params)

    # ── Positions ────────────────────────────────────────────

    async def get_market_positions(self, condition_id: str) -> List[Dict]:
        """Get positions for a market condition."""
        params = {"condition_id": condition_id}
        data = await self._rate_limited_get(f"{cfg.DATA_URL}/positions", params)
        return data or []

    # ── Batch operations ──────────────────────────────────────

    async def get_top_markets_trades(self, markets: List[Dict], top_n: int = 5) -> Dict[str, List[Dict]]:
        """Fetch trades for top N markets by volume."""
        # Sort by volume if available
        sorted_markets = sorted(
            markets,
            key=lambda m: float(m.get("volume", 0) or 0),
            reverse=True,
        )
        top = sorted_markets[:top_n]

        results = {}
        tasks = []
        slugs = []
        for market in top:
            # Use slug for data API trades
            slug = market.get("slug", "")
            if slug:
                slugs.append(slug)
                tasks.append(self.get_market_trades(slug))

        trades_list = await asyncio.gather(*tasks, return_exceptions=True)

        for slug_val, trades in zip(slugs, trades_list):
            if isinstance(trades, Exception):
                logger.error(f"Error fetching trades for {slug_val}: {trades}")
                results[slug_val] = []
            else:
                results[slug_val] = trades
                logger.info(f"  {slug_val}: {len(trades)} trades")

        return results