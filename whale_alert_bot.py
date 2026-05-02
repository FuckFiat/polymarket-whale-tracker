#!/usr/bin/env python3
"""
🐋 NANO Polymarket Whale Alert Bot
Interactive Telegram bot with commands + automatic whale monitoring.
"""
import asyncio, aiohttp, json, time, os, sys
from datetime import datetime, timezone
from virtual_trading import load_portfolio, save_portfolio, place_bet, close_position, get_stats, update_prices
from hyperliquid_monitor import scan_whale_positions, format_alert as hl_format_alert, load_hl_state, HYPERLIQUID_WHALES, HL_API, refresh_leaderboard, get_user_state, get_all_mids
from eth_whale_monitor import fetch_all_eth_data, format_eth_summary, format_eth_compact, load_eth_state, save_eth_state

BOT_TOKEN = "8375563056:AAH0vHARkJW6cstYsIhkczZHxfYRp7v3PLw"
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
    "0x2005d16a84ceefa912d4e380cd32e7ff827875ea": {"name": "⚠️ Кит #9 — RN1", "vol": "$50.9M", "strat": "Хай-волюм ротация (СЛИВАЕТ)", "tier": "watch_only"},
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

async def cmd_help_orig(chat_id):
    """Deprecated — replaced by new cmd_help"""
    pass

