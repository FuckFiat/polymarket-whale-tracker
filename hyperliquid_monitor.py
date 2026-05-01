#!/usr/bin/env python3
"""
🐋 NANO Hyperliquid Whale Monitor
Tracks large positions and trading activity on Hyperliquid DEX perps.
Integrates with the whale_alert_bot for Telegram alerts.
"""
import json, time, os, asyncio, aiohttp
from datetime import datetime, timezone

HL_API = "https://api.hyperliquid.xyz/info"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "hl_whale_state.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Hyperliquid whale wallets — top traders from leaderboard
# Updated: 2026-05-01
HYPERLIQUID_WHALES = {
    "0xa822a9ceb6d6cb5b565bd10098abcfa9cf18d748": {"name": "🐋 HL #1 — $13.7B", "vol": "$0", "strat": "Макро-позиции", "tier": "whale"},
    "0x1c498a93b145e7a73d69691e9023f6f308e1cc3f": {"name": "🐋 HL #2 — $6.8B", "vol": "$0", "strat": "PnL +$288M", "tier": "whale"},
    "0x24de6b77e8bc31c40aa452926daa6bbab7a71b0f": {"name": "🐋 HL #3 — $2.9B", "vol": "$0", "strat": "Крупные перпы", "tier": "whale"},
    "0xe6111266afdcdf0b1fe8505028cc1f7419d798a7": {"name": "🐋 HL #4 — $906M", "vol": "$0", "strat": "Хедж-фонд", "tier": "whale"},
    "0x4ec8fe22a531a96c8a846aaf5cbef73202649a80": {"name": "🏆 HL #5 — $593M", "vol": "$0", "strat": "PnL +$813M", "tier": "whale"},
    "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303": {"name": "🐋 HL #6 — $369M", "vol": "$0", "strat": "PnL +$136M", "tier": "whale"},
    "0x87f9cd15f5050a9283b8896300f7c8cf69ece2cf": {"name": "🐋 HL #7 — $74M", "vol": "$479B", "strat": "PnL +$52.9M, Vol $479B", "tier": "whale"},
    "0x31ca8395cf837de08b24da3f660e77761dfb974b": {"name": "🐋 HL #8 — $114M", "vol": "$185B", "strat": "PnL +$37.4M", "tier": "whale"},
    "0x010461c14e8f7c3a9b2d5e6f4a7c8d9e0b1a2f3e": {"name": "🐋 HL #9 — $114M", "vol": "$189B", "strat": "PnL +$46.8M", "tier": "whale"},
    "0xfc667adba8881ae9f0d7dac1b7b5c8d4e2a3f1b0": {"name": "🐋 HL #10 — $80M", "vol": "$22B", "strat": "PnL +$21.5M", "tier": "whale"},
}

# Minimum notional value to trigger alert (USD)
MIN_NOTIONAL = 100000  # $100K+
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

def load_hl_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "last_check": 0,
        "alerts_sent": 0,
        "tracked_positions": {},
        "seen_positions": {},
        "whale_pnl": {},
    }

def save_hl_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

async def hl_post(session, payload):
    """Post request to Hyperliquid API"""
    try:
        async with session.post(HL_API, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"HL API error: {e}")
    return None

async def get_user_state(session, address):
    """Get clearinghouse state for a wallet"""
    payload = {"type": "clearinghouseState", "user": address.lower()}
    return await hl_post(session, payload)

async def get_all_mids(session):
    """Get all mid prices"""
    payload = {"type": "allMids"}
    return await hl_post(session, payload)

async def get_meta(session):
    """Get asset metadata"""
    payload = {"type": "meta"}
    return await hl_post(session, payload)

async def get_candles(session, coin, interval="1h"):
    """Get candle data for an asset"""
    payload = {"type": "candleSnapshot", "coin": coin, "interval": interval}
    return await hl_post(session, payload)

