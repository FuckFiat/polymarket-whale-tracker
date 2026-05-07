#!/usr/bin/env python3
"""
PredictFun API client + Polymarket/Kalshi cross-reference + Arbitrage detection
"""

import aiohttp, asyncio, json, time, os
from datetime import datetime, timezone

PREDICTFUN_API = "https://api.predict.fun"
POLYMARKET_API = "https://clob.polymarket.com"
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "predictfun_cache.json")
CACHE_TTL = 300  # 5 min

async def fetch_predictfun_markets(session, api_key=None):
    """Fetch all markets from Predict.fun with pagination."""
    markets = []
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    
    cursor = None
    while True:
        params = {"first": "100"}
        if cursor:
            params["after"] = cursor
        
        try:
            async with session.get(f"{PREDICTFUN_API}/v1/markets", params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    break
                data = await r.json()
                if not data.get("success"):
                    break
                items = data.get("data", [])
                markets.extend(items)
                cursor = data.get("pagination", {}).get("after")
                if not cursor:
                    break
        except Exception:
            break
    
    return markets

async def fetch_polymarket_prices(session, condition_id=None, token_id=None):
    """Fetch Polymarket prices for cross-reference."""
    prices = {}
    try:
        if token_id:
            url = f"{POLYMARKET_API}/prices?token_ids={token_id}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    for tid, info in data.items():
                        prices[tid] = {
                            "yes": float(info.get("price", 0)),
                            "no": 1 - float(info.get("price", 0)),
                        }
    except Exception:
        pass
    return prices

async def find_arbitrage(session, markets, poly_prices=None):
    """Find arbitrage opportunities between Predict.fun and Polymarket."""
    arb_opps = []
    
    for m in markets:
        title = m.get("title", "")
        outcomes = m.get("outcomes", [])
        poly_ids = m.get("polymarketConditionIds", [])
        
        if not poly_ids or len(outcomes) < 2:
            continue
        
        # Get Predict.fun prices
        pf_yes = None
        pf_no = None
        for out in outcomes:
            name = (out.get("name") or "").lower()
            price = float(out.get("price") or out.get("lastPrice") or 0)
            if name in ("yes", "y"):
                pf_yes = price
            elif name in ("no", "n"):
                pf_no = price
        
        if pf_yes is None or pf_no is None:
            continue
        
        # Check if Polymarket condition ID matches
        for cid in poly_ids:
            poly_price = None
            if poly_prices and cid in poly_prices:
                poly_price = poly_prices[cid].get("yes", 0)
            
            if poly_price and pf_yes:
                spread = abs(pf_yes - poly_price)
                if spread > 0.03:  # 3% minimum spread for arbitrage
                    arb_opps.append({
                        "title": title,
                        "predictfun_yes": pf_yes,
                        "polymarket_yes": poly_price,
                        "spread": spread,
                        "spread_pct": spread * 100,
                        "direction": "BUY Predict.fun, SELL Polymarket" if pf_yes < poly_price else "BUY Polymarket, SELL Predict.fun",
                        "condition_id": cid,
                    })
    
    # Sort by spread
    arb_opps.sort(key=lambda x: x["spread"], reverse=True)
    return arb_opps

async def get_cross_platform_markets(session, api_key=None):
    """Get markets that exist on both Predict.fun AND Polymarket/Kalshi."""
    markets = await fetch_predictfun_markets(session, api_key)
    
    cross_platform = []
    for m in markets:
        poly_ids = m.get("polymarketConditionIds") or []
        kalshi_id = m.get("kalshiMarketId") or m.get("kalshiTicker")
        
        if poly_ids or kalshi_id:
            m["platforms"] = []
            if poly_ids:
                m["platforms"].append("Polymarket")
            if kalshi_id:
                m["platforms"].append("Kalshi")
            m["platforms"].append("Predict.fun")
            cross_platform.append(m)
    
    return cross_platform, markets

def save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"data": data, "ts": time.time()}, f, ensure_ascii=False, indent=2)

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE) as f:
            d = json.load(f)
        if time.time() - d.get("ts", 0) > CACHE_TTL:
            return None
        return d["data"]
    except:
        return None
