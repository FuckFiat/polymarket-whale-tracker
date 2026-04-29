#!/usr/bin/env python3
"""
🐋 NANO Polymarket Whale Alert Bot
Interactive Telegram bot with commands + automatic whale monitoring.
"""
import asyncio, aiohttp, json, time, os, sys
from datetime import datetime, timezone

BOT_TOKEN = "8375563056:AAHqFtfsxK1zMfKrEBgMTa9d0QcIXVTlYGI"
CHAT_ID = 730668
DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "whale_state.json")

WHALES = {
    "0x2a2c53bd278c04da9962fcf96490e17f3dfb9bc1": {"name": "🐋 Кит #1 — kcnyekchno", "vol": "$55.6M", "strat": "NO на геополитику", "tier": "whale"},
    "0xdc876e6873772d38716fda7f2452a78d426d7ab6": {"name": "🐋 Кит #2 — 432614799197", "vol": "$20.2M", "strat": "Кросс-категорийный", "tier": "whale"},
    "0x02227b8f5a9636e895607edd3185ed6ee5598ff7": {"name": "🐋 Кит #3 — HorizonSplendidView", "vol": "$6.5M", "strat": "Спорт + макро", "tier": "whale"},
    "0x019782cab5d844f02bafb71f512758be78579f3c": {"name": "🐋 Кит #4 — majorexploiter", "vol": "$6.9M", "strat": "Геополитика", "tier": "whale"},
    "0x492442eab586f242b53bda933fd5de859c8a3782": {"name": "🏆 Кит #5 — April #1", "vol": "$24.5M", "strat": "Спорт, ивенты", "tier": "whale"},
    "0xefbc5fec8d7b0acdc8911bdd9a98d6964308f9a2": {"name": "🐋 Кит #6 — reachingthesky", "vol": "$3.7M", "strat": "Спорт", "tier": "whale"},
    "0xc2e7800b5af46e6093872b177b7a5e7f0563be51": {"name": "🐋 Кит #7 — beachboy4", "vol": "$12.4M", "strat": "Спорт, футбол", "tier": "whale"},
    "0xde17f7144fbd0eddb2679132c10ff5e74b120988": {"name": "🐈 Кит #8 — Crypto Leader", "vol": "$727K", "strat": "Крипто, DeFi", "tier": "dolphin"},
    "0x2005d16a84ceefa912d4e380cd32e7ff827875ea": {"name": "🐋 Кит #9 — RN1", "vol": "$50.9M", "strat": "Хай-волюм ротация", "tier": "whale"},
    "0xbddf61af533ff524d27154e589d2d7a81510c684": {"name": "🐋 Кит #10 — Countryside", "vol": "$14.9M", "strat": "Спорт, турниры", "tier": "whale"},
}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_trades": {}, "last_check": 0, "alerts_sent": 0, "last_activity": {}}

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

async def tg_send(text, buttons=None, chat_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id or CHAT_ID, "parse_mode": "Markdown", "text": text, "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as r:
                return (await r.json()).get("ok", False)
    except Exception as e:
        print(f"TG send error: {e}")
        return False

async def tg_answer_callback(callback_id, text=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"callback_query_id": callback_id, "text": text}) as r:
                return (await r.json()).get("ok", False)
    except Exception:
        return False

# ===== COMMANDS =====

async def cmd_start(chat_id):
    text = """🐋 *NANO Polymarket Whale Tracker*

Отслеживаю топ-10 китов Polymarket в реальном времени.

*Команды:*
/whales — Список отслеживаемых китов
/status — Статус бота и последняя активность
/markets — Топ рынки Polymarket прямо сейчас
/check — Проверить китов вручную
/help — Помощь

Алерты прилетают автоматически когда киты торгуют 🐋"""
    btns = [[{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}],
            [{"text": "📊 PolyMonit", "url": "https://polymonit.com/leaderboard/polymarket-whales"}, {"text": "🔍 PolyIntel", "url": "https://polyintel.io/"}]]
    await tg_send(text, btns, chat_id)

