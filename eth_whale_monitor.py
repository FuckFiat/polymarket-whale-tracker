#!/usr/bin/env python3
"""
🐋 NANO ETH Whale Monitor — Multi-Exchange
Tracks ETH long/short positions from top traders across all major exchanges.
Integrates with whale_alert_bot for Telegram alerts.
"""
import json, time, os, asyncio, aiohttp
from datetime import datetime, timezone

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "eth_whale_state.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ===== EXCHANGE APIs =====

BINANCE_FAPI = "https://fapi.binance.com"
BYBIT_API = "https://api.bybit.com"
OKX_API = "https://www.okx.com"
HL_API = "https://api.hyperliquid.xyz/info"

# ===== ETH DATA FETCHERS =====

async def fetch_binance_eth(session):
    """Binance Futures: top trader L/S ratio, global L/S ratio, OI, funding"""
    data = {"exchange": "Binance", "symbol": "ETHUSDT", "timestamp": int(time.time())}
    
    try:
        # Top trader long/short position ratio (1h)
        async with session.get(f"{BINANCE_FAPI}/futures/data/topLongShortPositionRatio?symbol=ETHUSDT&period=1h&limit=5", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                ls = await r.json()
                if ls:
                    latest = ls[-1]
                    data["top_long_pct"] = float(latest.get("longAccount", 0)) * 100
                    data["top_short_pct"] = float(latest.get("shortAccount", 0)) * 100
                    data["top_ls_ratio"] = float(latest.get("longShortRatio", 0))
        
        # Global long/short account ratio (1h)
        async with session.get(f"{BINANCE_FAPI}/futures/data/globalLongShortAccountRatio?symbol=ETHUSDT&period=1h&limit=5", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                gls = await r.json()
                if gls:
                    latest = gls[-1]
                    data["global_long_pct"] = float(latest.get("longAccount", 0)) * 100
                    data["global_short_pct"] = float(latest.get("shortAccount", 0)) * 100
                    data["global_ls_ratio"] = float(latest.get("longShortRatio", 0))
        
        # Open interest
        async with session.get(f"{BINANCE_FAPI}/fapi/v1/openInterest?symbol=ETHUSDT", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                oi = await r.json()
                data["open_interest"] = float(oi.get("openInterest", 0))
        
        # Funding rate
        async with session.get(f"{BINANCE_FAPI}/fapi/v1/fundingRate?symbol=ETHUSDT&limit=1", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                fr = await r.json()
                if fr:
                    data["funding_rate"] = float(fr[0].get("fundingRate", 0))
                    data["funding_rate_pct"] = data["funding_rate"] * 100
        
        # Taker buy/sell volume ratio
        async with session.get(f"{BINANCE_FAPI}/futures/data/takerlongshortRatio?symbol=ETHUSDT&period=1h&limit=5", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                tv = await r.json()
                if tv:
                    latest = tv[-1]
                    data["taker_buy_vol"] = float(latest.get("buyVol", 0))
                    data["taker_sell_vol"] = float(latest.get("sellVol", 0))
                    data["taker_ratio"] = float(latest.get("buySellRatio", 0))
        
        data["success"] = True
    except Exception as e:
        data["error"] = str(e)
        data["success"] = False
    
    return data


async def fetch_bybit_eth(session):
    """Bybit: open interest, funding rate"""
    data = {"exchange": "Bybit", "symbol": "ETHUSDT", "timestamp": int(time.time())}
    
    try:
        # Open interest
        async with session.get(f"{BYBIT_API}/v5/market/open-interest?category=linear&symbol=ETHUSDT&intervalTime=1h", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("result", {}).get("list"):
                    latest = resp["result"]["list"][0]
                    data["open_interest"] = float(latest.get("openInterest", 0))
        
        # Funding rate
        async with session.get(f"{BYBIT_API}/v5/market/funding/history?category=linear&symbol=ETHUSDT&limit=3", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("result", {}).get("list"):
                    latest = resp["result"]["list"][0]
                    data["funding_rate"] = float(latest.get("fundingRate", 0))
                    data["funding_rate_pct"] = data["funding_rate"] * 100
        
        data["success"] = True
    except Exception as e:
        data["error"] = str(e)
        data["success"] = False
    
    return data


async def fetch_okx_eth(session):
    """OKX: open interest, long/short ratio"""
    data = {"exchange": "OKX", "symbol": "ETH-USDT-SWAP", "timestamp": int(time.time())}
    
    try:
        # Open interest
        async with session.get(f"{OKX_API}/api/v5/public/open-interest?instType=SWAP&instId=ETH-USDT-SWAP", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("data"):
                    oi_data = resp["data"][0]
                    data["open_interest"] = float(oi_data.get("oi", 0))
                    data["open_interest_usd"] = float(oi_data.get("oiUsd", 0))
        
        # Long/short ratio (position)
        async with session.get(f"{OKX_API}/api/v5/rubik/stat/long-short-position-ratio?instId=ETH-USDT-SWAP&period=1h", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("data"):
                    ratios = resp["data"]
                    if ratios:
                        latest = ratios[-1] if isinstance(ratios[0], list) else ratios[0]
                        data["ls_ratio"] = float(latest[1]) if len(latest) > 1 else 0
        
        # Funding rate
        async with session.get(f"{OKX_API}/api/v5/public/funding-rate?instId=ETH-USDT-SWAP", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("data"):
                    fr_data = resp["data"][0]
                    data["funding_rate"] = float(fr_data.get("fundingRate", 0))
                    data["funding_rate_pct"] = float(fr_data.get("fundingRate", 0)) * 100
                    data["next_funding_time"] = fr_data.get("nextFundingTime", "")
        
        data["success"] = True
    except Exception as e:
        data["error"] = str(e)
        data["success"] = False
    
    return data


async def fetch_hyperliquid_eth(session):
    """Hyperliquid: ETH positions from whale wallets"""
    data = {"exchange": "Hyperliquid", "symbol": "ETH", "timestamp": int(time.time())}
    
    try:
        # Get mid prices
        async with session.post(HL_API, json={"type": "allMids"}, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                mids = await r.json()
                eth_price = float(mids.get("ETH", 0))
                data["eth_price"] = eth_price
        
        # Get open interest for ETH
        async with session.post(HL_API, json={"type": "meta"}, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                meta = await r.json()
                for asset in meta.get("universe", []):
                    if asset.get("name") == "ETH":
                        data["hl_oi"] = float(asset.get("openInterest", 0))
                        data["hl_max_leverage"] = asset.get("maxLeverge", 0)
                        break
        
        data["success"] = True
    except Exception as e:
        data["error"] = str(e)
        data["success"] = False
    
    return data


async def fetch_deribit_eth(session):
    """Deribit: ETH options OI, put/call ratio"""
    data = {"exchange": "Deribit", "symbol": "ETH", "timestamp": int(time.time())}
    
    try:
        # Get ETH options summary
        async with session.get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=ETH&kind=option", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("result"):
                    total_call_oi = 0
                    total_put_oi = 0
                    total_call_vol = 0
                    total_put_vol = 0
                    for opt in resp["result"]:
                        if opt.get("instrument_name", "").startswith("ETH-"):
                            oi = float(opt.get("open_interest", 0))
                            vol = float(opt.get("volume", 0))
                            if opt.get("instrument_name", "").find("-C-") > 0:
                                total_call_oi += oi
                                total_call_vol += vol
                            elif opt.get("instrument_name", "").find("-P-") > 0:
                                total_put_oi += oi
                                total_put_vol += vol
                    
                    data["call_oi"] = total_call_oi
                    data["put_oi"] = total_put_oi
                    data["put_call_ratio"] = total_put_oi / total_call_oi if total_call_oi > 0 else 0
                    data["call_volume"] = total_call_vol
                    data["put_volume"] = total_put_vol
        
        # Get ETH futures OI
        async with session.get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=ETH&kind=future", timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("result"):
                    total_fut_oi = sum(float(f.get("open_interest", 0)) for f in resp["result"])
                    data["futures_oi"] = total_fut_oi
        
        data["success"] = True
    except Exception as e:
        data["error"] = str(e)
        data["success"] = False
    
    return data


# ===== AGGREGATOR =====

async def fetch_all_eth_data(session=None):
    """Fetch ETH data from ALL exchanges simultaneously"""
    close_session = False
    if session is None:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        close_session = True
    
    try:
        results = await asyncio.gather(
            fetch_binance_eth(session),
            fetch_bybit_eth(session),
            fetch_okx_eth(session),
            fetch_hyperliquid_eth(session),
            fetch_deribit_eth(session),
            return_exceptions=True
        )
        
        aggregated = {
            "timestamp": int(time.time()),
            "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "exchanges": {}
        }
        
        for result in results:
            if isinstance(result, Exception):
                continue
            exchange = result.get("exchange", "unknown")
            aggregated["exchanges"][exchange] = result
        
        # Compute aggregate metrics
        total_oi_usd = 0
        all_ls_ratios = []
        all_funding = []
        
        bn = aggregated["exchanges"].get("Binance", {})
        if bn.get("success"):
            if bn.get("top_ls_ratio"):
                all_ls_ratios.append(("Binance Top", bn["top_ls_ratio"]))
            if bn.get("global_ls_ratio"):
                all_ls_ratios.append(("Binance Global", bn["global_ls_ratio"]))
            if bn.get("open_interest"):
                total_oi_usd += bn["open_interest"] * bn.get("eth_price", 2300)  # approximate
            if bn.get("funding_rate_pct"):
                all_funding.append(("Binance", bn["funding_rate_pct"]))
        
        bybit = aggregated["exchanges"].get("Bybit", {})
        if bybit.get("success"):
            if bybit.get("open_interest"):
                total_oi_usd += bybit["open_interest"] * 2300  # ETH price approx
        
        okx = aggregated["exchanges"].get("OKX", {})
        if okx.get("success"):
            if okx.get("open_interest_usd"):
                total_oi_usd += okx["open_interest_usd"]
            if okx.get("ls_ratio"):
                all_ls_ratios.append(("OKX", okx["ls_ratio"]))
            if okx.get("funding_rate_pct"):
                all_funding.append(("OKX", okx["funding_rate_pct"]))
        
        hl = aggregated["exchanges"].get("Hyperliquid", {})
        if hl.get("success"):
            if hl.get("eth_price"):
                aggregated["eth_price"] = hl["eth_price"]
        
        deribit = aggregated["exchanges"].get("Deribit", {})
        if deribit.get("success"):
            if deribit.get("put_call_ratio"):
                all_ls_ratios.append(("Deribit P/C", deribit["put_call_ratio"]))
        
        aggregated["total_oi_usd"] = total_oi_usd
        aggregated["ls_ratios"] = all_ls_ratios
        aggregated["funding_rates"] = all_funding
        
        return aggregated
    finally:
        if close_session:
            await session.close()


# ===== FORMATTERS =====

def format_eth_summary(data):
    """Format ETH whale data for Telegram"""
    lines = []
    lines.append("🔮 *ETH КИТОВЫЙ МОНИТОР*")
    lines.append("═══════════════════════════════════")
    
    eth_price = data.get("eth_price", 0)
    if eth_price:
        lines.append(f"💰 ETH: *${eth_price:,.2f}*")
    
    lines.append("")
    
    # L/S Ratios
    ls_ratios = data.get("ls_ratios", [])
    if ls_ratios:
        lines.append("📊 *Long/Short Ratio:*")
        for name, ratio in ls_ratios:
            if "P/C" in name:
                # Put/Call ratio — inverse logic
                if ratio > 1:
                    emoji = "🔴"  # More puts = bearish
                    sentiment = "МЕДВЕЖИЙ"
                else:
                    emoji = "🟢"  # More calls = bullish
                    sentiment = "БЫЧИЙ"
                lines.append(f"  {emoji} {name}: {ratio:.4f} ({sentiment})")
            else:
                if ratio > 1.5:
                    emoji = "🟢🟢"
                elif ratio > 1.2:
                    emoji = "🟢"
                elif ratio > 1.0:
                    emoji = "🟡"
                elif ratio > 0.8:
                    emoji = "🔴"
                else:
                    emoji = "🔴🔴"
                lines.append(f"  {emoji} {name}: {ratio:.4f}")
    
    # Funding rates
    funding = data.get("funding_rates", [])
    if funding:
        lines.append("")
        lines.append("💸 *Funding Rate:*")
        for name, rate in funding:
            if rate > 0.01:
                emoji = "🔥"
            elif rate > 0:
                emoji = "🟢"
            elif rate > -0.01:
                emoji = "🟡"
            else:
                emoji = "🔴"
            lines.append(f"  {emoji} {name}: {rate:+.4f}%")
    
    # Per-exchange details
    lines.append("")
    lines.append("🏦 *По биржам:*")
    
    bn = data.get("exchanges", {}).get("Binance", {})
    if bn.get("success"):
        lines.append(f"  *Binance:*")
        lines.append(f"    OI: {bn.get('open_interest', 0):,.0f} ETH")
        if bn.get("taker_ratio"):
            lines.append(f"    Taker B/S: {bn.get('taker_ratio', 0):.4f}")
        if bn.get("top_long_pct"):
            lines.append(f"    Топ-трейдеры: {bn['top_long_pct']:.1f}% 🟢 / {bn.get('top_short_pct', 0):.1f}% 🔴")
        if bn.get("global_long_pct"):
            lines.append(f"    Глобально: {bn['global_long_pct']:.1f}% 🟢 / {bn.get('global_short_pct', 0):.1f}% 🔴")
    
    okx = data.get("exchanges", {}).get("OKX", {})
    if okx.get("success"):
        lines.append(f"  *OKX:*")
        if okx.get("open_interest_usd"):
            lines.append(f"    OI: ${okx['open_interest_usd']:,.0f}")
    
    bybit = data.get("exchanges", {}).get("Bybit", {})
    if bybit.get("success"):
        lines.append(f"  *Bybit:*")
        if bybit.get("open_interest"):
            lines.append(f"    OI: {bybit['open_interest']:,.0f} ETH")
    
    deribit = data.get("exchanges", {}).get("Deribit", {})
    if deribit.get("success"):
        lines.append(f"  *Deribit:*")
        if deribit.get("call_oi"):
            lines.append(f"    Call OI: {deribit['call_oi']:,.0f}")
        if deribit.get("put_oi"):
            lines.append(f"    Put OI: {deribit['put_oi']:,.0f}")
        if deribit.get("put_call_ratio"):
            lines.append(f"    P/C Ratio: {deribit['put_call_ratio']:.4f}")
    
    hl = data.get("exchanges", {}).get("Hyperliquid", {})
    if hl.get("success") and hl.get("hl_oi"):
        lines.append(f"  *Hyperliquid:*")
        lines.append(f"    OI: {hl['hl_oi']:,.0f} ETH")
    
    # Total OI
    total_oi = data.get("total_oi_usd", 0)
    if total_oi > 0:
        lines.append("")
        lines.append(f"💎 *Total ETH OI: ${total_oi/1e9:.2f}B*")
    
    # Sentiment
    lines.append("")
    avg_ls = 0
    non_pc_ratios = [r for n, r in ls_ratios if "P/C" not in n]
    if non_pc_ratios:
        avg_ls = sum(non_pc_ratios) / len(non_pc_ratios)
    
    if avg_ls > 1.5:
        sentiment = "🟢🟢 ЭКСТРЕМАЛЬНО БЫЧИЙ — шорт-сквиз возможен"
    elif avg_ls > 1.2:
        sentiment = "🟢 БЫЧИЙ — киты лонгуют"
    elif avg_ls > 1.0:
        sentiment = "🟡 Слегка бычий — лонги доминируют"
    elif avg_ls > 0.8:
        sentiment = "🟡 Нейтрально-медвежий"
    else:
        sentiment = "🔴 МЕДВЕЖИЙ — киты шортят"
    
    lines.append(f"📈 *Сентимент:* {sentiment}")
    lines.append(f"📊 Средний L/S: {avg_ls:.4f}")
    lines.append(f"⏰ {data.get('time_utc', '')}")
    
    return "\n".join(lines)


def format_eth_compact(data):
    """Compact format for quick alerts"""
    eth_price = data.get("eth_price", 0)
    ls_ratios = data.get("ls_ratios", [])
    funding = data.get("funding_rates", [])
    
    parts = []
    if eth_price:
        parts.append(f"ETH ${eth_price:,.0f}")
    
    for name, ratio in ls_ratios[:3]:
        emoji = "🟢" if ratio > 1 else "🔴"
        parts.append(f"{emoji}{name}:{ratio:.3f}")
    
    for name, rate in funding[:2]:
        emoji = "🔥" if rate > 0.01 else "🟢" if rate > 0 else "🔴"
        parts.append(f"{emoji}F:{name}:{rate:+.4f}%")
    
    return " | ".join(parts) if parts else "No data"


def load_eth_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_check": 0, "history": [], "alerts_sent": 0}

def save_eth_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    async def test():
        data = await fetch_all_eth_data()
        print(format_eth_summary(data))
        print("\n--- COMPACT ---")
        print(format_eth_compact(data))
    
    asyncio.run(test())