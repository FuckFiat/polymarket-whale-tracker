#!/usr/bin/env python3
"""
🐋 NANO Polymarket Whale Alert Bot
Telegram bot with inline buttons for whale tracking alerts.
"""

import asyncio
import aiohttp
import json
import time
import os
import sys
from datetime import datetime

# === CONFIG ===
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8375563056:AAHqFtfsxK1zMfKrEBgMTa9d0QcIXVTlYGI")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "730668"))
DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "whale_state.json")

WHALE_ADDRESSES = {
    "0x2a2c": {"name": "🐋 Кит #1 — Геополитик-контрариан", "volume": "$26.3M", "strategy": "NO на геополитику, контрариан"},
    "0xdc87": {"name": "🐋 Кит #2 — Mega Whale", "volume": "$20.2M", "strategy": "Крупные ставки на крипто"},
    "0xe90b": {"name": "🐈 Кит #3 — Крипто-оракул", "volume": "$12.1M", "strategy": "15min крипто-направление"},
    "0x0197": {"name": "🐋 Кит #4 — majorexploiter", "volume": "$6.9M", "strategy": "Арбитраж"},
    "0x0222": {"name": "🐋 Кит #5 — HorizonSplendidView", "volume": "$6.5M", "strategy": "Макро-ставки"},
    "0x07b8": {"name": "🐋 Кит #6 — joosangyoo", "volume": "$5.5M", "strategy": "Спорт"},
    "0xb904": {"name": "🐋 Кит #7 — MinorKey4", "volume": "$5.1M", "strategy": "Длинные позиции"},
    "0xc2e7": {"name": "🐠 Кит #8 — beachboy4", "volume": "$3.5M", "strategy": "Микро-капы"},
    "0xb45a": {"name": "🐠 Кит #9 — bcda", "volume": "$3.2M", "strategy": "Стабильные рынки"},
    "0x916f": {"name": "🐠 Кит #10 — WoofMaster", "volume": "$1.5M", "strategy": "Хай-ризк ставки"},
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
    addr_lower = address.lower()
    for prefix, info in WHALE_ADDRESSES.items():
        if addr_lower.startswith(prefix.lower()):
            return info
    return None


async def send_telegram(text, inline_keyboard=None):
    """Send message via Telegram Bot API with optional inline buttons."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "parse_mode": "Markdown",
        "text": text,
        "disable_web_page_preview": True,
    }
    if inline_keyboard:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
            if not result.get("ok"):
                print(f"Telegram error: {result}")
            return result.get("ok", False)


def build_whale_alert(whale_info, trade):
    """Build rich whale alert with analysis."""
    side = trade.get("side", "?")
    size = float(trade.get("size", 0) or 0)
    price = float(trade.get("price", 0) or 0)
    vol = size * price
    title = trade.get("title", "Unknown market")[:60]
    outcome = trade.get("outcome", "?")
    slug = trade.get("slug", "")
    pseudo = trade.get("pseudonym", "anon")
    ts = trade.get("timestamp", "")

    side_emoji = "🟢" if side == "BUY" else "🔴"
    side_text = "КУПИЛ" if side == "BUY" else "ПРОДАЛ"

    # Risk assessment
    if vol > 50000:
        risk = "🔴 HIGH"
        risk_desc = "Огромная ставка — рынок может отреагировать"
    elif vol > 10000:
        risk = "🟡 MEDIUM"
        risk_desc = "Значительная позиция — следи за рынком"
    else:
        risk = "🟢 LOW"
        risk_desc = "Средний трейд — мониторинг"

    # Strategy match analysis
    strategy = whale_info.get("strategy", "Неизвестно")
    is_typical = "✅ Типичная стратегия" if any(kw in strategy.lower() for kw in ["контрариан", "крипто", "геополи"]) else "🤔 Необычная позиция для кита"

    text = f"""🐋 *WHALE ALERT*
═══════════════════════════════════

🐳 {whale_info['name']}
📊 All-time volume: {whale_info['volume']}

{side_emoji} *{side_text}: {outcome}*
💰 *${vol:,.0f}* ({size:,.0f} shares @ {price:.1f}¢)
📈 *Market:* {title}
🎯 *Outcome:* {outcome} @ {price:.1f}¢
👤 Pseudonym: `{pseudo}`
⏰ {ts}

📊 *АНАЛИЗ:*
├─ {is_typical} — {strategy}
├─ 💰 ${vol:,.0f} — {"крупная" if vol > 10000 else "средняя"} позиция
├─ {risk} — {risk_desc}
└─ 🧠 Стратегия кита: {strategy}

💡 *Что делать:*
├─ {"Сильный сигнал — кит уверен" if vol > 50000 else "Умеренный сигнал — следи"}
└─ {risk} Риск"""

    buttons = [
        [{"text": "📈 View Market", "url": f"https://polymarket.com/event/{slug}"}],
        [
            {"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"},
            {"text": "📊 Whale Profile", "url": "https://polymonit.com/leaderboard/polymarket-whales"}
        ],
        [{"text": "🔍 PolyIntel", "url": "https://polyintel.io/"}]
    ]

    return text, buttons


def build_cluster_alert(trades, market_title, slug):
    """Build cluster signal alert when 3+ whales in same market."""
    whales = {}
    total_vol = 0
    for t in trades:
        addr = t.get("proxyWallet", "")
        w = match_whale(addr)
        if w:
            wid = w["name"]
            if wid not in whales:
                whales[wid] = {"trades": [], "volume": 0, "strategy": w["strategy"]}
            vol = float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)
            whales[wid]["trades"].append(t)
            whales[wid]["volume"] += vol
            total_vol += vol

    # Determine consensus
    yes_count = sum(1 for t in trades if t.get("outcome") == "YES")
    no_count = len(trades) - yes_count
    consensus = "YES" if yes_count > no_count else "NO"
    consensus_pct = max(yes_count, no_count) / len(trades) * 100

    text = f"""🔥 *CLUSTER SIGNAL*
═══════════════════════════════════

{len(whales)} 🐋 *КИТОВ в одном рынке за 2ч!*

📈 *Market:* {market_title[:60]}
💰 Combined volume: *${total_vol:,.0f}*

📊 *Consensus:* {consensus_pct:.0f}% на {consensus}
├─ 🟢 YES: {yes_count} китов
└─ 🔴 NO: {no_count} китов

⚠️ *Это сильный Consensus-сигнал!*
Несколько китов независимо делают одну ставку —
вероятность прибыли выше средней.

💡 Следи за рынком — входи после стабилизации цены."""

    buttons = [
        [{"text": "📈 View Market", "url": f"https://polymarket.com/event/{slug}"}],
        [
            {"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"},
            {"text": "🔥 Cluster View", "url": "https://polyintel.io/"}
        ]
    ]

    return text, buttons


async def check_whales(session):
    """Check for whale trades and send alerts."""
    state = load_state()
    alerts_sent = 0

    # Fetch top markets
    try:
        async with session.get(f"{GAMMA_API}/markets?limit=30&order=volume24hr&ascending=false&closed=false") as resp:
            markets = await resp.json()
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return 0

    # Fetch global trades
    all_trades = []
    try:
        async with session.get(f"{DATA_API}/trades?limit=500&order=desc") as resp:
            all_trades = await resp.json()
    except Exception as e:
        print(f"Error fetching trades: {e}")

    # Fetch per-market trades for top 5
    for m in markets[:5]:
        slug = m.get("slug", "")
        if slug:
            try:
                async with session.get(f"{DATA_API}/trades?limit=200&order=desc&slug={slug}") as resp:
                    all_trades.extend(await resp.json())
            except Exception:
                pass

    # Find whale trades
    whale_trades_by_market = {}
    for t in all_trades:
        addr = t.get("proxyWallet", "")
        whale_info = match_whale(addr)
        if not whale_info:
            continue

        ts_key = f"{addr}:{t.get('timestamp', '')}"
        if ts_key in state["last_trades"]:
            continue

        vol = float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)
        if vol < 100:
            continue

        # New whale trade!
        text, buttons = build_whale_alert(whale_info, t)
        await send_telegram(text, buttons)
        state["last_trades"][ts_key] = time.time()
        state["alerts_sent"] += 1
        alerts_sent += 1

        # Track for cluster detection
        slug = t.get("slug", "")
        if slug not in whale_trades_by_market:
            whale_trades_by_market[slug] = []
        whale_trades_by_market[slug].append(t)

    # Check for cluster signals
    for slug, trades in whale_trades_by_market.items():
        unique_whales = set(t.get("proxyWallet", "")[:6] for t in trades)
        if len(unique_whales) >= 3:
            title = trades[0].get("title", slug) if trades else slug
            text, buttons = build_cluster_alert(trades, title, slug)
            await send_telegram(text, buttons)
            alerts_sent += 1

    # Clean old entries (keep last 1000)
    if len(state["last_trades"]) > 1000:
        sorted_keys = sorted(state["last_trades"].keys(), key=lambda k: state["last_trades"][k])
        for k in sorted_keys[:200]:
            del state["last_trades"][k]

    state["last_check"] = time.time()
    save_state(state)
    return alerts_sent


async def run_once():
    """Single check for cron mode."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        count = await check_whales(session)
        if count == 0:
            print("NO_WHALE_ACTIVITY")
        else:
            print(f"SENT_{count}_ALERTS")


async def run_daemon(interval=300):
    """Continuous daemon mode."""
    print(f"🐋 Whale Alert Bot started. Checking every {interval}s")
    print(f"📋 Tracking {len(WHALE_ADDRESSES)} whale addresses")
    print(f"📱 Sending to chat_id {CHAT_ID}")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        while True:
            try:
                count = await check_whales(session)
                ts = datetime.utcnow().strftime("%H:%M:%S UTC")
                if count > 0:
                    print(f"[{ts}] 🐋 Sent {count} alert(s)")
                else:
                    print(f"[{ts}] No whale activity")
            except Exception as e:
                print(f"Error: {e}")

            await asyncio.sleep(interval)


if __name__ == "__main__":
    if "--once" in sys.argv:
        asyncio.run(run_once())
    elif "--daemon" in sys.argv:
        asyncio.run(run_daemon())
    else:
        asyncio.run(run_daemon())