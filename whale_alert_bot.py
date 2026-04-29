#!/usr/bin/env python3
"""
🐋 NANO Polymarket Whale Alert Bot
Sends Telegram alerts with inline buttons when tracked whales trade.
"""
import asyncio, aiohttp, json, time, os, sys
from datetime import datetime, timezone

BOT_TOKEN = "8375563056:AAHqFtfsxK1zMfKrEBgMTa9d0QcIXVTlYGI"
CHAT_ID = 730668
DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "whale_state.json")

# Full whale addresses from PolyMonit April 2026 leaderboard
WHALES = {
    "0x2a2c53bd278c04da9962fcf96490e17f3dfb9bc1": {"name": "🐋 Кит #1 — kcnyekchno", "vol": "$55.6M", "strat": "NO на геополитику, крупнейший объём", "tier": "whale"},
    "0xdc876e6873772d38716fda7f2452a78d426d7ab6": {"name": "🐋 Кит #2 — 432614799197", "vol": "$20.2M", "strat": "Кросс-категорийный флоу", "tier": "whale"},
    "0x02227b8f5a9636e895607edd3185ed6ee5598ff7": {"name": "🐋 Кит #3 — HorizonSplendidView", "vol": "$6.5M", "strat": "Спорт + макро, +$4M profit April", "tier": "whale"},
    "0x019782cab5d844f02bafb71f512758be78579f3c": {"name": "🐋 Кит #4 — majorexploiter", "vol": "$6.9M", "strat": "Геополитика, политика", "tier": "whale"},
    "0x492442eab586f242b53bda933fd5de859c8a3782": {"name": "🏆 Кит #5 — April #1 (+$6.3M)", "vol": "$24.5M", "strat": "Спорт, ивент-рынки", "tier": "whale"},
    "0xefbc5fec8d7b0acdc8911bdd9a98d6964308f9a2": {"name": "🐋 Кит #6 — reachingthesky", "vol": "$3.7M", "strat": "Спорт, глобальные события", "tier": "whale"},
    "0xc2e7800b5af46e6093872b177b7a5e7f0563be51": {"name": "🐋 Кит #7 — beachboy4", "vol": "$12.4M", "strat": "Спорт, футбол, +$3.5M profit", "tier": "whale"},
    "0xde17f7144fbd0eddb2679132c10ff5e74b120988": {"name": "🐈 Кит #8 — Crypto Leader", "vol": "$727K", "strat": "Крипто, DeFi, +$727K profit", "tier": "dolphin"},
    "0x2005d16a84ceefa912d4e380cd32e7ff827875ea": {"name": "🐋 Кит #9 — RN1", "vol": "$50.9M", "strat": "Хай-волюм ротация", "tier": "whale"},
    "0xbddf61af533ff524d27154e589d2d7a81510c684": {"name": "🐋 Кит #10 — Countryside", "vol": "$14.9M", "strat": "Спорт, турниры, +$1.8M profit", "tier": "whale"},
}

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
    if not address:
        return None
    addr = address.lower()
    for full_addr, info in WHALES.items():
        if addr == full_addr.lower() or addr.startswith(full_addr[:10].lower()):
            return info
    return None

async def send_telegram(text, buttons=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "parse_mode": "Markdown", "text": text, "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as r:
                return (await r.json()).get("ok", False)
    except Exception as e:
        print(f"TG error: {e}")
        return False

async def send_whale_alert(whale, trade):
    side = trade.get("side", "?")
    size = float(trade.get("size", 0) or 0)
    price = float(trade.get("price", 0) or 0)
    vol = size * price
    title = (trade.get("title") or trade.get("market", "?"))[:60]
    outcome = trade.get("outcome", "?")
    slug = trade.get("slug") or trade.get("market_slug", "")
    pseudo = trade.get("pseudonym") or trade.get("taker", whale.get("name", "").split("—")[-1].strip())

    emoji = "🟢" if side == "BUY" else "🔴"
    act = "КУПИЛ" if side == "BUY" else "ПРОДАЛ"
    risk = "🔴 HIGH" if vol > 50000 else "🟡 MED" if vol > 10000 else "🟢 LOW"

    text = f"""🐋 *WHALE ALERT*
═══════════════════════════════════

{whale['name']}
📊 Volume: {whale['vol']}
🧠 Strategy: {whale['strat']}

{emoji} *{act}: {outcome}*
💰 *${vol:,.0f}* ({size:,.0f} shares @ {price:.1f}¢)
📈 *Market:* {title}
👤 {pseudo}
⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}

💡 *Risk:* {risk}
{'⚠️ Крупная позиция — рынок может отреагировать' if vol > 50000 else '📈 Умеренный сигнал'}"""

    btns = [
        [{"text": "📈 Open Market", "url": f"https://polymarket.com/event/{slug}"}],
        [{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}, {"text": "📊 PolyMonit", "url": "https://polymonit.com/leaderboard/polymarket-whales"}],
        [{"text": "🔍 PolyIntel", "url": "https://polyintel.io/"}]
    ]
    await send_telegram(text, btns)

async def check_and_alert(session):
    state = load_state()
    alerts = 0

    # Fetch recent trades
    all_trades = []
    try:
        async with session.get(f"{DATA_API}/trades?limit=500&order=desc") as r:
            all_trades = await r.json()
    except Exception as e:
        print(f"Trades fetch error: {e}")

    # Also check top markets
    try:
        async with session.get(f"{GAMMA_API}/markets?limit=20&order=volume24hr&ascending=false&closed=false") as r:
            markets = await r.json()
            for m in markets[:10]:
                slug = m.get("slug", "")
                if slug:
                    async with session.get(f"{DATA_API}/trades?limit=100&order=desc&slug={slug}") as r2:
                        data = await r2.json()
                        all_trades.extend(data)
    except Exception:
        pass

    # Find whale trades
    for t in all_trades:
        addr = t.get("proxyWallet", "") or t.get("taker", "")
        whale = match_whale(addr)
        if not whale:
            continue

        ts = t.get("timestamp", "") or t.get("created_at", "")
        key = f"{addr}:{ts}"
        if key in state["last_trades"]:
            continue

        vol = float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)
        if vol < 100:
            continue

        await send_whale_alert(whale, t)
        state["last_trades"][key] = time.time()
        state["alerts_sent"] += 1
        alerts += 1

    # Cleanup
    if len(state["last_trades"]) > 2000:
        sorted_k = sorted(state["last_trades"].keys(), key=lambda k: state["last_trades"][k])
        for k in sorted_k[:500]:
            del state["last_trades"][k]

    state["last_check"] = time.time()
    save_state(state)
    return alerts

async def run_once():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        n = await check_and_alert(s)
        print(f"SENT_{n}_ALERTS" if n > 0 else "NO_WHALE_ACTIVITY")

async def run_daemon(interval=300):
    print(f"🐋 Whale Alert Bot started. {len(WHALES)} whales tracked. Interval: {interval}s")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        while True:
            try:
                n = await check_and_alert(s)
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                print(f"[{ts}] {'🐋 ' + str(n) + ' alert(s)' if n else 'No whale activity'}")
            except Exception as e:
                print(f"Error: {e}")
            await asyncio.sleep(interval)

if __name__ == "__main__":
    if "--once" in sys.argv:
        asyncio.run(run_once())
    else:
        asyncio.run(run_daemon())