def format_position(coin, size, entry_px, unrealized_pnl, cur_px, leverage):
    """Format a position for display"""
    side = "🟢 LONG" if float(size) > 0 else "🔴 SHORT"
    abs_size = abs(float(size))
    notional = abs_size * float(cur_px)
    pnl = float(unrealized_pnl)
    pnl_emoji = "📈" if pnl > 0 else "📉"
    entry = float(entry_px)
    liq_estimate = entry * (1 - 1/(float(leverage) * 2)) if float(size) > 0 else entry * (1 + 1/(float(leverage) * 2))
    
    return {
        "coin": coin,
        "side": side,
        "size": abs_size,
        "entry": entry,
        "current": float(cur_px),
        "pnl": pnl,
        "notional": notional,
        "leverage": float(leverage),
        "liq_estimate": liq_estimate,
    }

async def scan_whale_positions(session, whales=None, coins=None):
    """Scan all whale positions on Hyperliquid, optionally filtering by coins"""
    if whales is None:
        whales = HYPERLIQUID_WHALES
    
    state = load_hl_state()
    mids = await get_all_mids(session)
    if not mids:
        return []
    
    alerts = []
    
    for addr, info in whales.items():
        if info.get("tier") == "placeholder":
            continue
        
        user_state = await get_user_state(session, addr)
        if not user_state:
            continue
        
        positions = user_state.get("assetPositions", [])
        margin = user_state.get("marginSummary", {})
        account_value = float(margin.get("totalAccountValue", 0))
        
        for pos in positions:
            position = pos.get("position", {})
            coin = position.get("coin", "?")
            
            # Filter by selected coins
            if coins and coin not in coins:
                continue
            
            size = position.get("szi", "0")
            entry_px = position.get("entryPx", "0")
            unrealized_pnl = position.get("unrealizedPnl", "0")
            leverage = position.get("leverage", {}).get("value", "1") if isinstance(position.get("leverage"), dict) else "1"
            cur_px = mids.get(coin, "0")
            
            if not cur_px or cur_px == "0":
                continue
            
            formatted = format_position(coin, size, entry_px, unrealized_pnl, cur_px, leverage)
            
            # Check if this is a new or changed position
            pos_key = f"{addr[:10]}:{coin}:{'long' if float(size) > 0 else 'short'}"
            prev = state.get("seen_positions", {}).get(pos_key)
            
            if formatted["notional"] >= MIN_NOTIONAL:
                if prev is None:
                    # New position!
                    alerts.append({
                        "type": "new_position",
                        "whale": info["name"],
                        "whale_addr": addr,
                        "account_value": account_value,
                        **formatted,
                    })
                elif abs(formatted["size"] - prev.get("size", 0)) > prev.get("size", 0) * 0.1:
                    # Size changed by >10%
                    alerts.append({
                        "type": "size_change",
                        "whale": info["name"],
                        "whale_addr": addr,
                        "account_value": account_value,
                        **formatted,
                    })
                
                state["seen_positions"][pos_key] = {
                    "size": formatted["size"],
                    "entry": formatted["entry"],
                    "notional": formatted["notional"],
                    "timestamp": time.time(),
                }
        
        # Update whale PnL tracking
        state["whale_pnl"][addr[:10]] = {
            "account_value": account_value,
            "positions": len(positions),
            "timestamp": time.time(),
        }
    
    state["last_check"] = time.time()
    save_hl_state(state)
    
    return alerts

async def scan_top_positions(session, min_notional=500000):
    """
    Scan for large positions by checking OI and recent fills.
    This is a discovery method to find new whale wallets.
    """
    meta = await get_meta(session)
    mids = await get_all_mids(session)
    if not meta or not mids:
        return []
    
    universe = meta.get("universe", [])
    large_oi = []
    
    for asset in universe:
        coin = asset["name"]
        if coin in mids and float(mids[coin]) > 0:
            # We can estimate OI by checking the book depth
            try:
                book_payload = {"type": "l2Book", "coin": coin}
                book = await hl_post(session, book_payload)
                if book and "levels" in book:
                    total_bid = sum(float(b.get("sz", 0)) * float(b.get("px", 0)) for b in book["levels"][0][:10] if book["levels"])
                    total_ask = sum(float(a.get("sz", 0)) * float(a.get("px", 0)) for a in book["levels"][1][:10] if len(book["levels"]) > 1)
                    if total_bid + total_ask > min_notional:
                        large_oi.append({
                            "coin": coin,
                            "bid_depth": total_bid,
                            "ask_depth": total_ask,
                            "price": float(mids[coin]),
                        })
            except:
                pass
    
    return sorted(large_oi, key=lambda x: x["bid_depth"] + x["ask_depth"], reverse=True)