async def cmd_help(chat_id):
    text = """🐋 *Команды бота:*

/start — Приветствие
/whales — Список отслеживаемых китов
/status — Статус бота
/markets — Топ рынки Polymarket
/check — Проверить китов вручную
/help — Эта справка

*Как это работает:*
Бот проверяет китов каждые 5 минут.
Когда кит делает ставку >$100 — прилетает алерт с кнопками.

*Стратегии:*
🐋 Следуй за убеждённостью (крупные ставки)
🔥 Cluster = 3+ кита в одном рынке
⏰ Входи после стабилизации цены"""
    await tg_send(text, chat_id=chat_id)

async def cmd_whales(chat_id):
    text = "🐋 *Отслеживаемые киты:*\n═══════════════════════════════════\n\n"
    for i, (addr, w) in enumerate(WHALES.items(), 1):
        short = addr[:8] + "..." + addr[-4:]
        text += f"{w['name']}\n📊 {w['vol']} | 🧠 {w['strat']}\n🔑 `{short}`\n\n"
    btns = [[{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}],
            [{"text": "📊 PolyMonit", "url": "https://polymonit.com/leaderboard/polymarket-whales"}]]
    await tg_send(text, btns, chat_id)

async def cmd_status(chat_id):
    state = load_state()
    alerts = state.get("alerts_sent", 0)
    last = state.get("last_check", 0)
    last_ts = datetime.fromtimestamp(last, tz=timezone.utc).strftime("%H:%M:%S UTC") if last else "никогда"
    uptime = "running" if os.path.exists("/tmp/whale_bot_pid") else "unknown"

    text = f"""🐋 *Whale Tracker Status*
═══════════════════════════════════

🟢 Bot: *Online*
📊 Alerts sent: *{alerts}*
⏰ Last check: *{last_ts}*
🐋 Tracked whales: *{len(WHALES)}*
🔄 Interval: *5 min*

*Recent whale activity:*"""

    last_act = state.get("last_activity", {})
    if last_act:
        for addr, info in list(last_act.items())[-5:]:
            w = match_whale(addr)
            name = w["name"] if w else addr[:10]
            text += f"\n  {name}: {info}"
    else:
        text += "\n  Пока нет активности китов"

    await tg_send(text, chat_id=chat_id)

async def cmd_markets(chat_id):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        try:
            async with s.get(f"{GAMMA_API}/markets?limit=10&order=volume24hr&ascending=false&closed=false") as r:
                markets = await r.json()
        except Exception:
            await tg_send("❌ Не удалось загрузить рынки", chat_id=chat_id)
            return

    text = "📈 *Топ-10 рынков Polymarket:*\n═══════════════════════════════════\n\n"
    btns = []
    for i, m in enumerate(markets[:10], 1):
        title = (m.get("question") or m.get("title", "?"))[:50]
        vol = m.get("volume24hr", 0)
        slug = m.get("slug") or m.get("condition_id", "")
        try:
            vol_f = float(vol)
            vol_str = f"${vol_f:,.0f}"
        except (ValueError, TypeError):
            vol_str = "N/A"
        text += f"{i}. *{title}*\n   24h Vol: {vol_str}\n\n"
        if slug and i <= 5:
            btns.append([{"text": f"📈 {title[:30]}", "url": f"https://polymarket.com/event/{slug}"}])

    btns.append([{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}])
    await tg_send(text, btns, chat_id)

async def cmd_check(chat_id):
    await tg_send("🔍 Проверяю китов вручную...", chat_id=chat_id)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        n = await check_and_alert(s)
    if n > 0:
        await tg_send(f"🐋 Найдено {n} алерт(ов)!", chat_id=chat_id)
    else:
        await tg_send("🐋 Киты спят — нет активности в последние 5 минут", chat_id=chat_id)

# ===== WHALE MONITORING =====

async def send_whale_alert(whale, trade):
    side = trade.get("side", "?")
    size = float(trade.get("size", 0) or 0)
    price = float(trade.get("price", 0) or 0)
    vol = size * price
    title = (trade.get("title") or trade.get("market", "?"))[:60]
    outcome = trade.get("outcome", "?")
    slug = trade.get("slug") or trade.get("market_slug", "")
    pseudo = trade.get("pseudonym") or trade.get("taker", whale["name"])

    emoji = "🟢" if side == "BUY" else "🔴"
    act = "КУПИЛ" if side == "BUY" else "ПРОДАЛ"
    risk = "🔴 HIGH" if vol > 50000 else "🟡 MED" if vol > 10000 else "🟢 LOW"

    instructions = get_trade_instructions(side, price, vol)
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