async def cmd_start(chat_id, args=""):
    """Handle /start command with optional deep link args."""
    # Deep link handling: /start bet, /start deposit, /start close, /start topup
    if args:
        arg = args.lower().strip()
        if arg == "bet":
            await cmd_bet(chat_id)
            return
        if arg == "deposit":
            await cmd_deposit(chat_id)
            return
        if arg == "close":
            await cmd_close(chat_id)
            return
        if arg == "topup":
            portfolio = load_portfolio()
            portfolio["balance"] += 500
            save_portfolio(portfolio)
            await tg_send(f"\u2795 Депозит пополнен на $500!\nБаланс: ${portfolio['balance']:.2f}", chat_id)
            return
        # bet_whale_outcome_price format
        if arg.startswith("bet_"):
            parts = arg.split("_")
            if len(parts) >= 3:
                await tg_send(f"\U0001f3b0 Для ставки используйте /bet в боте", chat_id)
                await cmd_bet(chat_id)
                return
    text = """🐋 *Whale Tracker Online*

 Polymarket + Hyperliquid киты в реальном времени

/whales — Список китов
/hlwhales — HL киты и монеты
/status — Статус бота
/markets — Топ рынки
/check — Проверить китов
/positions — Позиции и P&L

 Алерты прилетают автоматически 🐋"""
    btns = [[{"text": "\U0001f40b Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}],
            [{"text": "\U0001f4ca PolyMonit", "url": "https://polymonit.com/leaderboard/polymarket-whales"}, {"text": "\U0001f50d PolyIntel", "url": "https://polyintel.io/"}]]
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
    title = (trade.get("title") or trade.get("market", "?"))[:55]
    outcome = trade.get("outcome", "?")
    slug = trade.get("slug") or trade.get("market_slug", "")
    pseudo = trade.get("pseudonym") or trade.get("taker", whale["name"])

    emoji = "🟢" if side == "BUY" else "🔴"
    act = "LONG" if side == "BUY" else "SHORT"
    risk_emoji = "🔥" if vol > 50000 else "⚡" if vol > 10000 else "🎯"

    # Format volume nicely
    if vol >= 1_000_000:
        vol_str = f"${vol/1_000_000:.1f}M"
    else:
        vol_str = f"${vol:,.0f}"

    price_cents = f"{price*100:.0f}¢"

    instructions = get_trade_instructions(side, price, vol)
    text = f"""{emoji} *{act}* {outcome} · {title}
{risk_emoji} ${vol_str} @ {price_cents}

{whale['name']} · Vol {whale['vol']}
🧠 {whale['strat']}
⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}

{instructions}"""

    btns = [
        [{"text": "📈 Market", "url": f"https://polymarket.com/event/{slug}"}],
        [{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}, {"text": "📊 Leaderboard", "url": "https://polymonit.com/leaderboard/polymarket-whales"}],
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
    """Monitor whale POSITIONS (not trades) and auto-bet on significant moves."""
    state = load_state()
    alerts = 0
    all_whale_positions = []
    significant_moves = []
    
    # 1. Fetch positions for each whale
    for addr, info in WHALES.items():
        try:
            async with session.get(f"{DATA_API}/positions?user={addr.lower()}", timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    positions = await r.json()
                    if isinstance(positions, list):
                        # Filter significant positions (>$500)
                        sig_positions = [p for p in positions if float(p.get("currentValue", 0) or 0) > 500]
                        total_val = sum(float(p.get("currentValue", 0) or 0) for p in positions)
                        total_pnl = sum(float(p.get("cashPnl", 0) or 0) for p in positions)
                        
                        # Check for new or changed positions
                        whale_key = addr[:10]
                        prev_count = state.get("last_position_count", {}).get(whale_key, 0)
                        curr_count = len(sig_positions)
                        
                        for p in sig_positions[:5]:  # Top 5 positions per whale
                            title = p.get("title", "?")[:40]
                            cur_val = float(p.get("currentValue", 0) or 0)
                            pnl = float(p.get("cashPnl", 0) or 0)
                            outcome = p.get("outcome", "?")
                            price = float(p.get("curPrice", 0) or 0.5)
                            
                            # Check if this is a NEW significant position
                            pos_key = f"{whale_key}:{title}:{outcome}"
                            if pos_key not in state.get("seen_positions", {}):
                                # New position found!
                                significant_moves.append({
                                    "whale": info["name"],
                                    "whale_addr": addr,
                                    "market": title,
                                    "outcome": outcome,
                                    "value": cur_val,
                                    "pnl": pnl,
                                    "price": price,
                                    "pct_change": float(p.get("percentPnl", 0) or 0),
                                })
                                state.setdefault("seen_positions", {})[pos_key] = time.time()
                            
                            all_whale_positions.append(p)
                        
                        # Update whale state
                        state.setdefault("last_position_count", {})[whale_key] = curr_count
                        state.setdefault("last_activity", {})[whale_key] = f"${total_val:,.0f} | P&L: ${total_pnl:+,.0f} | {datetime.now(timezone.utc).strftime('%H:%M')}"
                        
                        # Alert on significant P&L changes
                        if abs(total_pnl) > 100000:
                            pnl_emoji = "🟢" if total_pnl > 0 else "🔴"
                            await tg_send(f"*{info['name']}* — P&L: {pnl_emoji} ${total_pnl:+,.0f}\n📊 {len(sig_positions)} значимых позиций | ${total_val:,.0f} всего")
                            alerts += 1
        except Exception as e:
            print(f"Whale {info['name']} error: {e}")
    
    # 2. Auto-bet on new whale positions
    portfolio = load_portfolio()
    if portfolio.get("auto_betting", True) and significant_moves:
        for move in significant_moves[:15]:  # Max 15 new bets per cycle
            if portfolio["balance"] < 50:
                break
            # Only bet on whales with >$1M volume
            whale_info = WHALES.get(move["whale_addr"], {})
            # Skip watch_only whales (e.g. RN1 — consistent loser)
            if whale_info.get("tier") == "watch_only":
                continue
            whale_vol_str = whale_info.get("vol", "$0")
            whale_vol = float(whale_vol_str.replace("$", "").replace("M", "")) if "M" in whale_vol_str else 0
            if whale_vol < 1:  # Skip dolphins
                continue
            price = move.get("price", 0.5)
            if price <= 0.05 or price >= 0.98:  # Skip near-certain markets
                continue
            result = place_bet(portfolio, move["whale"], move["market"], move["outcome"], price, 50.0, price)
            if "error" not in result:
                await tg_send(f"🎰 *АВТО-СТАВКА*\n\n{move['whale']}: {move['outcome']} {move['market'][:30]}\n@ {price*100:.0f}¢ | $50\n💰 Баланс: ${portfolio['balance']:.2f}")
                alerts += 1
    
    # 3. Update virtual trading prices
    from virtual_trading import update_prices
    update_prices(portfolio, all_whale_positions)
    
    # 4. Check for resolved markets (improved matching)
    for pos in list(portfolio.get("positions", [])):
        market_hint = pos["market"][:50].lower().strip()
        # Extract key words for fuzzy matching
        market_words = [w.lower() for w in market_hint.split() if len(w) > 2]
        try:
            async with session.get(f"{GAMMA_API}/markets?limit=10&search={'+'.join(market_words[:5])}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    markets = await r.json()
                    for m in markets:
                        question = m.get("question", "").lower()
                        # Fuzzy match: at least 3 key words match OR question contains the market hint
                        matches = sum(1 for w in market_words if w in question)
                        is_match = (matches >= 2 and len(market_words) <= 3) or (matches >= 3) or question.startswith(market_hint) or market_hint in question
                        if m.get("closed") and is_match:
                            resolution = m.get("resolution", "").lower()
                            outcome = pos["outcome"].lower()
                            # Determine win/loss
                            if outcome in ("yes", "y") and resolution == "yes":
                                won = True
                            elif outcome in ("no", "n") and resolution == "no":
                                won = True
                            elif resolution == outcome:
                                won = True
                            else:
                                # For sport markets: check if outcome matches the winner
                                won = outcome in resolution or resolution in outcome
                            
                            close_position(portfolio, pos["id"], "win" if won else "loss")
                            result_emoji = "✅" if won else "❌"
                            result_text = "ВЫИГРАЛА" if won else "ПРОИГРАНА"
                            await tg_send(f"{result_emoji} *СТАВКА {result_text}!*\n\n{pos['whale']}: {outcome} {pos['market'][:40]}\n💰 {'+' + str(pos['bet_size']) if won else '-' + str(pos['bet_size'])}\n📊 Разрешение: {resolution}")
                            break
        except Exception as e:
            print(f"[check_resolved] Error checking {market_hint}: {e}")
    
    # 4b. Auto-close dead positions (> 48h open with no price update, likely resolved)
    now = time.time()
    for pos in list(portfolio.get("positions", [])):
        entry_ts = pos.get("id", "").split("_")
        try:
            entry_time = int(entry_ts[1]) if len(entry_ts) > 1 else 0
            hours_open = (now - entry_time) / 3600
            cur = pos.get("cur_price", 0)
            # If open > 48h and price stuck at 1.0 or 0.0, likely resolved
            if hours_open > 48 and cur in (1.0, 0.0):
                # Check if cur_price hasn't changed from entry
                if cur == pos.get("entry_price", -1):
                    # Likely a dead position — don't auto-close, but flag it
                    pos["status"] = "stale"
        except (ValueError, IndexError):
            pass
    
    # 5. Cleanup old seen positions (keep last 500)
    if len(state.get("seen_positions", {})) > 500:
        sorted_keys = sorted(state["seen_positions"].keys(), key=lambda k: state["seen_positions"][k])
        for k in sorted_keys[:200]:
            del state["seen_positions"][k]
    
    state["last_check"] = time.time()
    state["alerts_sent"] = state.get("alerts_sent", 0) + alerts
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
                
                lines.append(f"*{info['name']}* — ${total_val:,.0f} | {pnl_emoji} ${total_pnl:+,.0f}")
                
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



async def cmd_predictfun(chat_id):
    """Show PredictFun markets that are also on Polymarket/Kalshi."""
    await tg_send("🔍 Загружаю кросс-платформенные маркеты...", chat_id)
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
        cross, all_mkts = await get_cross_platform_markets(s)
    
    if not cross:
        await tg_send("❌ Не удалось загрузить маркеты PredictFun", chat_id)
        return
    
    lines = [f"🔮 *Кросс-платформенные маркеты* ({len(cross)} из {len(all_mkts)})", ""]
    
    # Group by platform count
    poly_only = [m for m in cross if "Polymarket" in m.get("platforms", [])]
    kalshi_only = [m for m in cross if "Kalshi" in m.get("platforms", [])]
    both = [m for m in cross if "Polymarket" in m.get("platforms", []) and "Kalshi" in m.get("platforms", [])]
    
    lines.append(f"📊 Polymarket + Predict.fun: *{len(poly_only)}*")
    lines.append(f"📊 Kalshi + Predict.fun: *{len(kalshi_only)}*")
    lines.append(f"🔥 Все три: *{len(both)}*")
    lines.append("")
    
    # Top 10 by volume
    sorted_cross = sorted(cross, key=lambda m: float(m.get("volume24h", 0) or 0), reverse=True)[:10]
    lines.append("🏆 *ТОП-10 по объёму:*")
    for i, m in enumerate(sorted_cross, 1):
        title = m.get("title", "?")[:45]
        vol = float(m.get("volume24h", 0) or 0)
        platforms = ", ".join(m.get("platforms", []))
        lines.append(f"{i}. {title} — ${vol:,.0f} ({platforms})")
    
    text = "\n".join(lines)[:4096]
    btns = [
        [{"text": "🔮 Predict.fun", "url": "https://predict.fun"}, {"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}],
        [{"text": "💰 Арбитраж", "callback_data": "arbitrage"}],
    ]
    await tg_send(text, btns, chat_id)

async def cmd_arbitrage(chat_id):
    """Find arbitrage opportunities between Predict.fun and Polymarket."""
    await tg_send("🔍 Ищу арбитражные возможности...", chat_id)
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
        cross, _ = await get_cross_platform_markets(s)
        arb = await find_arbitrage(s, cross)
    
    if not arb:
        await tg_send("🤷 Арбитражных возможностей не найдено (спред < 3%)", chat_id)
        return
    
    lines = [f"💰 *АРБИТРАЖ* — {len(arb)} возможностей", ""]
    for i, a in enumerate(arb[:10], 1):
        lines.append(f"{i}. *{a['title'][:40]}*")
        lines.append(f"   PF YES: {a['predictfun_yes']:.1f}¢ | Poly YES: {a['polymarket_yes']:.1f}¢")
        lines.append(f"   Спред: *{a['spread_pct']:.1f}%* | {a['direction']}")
        lines.append("")
    
    text = "\n".join(lines)[:4096]
    btns = [[{"text": "🐋 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}]]
    await tg_send(text, btns, chat_id)



async def cmd_deposit(chat_id):
    """Show virtual portfolio status."""
    portfolio = load_portfolio()
    stats = get_stats(portfolio)
    
    text = f"""🎰 *NANO ВИРТУАЛЬНЫЙ ДЕПОЗИТ*
═══════════════════════════════════

💰 Баланс: *${stats['balance']:.2f}*
📊 Открытых ставок: *{stats['open_positions']}*
✅ Побед: *{stats['wins']}* | ❌ Поражений: *{stats['losses']}*
📈 Win Rate: *{stats['win_rate']:.0f}%*
💵 Всего выиграно: *${stats['total_won']:.2f}*
💸 Всего проиграно: *${stats['total_lost']:.2f}*
📊 Открытый P&L: *${stats['open_pnl']:+.2f}*
💰 Всего P&L: *${stats['total_pnl']:+.2f}*
📈 ROI: *{stats['roi_pct']:+.1f}%*
🎯 Стартовый депозит: *${stats['initial_deposit']:.2f}*"""

    if portfolio["positions"]:
        text += "\n\n📋 *Открытые ставки:*"
        for p in portfolio["positions"][:8]:
            pnl_emoji = "🟢" if p["pnl"] >= 0 else "🔴"
            text += f"\n{pnl_emoji} {p['whale']}: {p['outcome']} {p['market'][:30]} @ {p['entry_price']*100:.0f}c — ${p['pnl']:+.2f}"
    
    if portfolio["resolved"]:
        text += f"\n\n🏁 Разрешённых: {len(portfolio['resolved'])}"
    
    btns = [
        [{"text": "🎰 Ставка", "callback_data": "vt_bet"}, {"text": "📊 Dashboard", "url": "https://fuckfiat.github.io/polymarket-whale-tracker/"}],
        [{"text": "🔄 Обновить цены", "callback_data": "vt_refresh"}, {"text": "➕ Пополнить", "callback_data": "vt_topup"}],
    ]
    await tg_send(text, btns, chat_id)

async def cmd_bet(chat_id):
    """Show available whale signals to bet on."""
    portfolio = load_portfolio()
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        # Get top whale positions as bet signals
        signals = []
        for addr, info in WHALES.items():
            try:
                url = f"{DATA_API}/positions?user={addr.lower()}"
                async with s.get(url) as r:
                    positions = await r.json()
                for p in positions[:10]:
                    cv = float(p.get("currentValue", 0) or 0)
                    cur = float(p.get("curPrice", 0) or 0)
                    avg = float(p.get("avgPrice", 0) or 0)
                    if cv > 500 and cur > 0:
                        signals.append({
                            "whale": info["name"],
                            "emoji": info["name"][:2],  # Emoji is first chars of name
                            "market": p.get("title", "?"),
                            "outcome": p.get("outcome", "?"),
                            "cur_price": cur,
                            "avg_price": avg,
                            "value": cv,
                            "pnl": float(p.get("cashPnl", 0) or 0),
                        })
            except:
                continue
    
    # Sort by whale P&L direction (winning positions first)
    signals.sort(key=lambda x: x["pnl"], reverse=True)
    
    if not signals:
        await tg_send("🐋 Нет доступных сигналов от китов", chat_id)
        return
    
    text = f"🎰 *ДОСТУПНЫЕ СИГНАЛЫ*\nБаланс: ${portfolio['balance']:.2f}\n\n"
    
    # Create inline buttons for top signals
    btns = []
    for i, sig in enumerate(signals[:6]):
        pnl_emoji = "🟢" if sig["pnl"] >= 0 else "🔴"
        text += f"\n{pnl_emoji} {sig['emoji']} {sig['whale']}: {sig['outcome']} {sig['market'][:35]}"
        text += f"\n   @ {sig['cur_price']*100:.0f}c | ${sig['value']:,.0f} | ${sig['pnl']:+,.0f}"
        
        # Button to bet on this signal
        cb_data = f"bet_{sig['whale']}_{sig['outcome']}_{sig['cur_price']}_{sig['market'][:20]}"
        if len(cb_data) <= 64:
            btns.append([{"text": f"🎰 {sig['emoji']} {sig['whale']}: {sig['outcome']} @ {sig['cur_price']*100:.0f}c ($50)", "callback_data": cb_data}])
    
    text += f"\n\nСтавка: $50 | Баланс: ${portfolio['balance']:.2f}"
    
    btns.append([{"text": "🎰 Кастомная ставка", "callback_data": "vt_custom"}])
    await tg_send(text, btns, chat_id)

async def cmd_close(chat_id):
    """Close a position."""
    portfolio = load_portfolio()
    if not portfolio["positions"]:
        await tg_send("📋 Нет открытых ставок", chat_id)
        return
    
    text = "🏁 *ЗАКРЫТЬ СТАВКУ*\n\n"
    btns = []
    for p in portfolio["positions"][:6]:
        pnl_emoji = "🟢" if p["pnl"] >= 0 else "🔴"
        text += f"{pnl_emoji} {p['whale']}: {p['outcome']} {p['market'][:30]} — ${p['pnl']:+.2f}\n"
        btns.append([
            {"text": f"✅ WIN {p['id']}", "callback_data": f"close_win_{p['id']}"},
            {"text": f"❌ LOSS {p['id']}", "callback_data": f"close_loss_{p['id']}"},
        ])
    
    await tg_send(text, btns, chat_id)

# ===== TOP 10 COINS FOR HYPERLIQUID =====
HL_TOP_COINS = ["BTC", "ETH", "SOL", "HYPE", "XRP", "DOGE", "LINK", "AVAX", "ARB", "SUI"]

# User's selected coins (default: all top 10)
HL_SELECTED_COINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "hl_selected_coins.json")

def load_hl_selected_coins():
    if os.path.exists(HL_SELECTED_COINS_FILE):
        try:
            with open(HL_SELECTED_COINS_FILE) as f:
                data = json.load(f)
                return data if data else HL_TOP_COINS[:]
        except:
            return HL_TOP_COINS[:]
    return HL_TOP_COINS[:]

def save_hl_selected_coins(coins):
    os.makedirs(os.path.dirname(HL_SELECTED_COINS_FILE), exist_ok=True)
    with open(HL_SELECTED_COINS_FILE, "w") as f:
        json.dump(coins, f)

async def cmd_hlwhales(chat_id):
    """Show Hyperliquid whale positions + coin selection menu"""
    selected = load_hl_selected_coins()
    hl_state = load_hl_state()
    whales = HYPERLIQUID_WHALES
    active_whales = {k: v for k, v in whales.items() if v.get("tier") != "placeholder"}
    
    text = "🔮 *Hyperliquid Whale Monitor*\n═══════════════════════════════════\n\n"
    text += f"🐋 Отслеживается китов: {len(active_whales)}\n"
    text += f"📊 Монеты: {', '.join(selected)}\n"
    text += f"⏰ Последняя проверка: {datetime.fromtimestamp(hl_state.get('last_check', 0), tz=timezone.utc).strftime('%H:%M UTC') if hl_state.get('last_check') else 'никогда'}\n\n"
    
    # Show whale account values
    for addr, info in list(active_whales.items())[:5]:
        pnl_info = hl_state.get("whale_pnl", {}).get(addr[:10], {})
        if pnl_info:
            text += f"{info['name']}\n"
            text += f"  💰 ${pnl_info.get('account_value', 0):,.0f} | 📊 {pnl_info.get('positions', 0)} поз.\n"
    text += "\n"
    
    # Coin selection buttons (2 per row)
    btns = []
    for i in range(0, len(HL_TOP_COINS), 2):
        row = []
        for coin in HL_TOP_COINS[i:i+2]:
            if coin in selected:
                row.append({"text": f"✅ {coin}", "callback_data": f"hl_coin_off_{coin}"})
            else:
                row.append({"text": f"⬜ {coin}", "callback_data": f"hl_coin_on_{coin}"})
        btns.append(row)
    
    btns.append([
        {"text": "🔍 Сканировать", "callback_data": "hl_scan"},
        {"text": "🔄 Все", "callback_data": "hl_coins_all"},
    ])
    btns.append([{"text": "🔮 Hyperliquid", "url": "https://app.hyperliquid.xyz/trade"}])
    await tg_send(text, btns, chat_id)

async def cmd_hlcheck(chat_id):
    """Manually check Hyperliquid whales (only selected coins)"""
    selected = load_hl_selected_coins()
    await tg_send(f"🔮 Сканирую HL китов...\nМонеты: {', '.join(selected)}", chat_id=chat_id)
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        mids = await get_all_mids(session)
        if not mids:
            await tg_send("❌ Не удалось подключиться к Hyperliquid", chat_id=chat_id)
            return
        
        # Fetch leaderboard for active traders
        import urllib.request
        try:
            req = urllib.request.Request("https://stats-data.hyperliquid.xyz/Mainnet/leaderboard", headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            lb_data = json.loads(resp.read())
            rows = lb_data.get("leaderboardRows", [])
            # Sort by account value, skip mega-vaults
            candidates = sorted(
                [r for r in rows if float(r.get("accountValue", 0)) < 5_000_000_000],
                key=lambda x: float(x.get("accountValue", 0)), reverse=True
            )
        except:
            candidates = []
        
        # Check both pre-configured whales AND leaderboard top traders
        all_addresses = {}
        for addr, info in HYPERLIQUID_WHALES.items():
            if info.get("tier") != "placeholder":
                all_addresses[addr] = info
        
        # Add top leaderboard traders
        for entry in candidates[:30]:
            addr = entry.get("ethAddress", "")
            if addr not in all_addresses:
                av = float(entry.get("accountValue", 0))
                all_pnl = 0
                for w, perf in entry.get("windowPerformances", []):
                    if w == "allTime":
                        all_pnl = float(perf.get("pnl", 0))
                name = entry.get("displayName") or f"${av/1e6:.0f}M"
                all_addresses[addr] = {
                    "name": f"🐋 {name}",
                    "vol": "$0",
                    "strat": f"PnL ${all_pnl/1e6:.1f}M",
                    "tier": "whale" if av > 1_000_000 else "dolphin",
                }
        
        messages = []
        total_found = 0
        
        for addr, info in all_addresses.items():
            try:
                state = await get_user_state(session, addr)
            except:
                continue
            if not state:
                continue
            
            positions = state.get("assetPositions", [])
            margin = state.get("marginSummary", {})
            account_value = float(margin.get("totalAccountValue", 0))
            
            if account_value < 100_000:  # Skip small accounts
                continue
            
            whale_positions = []
            for pos in positions:
                p = pos.get("position", {})
                coin = p.get("coin", "?")
                if selected and coin not in selected:
                    continue
                szi = p.get("szi", "0")
                if float(szi) == 0:
                    continue
                entry_px = p.get("entryPx", "0")
                pnl = p.get("unrealizedPnl", "0")
                lev = p.get("leverage", {})
                lev_val = float(lev.get("value", 1)) if isinstance(lev, dict) else 1.0
                liq_px = p.get("liquidationPx", None)
                margin_used = p.get("marginUsed", "0")
                cur_px = mids.get(coin, "0")
                
                if not cur_px or float(cur_px) == 0:
                    continue
                
                from hyperliquid_monitor import format_position
                fmt = format_position(coin, szi, entry_px, pnl, cur_px, lev_val, liq_px, margin_used)
                
                if fmt["notional"] < 10000:  # Skip tiny
                    continue
                
                whale_positions.append(fmt)
            
            if not whale_positions:
                continue
            
            # Sort by notional (biggest first)
            whale_positions.sort(key=lambda x: x["notional"], reverse=True)
            
            # Format this whale's positions
            if account_value >= 1_000_000:
                av_str = f"${account_value/1e6:.1f}M"
            else:
                av_str = f"${account_value:,.0f}"
            
            for fmt in whale_positions[:5]:
                side_icon = "🟢" if fmt["side"] == "LONG" else "🔴"
                pnl_icon = "📈" if fmt["pnl"] > 0 else "📉"
                pnl_str = f"+${fmt['pnl']:,.0f}" if fmt['pnl'] > 0 else f"-${abs(fmt['pnl']):,.0f}"
                
                # Notional
                n = fmt["notional"]
                notional_str = f"${n/1e6:.1f}M" if n >= 1e6 else f"${n:,.0f}"
                
                # Entry/Current formatting
                e, c = fmt["entry"], fmt["current"]
                if e >= 1000:
                    e_str, c_str = f"${e:,.0f}", f"${c:,.0f}"
                elif e >= 1:
                    e_str, c_str = f"${e:,.2f}", f"${c:,.2f}"
                else:
                    e_str, c_str = f"${e:,.4f}", f"${c:,.4f}"
                
                # ROI
                if e > 0 and fmt["side"] == "LONG":
                    roi = (c - e) / e * 100
                elif e > 0 and fmt["side"] == "SHORT":
                    roi = (e - c) / e * 100
                else:
                    roi = 0
                roi_str = f"+{roi:.1f}%" if roi > 0 else f"{roi:.1f}%"
                
                # Liquidation
                liq = fmt.get("liq_price")
                if liq and liq > 0:
                    if liq >= 1000:
                        liq_str = f"${liq:,.0f}"
                    elif liq >= 1:
                        liq_str = f"${liq:,.2f}"
                    else:
                        liq_str = f"${liq:,.4f}"
                else:
                    liq_str = "—"
                
                # Liq distance
                ld = fmt.get("liq_distance")
                if ld is not None:
                    if ld < 10:
                        dist_str = f"🔴 {ld:.1f}%"
                    elif ld < 25:
                        dist_str = f"🟡 {ld:.1f}%"
                    else:
                        dist_str = f"🟢 {ld:.1f}%"
                else:
                    dist_str = "—"
                
                text = f"""{side_icon} {fmt['side']} *{fmt['coin']}* · {notional_str}
{info['name']} · {av_str}

📍 {e_str} → {c_str} ({roi_str})
{pnl_icon} {pnl_str} · ⚡ {fmt['leverage']:.0f}x
💀 Liq: {liq_str} ({dist_str})
💰 Margin: ${fmt['margin_used']:,.0f}"""
                messages.append(text)
                total_found += 1
                
                if total_found >= 15:  # Max 15 positions
                    break
            
            if total_found >= 15:
                break
        
        if messages:
            for msg in messages:
                await tg_send(msg, chat_id=chat_id)
        else:
            await tg_send(f"🔮 Нет крупных позиций по {', '.join(selected)}\nПопробуй другие монеты через /hlwhales", chat_id=chat_id)

async def cmd_eth(chat_id):
    """Show ETH whale positions across all exchanges"""
    await tg_send("🔮 Собираю данные ETH со всех бирж...", chat_id=chat_id)
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        data = await fetch_all_eth_data(session)
    
    if not data.get("exchanges"):
        await tg_send("❌ Не удалось получить данные ETH", chat_id=chat_id)
        return
    
    text = format_eth_summary(data)
    
    # Save to state
    eth_state = load_eth_state()
    eth_state["last_check"] = int(time.time())
    eth_state["last_data"] = data
    # Keep history of last 24 entries (4h at 10min intervals)
    eth_state.setdefault("history", []).append({
        "time": data["timestamp"],
        "ls_ratios": data.get("ls_ratios", []),
        "funding_rates": data.get("funding_rates", []),
        "eth_price": data.get("eth_price", 0),
        "total_oi_usd": data.get("total_oi_usd", 0),
    })
    eth_state["history"] = eth_state["history"][-24:]
    save_eth_state(eth_state)
    
    # Buttons
    btns = [
        [{"text": "🔄 Обновить", "callback_data": "eth_refresh"},
         {"text": "📊 История", "callback_data": "eth_history"}],
        [{"text": "🔮 Hyperliquid", "callback_data": "hl_scan"},
         {"text": "🐋 Polymarket", "callback_data": "vt_refresh"}],
    ]
    await tg_send(text, btns, chat_id)


COMMANDS = {
    "/start": cmd_start,
    "/help": cmd_help,
    "/whales": cmd_whales,
    "/status": cmd_status,
    "/markets": cmd_markets,
    "/check": cmd_check,
    "/positions": cmd_positions,
    "/deposit": cmd_deposit,
    "/bet": cmd_bet,
    "/close": cmd_close,
    "/arbitrage": cmd_arbitrage,
    "/hlwhales": cmd_hlwhales,
    "/hlcheck": cmd_hlcheck,
    "/eth": cmd_eth,
    "/ethmonitor": cmd_eth,
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
                            cb_data = callback.get("data", "")
                            cb_chat = callback.get("from", {}).get("id", chat_id)
                            
                            # Virtual trading: bet on whale signal
                            if cb_data.startswith("bet_") and not cb_data.startswith("bet_0x"):
                                parts = cb_data.split("_", 3)
                                if len(parts) >= 4:
                                    whale = parts[1]
                                    outcome = parts[2]
                                    price_market = parts[3]
                                    price_str = price_market.split("_")[0]
                                    try:
                                        price = float(price_str)
                                        market = price_market.split("_", 1)[1] if "_" in price_market else whale
                                        portfolio = load_portfolio()
                                        pos = place_bet(portfolio, whale, market, outcome, price, 50.0, price)
                                        if "error" in pos:
                                            await tg_send(f"❌ {pos['error']}", cb_chat)
                                        else:
                                            await tg_send(f"🎰 *СТАВКА СДЕЛАНА!*\n\n{whale}: {outcome} {market[:30]}\n@ {price*100:.0f}¢ | $50\nБаланс: ${portfolio['balance']:.2f}", cb_chat)
                                    except Exception as e:
                                            await tg_send(f"❌ Ошибка: {e}", cb_chat)
                                continue
                            
                            # Close position: WIN
                            if cb_data.startswith("close_win_"):
                                pos_id = cb_data.replace("close_win_", "")
                                portfolio = load_portfolio()
                                result = close_position(portfolio, pos_id, "win")
                                if "error" in result:
                                    await tg_send(f"❌ {result['error']}", cb_chat)
                                else:
                                    pnl_emoji = "✅" if result.get("pnl", 0) >= 0 else "💸"
                                    await tg_send(f"{pnl_emoji} *Ставка закрыта WIN!*\n\n{result.get('whale','?')}: {result.get('outcome','?')} {result.get('market','?')[:30]}\nP&L: ${result.get('pnl',0):+.2f}\nБаланс: ${portfolio['balance']:.2f}", cb_chat)
                                continue
                            
                            # Close position: LOSS
                            if cb_data.startswith("close_loss_"):
                                pos_id = cb_data.replace("close_loss_", "")
                                portfolio = load_portfolio()
                                result = close_position(portfolio, pos_id, "loss")
                                if "error" in result:
                                    await tg_send(f"❌ {result['error']}", cb_chat)
                                else:
                                    await tg_send(f"❌ *Ставка закрыта LOSS*\n\n{result.get('whale','?')}: {result.get('outcome','?')} {result.get('market','?')[:30]}\nP&L: ${result.get('pnl',0):+.2f}\nБаланс: ${portfolio['balance']:.2f}", cb_chat)
                                continue
                            
                            # Virtual trading: bet menu
                            if cb_data == "vt_bet":
                                await cmd_bet(cb_chat)
                                continue
                            
                            # Virtual trading: refresh
                            if cb_data == "vt_refresh":
                                await cmd_deposit(cb_chat)
                                continue
                            
                            # Virtual trading: top up
                            if cb_data == "vt_topup":
                                portfolio = load_portfolio()
                                portfolio["balance"] += 500
                                save_portfolio(portfolio)
                                stats = get_stats(portfolio)
                                await tg_send(f"➕ Депозит пополнен на $500!\nБаланс: ${portfolio['balance']:.2f}", cb_chat)
                                continue
                            
                            # Arbitrage
                            if cb_data == "arbitrage":
                                await cmd_arbitrage(cb_chat)
                                continue
                            
                            # ===== Hyperliquid coin selection callbacks =====
                            if cb_data == "hl_scan":
                                await cmd_hlcheck(cb_chat)
                                continue
                            
                            if cb_data == "hl_coins_all":
                                save_hl_selected_coins(HL_TOP_COINS[:])
                                await cmd_hlwhales(cb_chat)
                                continue
                            
                            if cb_data.startswith("hl_coin_on_"):
                                coin = cb_data.replace("hl_coin_on_", "")
                                selected = load_hl_selected_coins()
                                if coin not in selected:
                                    selected.append(coin)
                                save_hl_selected_coins(selected)
                                await cmd_hlwhales(cb_chat)
                                continue
                            
                            if cb_data.startswith("hl_coin_off_"):
                                coin = cb_data.replace("hl_coin_off_", "")
                                selected = load_hl_selected_coins()
                                if coin in selected:
                                    selected.remove(coin)
                                if not selected:
                                    selected = HL_TOP_COINS[:]
                                save_hl_selected_coins(selected)
                                await cmd_hlwhales(cb_chat)
                                continue
                            
                            # HL: show whale detail
                            if cb_data.startswith("hl_whale_"):
                                addr_short = cb_data.replace("hl_whale_", "")
                                await tg_send(f"🔮 Детали кита {addr_short}...", cb_chat)
                                continue
                            
                            # ===== ETH Monitor callbacks =====
                            if cb_data == "eth_refresh":
                                await cmd_eth(cb_chat)
                                continue
                            
                            if cb_data == "eth_history":
                                eth_state = load_eth_state()
                                history = eth_state.get("history", [])
                                if not history:
                                    await tg_send("📊 История пуста. Нажми /eth сначала.", cb_chat)
                                    continue
                                
                                lines = ["📊 *ETH L/S История (4ч)*", "═══════════════════════════════════"]
                                for h in history[-12:]:  # Last 12 entries
                                    t = datetime.fromtimestamp(h["time"], tz=timezone.utc).strftime("%H:%M")
                                    price = h.get("eth_price", 0)
                                    ls = h.get("ls_ratios", [])
                                    ls_str = " | ".join([f"{n}:{r:.3f}" for n, r in ls[:2]])
                                    lines.append(f"{t} ${price:,.0f} | {ls_str}")
                                
                                await tg_send("\n".join(lines), cb_chat)
                                continue
                            
                            continue

                        # Handle commands
                        if text and text.lower().split()[0] in [c.lower() for c in COMMANDS]:
                            cmd = text.lower().split()[0]
                            parts = text.split(None, 1)  # Split into command + args
                            args = parts[1] if len(parts) > 1 else ""
                            for cmd_key, handler in COMMANDS.items():
                                if cmd_key.lower() == cmd:
                                    if cmd_key == "/start" and args:
                                        await handler(chat_id, args)
                                    else:
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
            
            # 3. ETH monitor every 10 minutes
            if not hasattr(run_bot, '_last_eth_check'):
                run_bot._last_eth_check = 0
            if now - run_bot._last_eth_check >= 600:
                try:
                    eth_data = await fetch_all_eth_data(session)
                    eth_state = load_eth_state()
                    eth_state["last_check"] = int(time.time())
                    eth_state["last_data"] = eth_data
                    eth_state.setdefault("history", []).append({
                        "time": eth_data["timestamp"],
                        "ls_ratios": eth_data.get("ls_ratios", []),
                        "funding_rates": eth_data.get("funding_rates", []),
                        "eth_price": eth_data.get("eth_price", 0),
                        "total_oi_usd": eth_data.get("total_oi_usd", 0),
                    })
                    eth_state["history"] = eth_state["history"][-24:]
                    save_eth_state(eth_state)
                    
                    # Alert on significant L/S shifts
                    prev_ls = eth_state.get("prev_avg_ls", 0)
                    avg_ls = 0
                    non_pc = [r for n, r in eth_data.get("ls_ratios", []) if "P/C" not in n]
                    if non_pc:
                        avg_ls = sum(non_pc) / len(non_pc)
                    
                    # Alert if L/S ratio changed by >0.1
                    if prev_ls > 0 and abs(avg_ls - prev_ls) > 0.1:
                        direction = "🟢 БЫЧИЙ сдвиг" if avg_ls > prev_ls else "🔴 МЕДВЕЖИЙ сдвиг"
                        alert = f"⚠️ ETH L/S Shift: {prev_ls:.3f} → {avg_ls:.3f}\n{direction}\n{format_eth_compact(eth_data)}"
                        await tg_send(alert)
                    
                    # Alert on extreme funding rates
                    for name, rate in eth_data.get("funding_rates", []):
                        if abs(rate) > 0.05:  # >0.05% = extreme
                            emoji = "🔥" if rate > 0 else "🥶"
                            await tg_send(f"{emoji} ETH Funding Alert: {name} = {rate:+.4f}%")
                    
                    eth_state["prev_avg_ls"] = avg_ls
                    save_eth_state(eth_state)
                    
                    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                    print(f"[{ts}] ETH monitor: L/S={avg_ls:.4f} Price=${eth_data.get('eth_price', 0):,.0f}")
                except Exception as e:
                    print(f"ETH monitor error: {e}")
                run_bot._last_eth_check = now

            await asyncio.sleep(3)
    finally:
        await session.close()
        if os.path.exists("/tmp/whale_bot_pid"):
            os.remove("/tmp/whale_bot_pid")

if __name__ == "__main__":
    asyncio.run(run_bot())