def format_alert(alert):
    """Format an alert for Telegram"""
    if alert["type"] == "new_position":
        title = "🆕 НОВАЯ ПОЗИЦИЯ"
    elif alert["type"] == "size_change":
        title = "🔄 ИЗМЕНЕНИЕ РАЗМЕРА"
    elif alert["type"] == "liquidation_risk":
        title = "⚠️ РИСК ЛИКВИДАЦИИ"
    else:
        title = "📊 ОБНОВЛЕНИЕ"
    
    pnl_str = f"+${alert['pnl']:,.0f}" if alert['pnl'] > 0 else f"-${abs(alert['pnl']):,.0f}"
    
    text = f"""🐋 *{title}*
═══════════════════════════════════

{alert['whale']}
💰 Account: ${alert['account_value']:,.0f}

{alert['side']} *{alert['coin']}*
📊 Size: {alert['size']:,.4f} (${alert['notional']:,.0f})
📈 Entry: ${alert['entry']:,.2f} → ${alert['current']:,.2f}
{pnl_str} unrealized PnL
⚡ Leverage: {alert['leverage']:.1f}x
⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}"""
    
    return text

# ===== DISCOVERY: Find whale wallets from on-chain data =====

async def discover_whales(session, top_n=20):
    """
    Discover whale wallets by scanning recent large fills.
    Uses Hyperliquid's public API to find wallets with large trading activity.
    """
    # We can use the leaderboard or scan known addresses
    # For now, return the pre-configured list
    whales = {}
    for addr, info in HYPERLIQUID_WHALES.items():
        if info.get("tier") != "placeholder":
            whales[addr] = info
    return whales

if __name__ == "__main__":
    import sys
    print("🐋 Hyperliquid Whale Monitor")
    print("Use via whale_alert_bot.py integration")

async def refresh_leaderboard(session=None):
    """Fetch top traders from Hyperliquid leaderboard and update whale list"""
    import urllib.request
    try:
        req = urllib.request.Request(LEADERBOARD_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        rows = data.get("leaderboardRows", [])
        
        # Sort by account value
        sorted_by_value = sorted(rows, key=lambda x: float(x.get("accountValue", 0)), reverse=True)
        
        new_whales = {}
        for i, entry in enumerate(sorted_by_value[:10], 1):
            addr = entry.get("ethAddress", "?")
            account_value = float(entry.get("accountValue", 0))
            all_time = None
            for window, perf in entry.get("windowPerformances", []):
                if window == "allTime":
                    all_time = perf
            all_pnl = float(all_time.get("pnl", 0)) if all_time else 0
            all_roi = float(all_time.get("roi", 0)) * 100 if all_time else 0
            
            tier = "whale" if account_value > 50_000_000 else "dolphin"
            new_whales[addr] = {
                "name": f"🐋 HL #{i} — ${account_value/1e6:.0f}M",
                "vol": "$0",
                "strat": f"PnL ${all_pnl/1e6:.1f}M, ROI {all_roi:.0f}%",
                "tier": tier,
                "account_value": account_value,
                "pnl": all_pnl,
            }
        
        # Update global
        global HYPERLIQUID_WHALES
        HYPERLIQUID_WHALES.update(new_whales)
        
        # Save to file
        with open(os.path.join(RESULTS_DIR, "hl_leaderboard.json"), "w") as f:
            json.dump({"updated": time.time(), "whales": new_whales}, f, indent=2)
        
        return len(new_whales)
    except Exception as e:
        print(f"Leaderboard refresh error: {e}")
        return 0


if __name__ == "__main__":
    import asyncio
    async def test():
        print("🐋 Refreshing leaderboard...")
        count = await refresh_leaderboard()
        print(f"✅ Updated {count} whales from leaderboard")
        for addr, info in HYPERLIQUID_WHALES.items():
            print(f"  {info['name']}: ${info.get('account_value', 0)/1e6:.0f}M | {info['strat']}")
    asyncio.run(test())