📋 *ИНСТРУКЦИЯ:*
{instructions}"""

    btns = [
        [{"text": "📈 Open Market", "url": f"https://polymarket.com/event/{slug}"}],
        [{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}, {"text": "📊 PolyMonit", "url": "https://polymonit.com/leaderboard/polymarket-whales"}],
        [{"text": "🔍 PolyIntel", "url": "https://polyintel.io/"}]
    ]
    await tg_send(text, btns)



def get_trade_instructions(side, price, vol):
    """Generate specific trading instructions."""
    instr = []
    if side == "BUY":
        if price < 0.30:
            instr.append("📈 Лангшот — риск <3% банкролла")
            instr.append(f"🎯 Тейк: {price*3:.0f}¢ (3x)")
            instr.append(f"🛑 Стоп: {price*0.5:.2f}¢ (-50%)")
        elif price < 0.50:
            instr.append(f"📈 Вход @ {price:.2f}¢ после стабилизации")
            instr.append(f"🎯 Тейк: {price+0.15:.0f}¢ (+{0.15/price*100:.0f}%)")
            instr.append(f"🛑 Стоп: {price*0.75:.2f}¢ (-25%)")
        elif price < 0.80:
            instr.append(f"📈 Высокая вероятность, низкий ROI")
            instr.append(f"🎯 Тейк: {price+0.08:.0f}¢ (+{0.08/price*100:.0f}%)")
            instr.append(f"🛑 Стоп: {price-0.10:.2f}¢ (-12%)")
        else:
            instr.append(f"⚠️ Почти гарантировано, но ROI = {(1-price)*100:.1f}% — НЕ СТОИТ")
    else:
        no_price = 1 - price
        instr.append(f"📉 Short (NO) @ {no_price:.2f}¢")
        instr.append(f"🎯 Тейк: resolve=NO → {no_price*100:.1f}¢/$")
        instr.append(f"🛑 Стоп: цена YES > {price+0.10:.2f}¢")
    
    if vol > 50000:
        instr.append("💰 Кит ВЫСОКО уверен — $100-500 за ним")
    elif vol > 10000:
        instr.append("💰 Средняя уверенность — $50-200")
    else:
        instr.append("💰 Разведка — подожди подтверждения")
    
    return "\n".join(instr)

async def check_and_alert(session):
    state = load_state()
    alerts = 0
    all_trades = []

    try:
        async with session.get(f"{DATA_API}/trades?limit=500&order=desc") as r:
            all_trades = await r.json()
    except Exception as e:
        print(f"Trades fetch error: {e}")

    try:
        async with session.get(f"{GAMMA_API}/markets?limit=20&order=volume24hr&ascending=false&closed=false") as r:
            markets = await r.json()
            for m in markets[:10]:
                slug = m.get("slug", "")
                if slug:
                    try:
                        async with session.get(f"{DATA_API}/trades?limit=100&order=desc&slug={slug}") as r2:
                            all_trades.extend(await r2.json())
                    except Exception:
                        pass
    except Exception:
        pass

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
        state["last_activity"][addr[:10]] = f"${vol:,.0f} {t.get('side','?')} @ {datetime.now(timezone.utc).strftime('%H:%M')}"
        alerts += 1

    if len(state["last_trades"]) > 2000:
        sorted_k = sorted(state["last_trades"].keys(), key=lambda k: state["last_trades"][k])
        for k in sorted_k[:500]:
            del state["last_trades"][k]

    state["last_check"] = time.time()
    save_state(state)
    return alerts

# ===== POLLING LOOP =====



async def cmd_positions(chat_id):
    """Show current whale positions with P&L and instructions."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        lines = ["📊 *ПОЗИЦИИ КИТОВ*", "═════════════════════════", ""]
        for addr, info in WHALES.items():
            try:
                url = f"{DATA_API}/positions?user={addr.lower()}"
                async with s.get(url) as r:
                    positions = await r.json()
                
                # Filter significant positions (> $500 value)
                significant = []
                for p in positions[:30]:
                    try:
                        cv = float(p.get("currentValue", 0) or 0)
                        if cv > 500:
                            significant.append(p)
                    except:
                        continue
                
                if not significant:
                    continue
                
                total_val = sum(float(p.get("currentValue", 0) or 0) for p in significant)
                total_pnl = sum(float(p.get("cashPnl", 0) or 0) for p in significant)
                pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
                
                lines.append(f"{info['emoji']} *{info['name']}* — ${total_val:,.0f} | {pnl_emoji} ${total_pnl:+,.0f}")
                
                for p in significant[:3]:
                    title = p.get("title", "?")[:35]
                    cv = float(p.get("currentValue", 0) or 0)
                    pnl = float(p.get("cashPnl", 0) or 0)
                    pct = float(p.get("percentPnl", 0) or 0)
                    cur = float(p.get("curPrice", 0) or 0)
                    avg = float(p.get("avgPrice", 0) or 0)
                    outcome = p.get("outcome", "?")
                    
                    p_emoji = "🟢" if pnl >= 0 else "🔴"
                    instr_line = ""
                    if cur > 0 and avg > 0:
                        if pnl > 0:
                            instr_line = f"  💰 Тейк: держи или продавай @ {cur*100:.0f}¢ (+{pct:.0f}%)"
                        else:
                            instr_line = f"  🛑 Стоп: если упадёт до {avg*0.75*100:.0f}¢"
                    
                    lines.append(f"  {p_emoji} {outcome} {title} — ${cv:,.0f} ({pnl:+,.0f})")
                    if instr_line:
                        lines.append(f"  {instr_line}")
                
                lines.append("")
                
            except Exception as e:
                lines.append(f"❌ {info['name']}: error")
        
        if len(lines) <= 3:
            lines.append("🐋 Киты отдыхают — нет значимых позиций")
        
        text = "\n".join(lines[:4096])
    
    btns = [[{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}]]
    await tg_send(text, btns, chat_id)

COMMANDS = {
    "/start": cmd_start,
    "/help": cmd_help,
    "/whales": cmd_whales,
    "/status": cmd_status,
    "/markets": cmd_markets,
    "/check": cmd_check,
    "/positions": cmd_positions,
}

async def run_bot():
    print(f"🐋 Whale Alert Bot started. {len(WHALES)} whales tracked.")
    
    # Write PID file
    with open("/tmp/whale_bot_pid", "w") as f:
        f.write(str(os.getpid()))

    last_update_id = 0
    last_whale_check = 0
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    try:
        while True:
            # 1. Poll for messages (commands)
            try:
                async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id+1}&limit=10&timeout=5") as r:
                    updates = await r.json()
                    for u in updates.get("result", []):
                        last_update_id = max(last_update_id, u.get("update_id", 0))
                        msg = u.get("message") or u.get("callback_query", {}).get("message", {})
                        text = (msg.get("text") or "").strip()
                        chat_id = msg.get("chat", {}).get("id")
                        callback = u.get("callback_query")

                        # Handle callback buttons
                        if callback:
                            await tg_answer_callback(callback["id"], "✅")
                            continue

                        # Handle commands
                        if text and text.lower().split()[0] in [c.lower() for c in COMMANDS]:
                            cmd = text.lower().split()[0]
                            for cmd_key, handler in COMMANDS.items():
                                if cmd_key.lower() == cmd:
                                    await handler(chat_id)
                                    break
            except Exception as e:
                print(f"Poll error: {e}")

            # 2. Check whales every 5 minutes
            now = time.time()
            if now - last_whale_check >= 300:
                try:
                    n = await check_and_alert(session)
                    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                    print(f"[{ts}] {'🐋 ' + str(n) + ' alert(s)' if n else 'No whale activity'}")
                except Exception as e:
                    print(f"Whale check error: {e}")
                last_whale_check = now

            await asyncio.sleep(3)
    finally:
        await session.close()
        if os.path.exists("/tmp/whale_bot_pid"):
            os.remove("/tmp/whale_bot_pid")

if __name__ == "__main__":
    asyncio.run(run_bot())
