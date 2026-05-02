#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🐋 NANO Polymarket Whale Tracker v3.0
- Динамический дашборд с реальными данными
- Торговые инструкции к каждой сделке
- Визуализация дохода (всплывающие цифры)
- Сигнальный P&L трекер
"""

import asyncio, aiohttp, json, time, os, sys
from datetime import datetime, timezone, timedelta

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

WHALES = {
    "0x2a2c53bd278c04da9962fcf96490e17f3dfb9bc1": {"name": "kcnyekchno", "tier": "whale", "strat": "NO на геополитику", "emoji": "🐋"},
    "0xdc876e6873772d38716fda7f2452a78d426d7ab6": {"name": "432614799197", "tier": "whale", "strat": "Кросс-категорийный", "emoji": "🐋"},
    "0x02227b8f5a9636e895607edd3185ed6ee5598ff7": {"name": "HorizonSplendidView", "tier": "whale", "strat": "Спорт + макро", "emoji": "🐋"},
    "0x019782cab5d844f02bafb71f512758be78579f3c": {"name": "majorexploiter", "tier": "whale", "strat": "Геополитика", "emoji": "🐋"},
    "0x492442eab586f242b53bda933fd5de859c8a3782": {"name": "April #1", "tier": "whale", "strat": "Спорт, ивенты", "emoji": "🏆"},
    "0xefbc5fec8d7b0acdc8911bdd9a98d6964308f9a2": {"name": "reachingthesky", "tier": "whale", "strat": "Спорт", "emoji": "🐋"},
    "0xc2e7800b5af46e6093872b177b7a5e7f0563be51": {"name": "beachboy4", "tier": "whale", "strat": "Спорт, футбол", "emoji": "🐋"},
    "0xde17f7144fbd0eddb2679132c10ff5e74b120988": {"name": "Crypto Leader", "tier": "dolphin", "strat": "Крипто, DeFi", "emoji": "🐈"},
    "0x2005d16a84ceefa912d4e380cd32e7ff827875ea": {"name": "RN1", "tier": "whale", "strat": "Хай-волюм ротация", "emoji": "🐋"},
    "0xbddf61af533ff524d27154e589d2d7a81510c684": {"name": "Countryside", "tier": "whale", "strat": "Спорт, турниры", "emoji": "🐋"},
}

SIGNAL_TRACKER_FILE = os.path.join(RESULTS_DIR, "signal_tracker.json")
VIRTUAL_TRADES_FILE = os.path.join(RESULTS_DIR, "virtual_trades.json")

def load_signal_tracker():
    if os.path.exists(SIGNAL_TRACKER_FILE):
        with open(SIGNAL_TRACKER_FILE) as f:
            return json.load(f)
    return {"signals": [], "total_pnl": 0, "wins": 0, "losses": 0, "pending": 0}

def save_signal_tracker(tracker):
    with open(SIGNAL_TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)

async def fetch_whale_positions(session, addr):
    """Fetch current positions for a whale address."""
    try:
        url = f"{DATA_API}/positions?user={addr.lower()}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except:
        pass
    return []

async def fetch_top_markets(session, limit=15):
    """Fetch top markets by volume."""
    try:
        url = f"{GAMMA_API}/markets?limit={limit}&order=volume24hr&ascending=false&closed=false"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except:
        pass
    return []

async def fetch_recent_trades(session, limit=200):
    """Fetch recent trades."""
    try:
        url = f"{DATA_API}/trades?limit={limit}&order=desc"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except:
        pass
    return []

async def fetch_crypto_prices(session):
    """Fetch BTC/ETH prices."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum,bitcoin&vs_currencies=usd"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                return {
                    "eth": data.get("ethereum", {}).get("usd", 0),
                    "btc": data.get("bitcoin", {}).get("usd", 0)
                }
    except:
        pass
    return {"eth": 0, "btc": 0}

def generate_trade_instruction(whale_name, side, market_title, size, price, outcome):
    """Generate specific trading instructions for a whale trade."""
    vol = size * price
    instructions = []
    
    # Entry strategy
    if side == "BUY":
        entry_price = price
        if price < 0.30:
            instructions.append(f"📈 Вход: купить YES @ {price:.2f}¢ — лангшот, риск <30% капитала")
            instructions.append(f"🎯 Тейк-профит: {price*3:.0f}¢ (3x) или держи до resolve")
            instructions.append(f"🛑 Стоп-лосс: {(price*0.5):.2f}¢ (потеря 50%)")
        elif price < 0.50:
            instructions.append(f"📈 Вход: купить YES @ {price:.2f}¢ после стабилизации (1-5 мин)")
            instructions.append(f"🎯 Тейк-профит: {(price + 0.15):.0f}¢ (+{0.15/price*100:.0f}%) или до resolve")
            instructions.append(f"🛑 Стоп-лосс: {(price*0.75):.2f}¢ (-25%)")
        elif price < 0.80:
            instructions.append(f"📈 Вход: купить YES @ {price:.2f}¢ — высокая вероятность, низкий ROI")
            instructions.append(f"🎯 Тейк-профит: {(price + 0.08):.0f}¢ (+{0.08/price*100:.0f}%) или держи")
            instructions.append(f"🛑 Стоп-лосс: {(price - 0.10):.2f}¢ (-10-15%)")
        else:
            instructions.append(f"📈 Вход: купить YES @ {price:.2f}¢ — почти гарантировано, но ROI мизерный")
            instructions.append(f"💰 Прибыль: {(1-price)*100:.1f}¢ на доллар если resolve=YES")
            instructions.append(f"⚠️ Риск: {price*100:.0f}¢ на доллар если resolve=NO — НЕ СТОИТ")
    else:  # SELL
        if price > 0.70:
            instructions.append(f"📉 Вход: продать (NO) @ {(1-price):.2f}¢ — кит ставит против")
            instructions.append(f"🎯 Тейк-профит: resolve=NO → профит {(1-price)*100:.1f}¢/$")
            instructions.append(f"🛑 Стоп-лосс: цена YES падает ниже {(price-0.10):.2f}¢")
        elif price > 0.40:
            instructions.append(f"📉 Вход: продать (NO) @ {(1-price):.2f}¢ — средний риск")
            instructions.append(f"🎯 Тейк-профит: {(1-price)*2:.0f}¢ (2x) или до resolve")
            instructions.append(f"🛑 Стоп-лосс: {(1-price)*0.5:.2f}¢ (-50%)")
        else:
            instructions.append(f"📉 Вход: продать (NO) @ {(1-price):.2f}¢ — ВЫСОКИЙ РИСК")
            instructions.append(f"⚠️ YES на {(1-price)*100:.0f}% — если resolve=YES, теряешь {price*100:.0f}¢/$")
    
    # Position sizing
    if vol > 50000:
        instructions.append(f"💰 Размер: кит ставит ${vol:,.0f} — ВЫСОКАЯ убеждённость")
        instructions.append(f"📊 Рекомендация: $100-500 за ним, не больше 5% банкролла")
    elif vol > 10000:
        instructions.append(f"💰 Размер: кит ставит ${vol:,.0f} — средняя убеждённость")
        instructions.append(f"📊 Рекомендация: $50-200 за ним, не больше 3% банкролла")
    else:
        instructions.append(f"💰 Размер: кит ставит ${vol:,.0f} — разведка/тест")
        instructions.append(f"📊 Рекомендация: подожди подтверждения от других китов")
    
    return "\n".join(instructions)

def load_virtual_portfolio():
    """Load virtual trading portfolio for dashboard widget."""
    if os.path.exists(VIRTUAL_TRADES_FILE):
        try:
            with open(VIRTUAL_TRADES_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"balance": 1000, "initial_deposit": 1000, "positions": [], "resolved": [], "total_won": 0, "total_lost": 0, "total_bets": 0, "win_count": 0, "loss_count": 0}

def generate_virtual_trading_html():
    """Generate virtual trading widget HTML from portfolio."""
    vp = load_virtual_portfolio()
    balance = vp.get("balance", 1000)
    initial = vp.get("initial_deposit", 1000)
    positions = vp.get("positions", [])
    resolved = vp.get("resolved", [])
    total_won = vp.get("total_won", 0)
    total_lost = vp.get("total_lost", 0)
    total_bets = vp.get("total_bets", 0)
    win_count = vp.get("win_count", 0)
    loss_count = vp.get("loss_count", 0)
    
    pnl = balance - initial
    pnl_class = "pnl-positive" if pnl >= 0 else "pnl-negative"
    pnl_sign = "+" if pnl >= 0 else ""
    roi = (pnl / initial * 100) if initial > 0 else 0
    roi_class = "pnl-positive" if roi >= 0 else "pnl-negative"
    
    # Active positions
    pos_rows = ""
    for p in positions[:5]:
        market = p.get("market", "?")[:50]
        side = p.get("side", "?")
        amount = p.get("amount", 0)
        entry = p.get("price", 0)
        pos_rows += f'''<div class="pos-item">
          <span class="pos-market">{market}</span>
          <span class="{('side-buy' if side=='BUY' else 'side-sell')}">{side}</span>
          <span class="pos-vol">${amount:,.0f}</span>
        </div>'''
    
    if not pos_rows:
        pos_rows = '<div class="no-pos">Нет открытых позиций</div>'
    
    # Recent resolved
    res_rows = ""
    for r in resolved[-3:]:
        market = r.get("market", "?")[:40]
        result = r.get("result", "?")
        profit = r.get("profit", 0)
        clr = "#00ff88" if profit >= 0 else "#ff4444"
        res_rows += f'''<div class="pos-item">
          <span class="pos-market">{market}</span>
          <span style="color:{clr};font-weight:600">{profit:+,.0f}</span>
          <span class="status-{result.lower()}">{result}</span>
        </div>'''
    
    if not res_rows:
        res_rows = '<div class="no-pos">Нет завершённых</div>'
    
    return f'''
<!-- Virtual Trading Widget -->
<div class="section"><div class="section-title">💼 ВИРТУАЛЬНЫЙ ТРЕЙДИНГ <span class="badge">PAPER</span></div></div>
<div style="background:linear-gradient(135deg,#0d0d1a,#111125);border:1px solid #1a1a3a;border-radius:10px;margin:5px 20px;padding:15px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <div>
      <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px">Баланс</div>
      <div style="font-size:24px;font-weight:700;color:#00ff88">${balance:,.0f}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px">P&L / ROI</div>
      <div style="font-size:18px;font-weight:700" class="{pnl_class}">{pnl_sign}${pnl:,.0f} ({roi:+.1f}%)</div>
    </div>
  </div>
  <div style="display:flex;gap:15px;font-size:10px;color:#888;margin-bottom:10px">
    <span style="color:#00ff88">✅ {win_count}W</span>
    <span style="color:#ff4444">❌ {loss_count}L</span>
    <span>💰 ${total_won:,.0f} won</span>
    <span>💀 ${total_lost:,.0f} lost</span>
    <span>📊 {total_bets} bets</span>
  </div>
  <div style="border-top:1px solid #1a1a3a;padding-top:8px;margin-top:5px">
    <div style="font-size:9px;color:#555;margin-bottom:5px">АКТИВНЫЕ ПОЗИЦИИ</div>
    {pos_rows}
  </div>
  <div style="border-top:1px solid #1a1a3a;padding-top:8px;margin-top:5px">
    <div style="font-size:9px;color:#555;margin-bottom:5px">ПОСЛЕДНИЕ РЕЗУЛЬТАТЫ</div>
    {res_rows}
  </div>
</div>'''

def generate_dashboard(whale_data, markets, prices, tracker, recent_signals):
    """Generate dynamic HTML dashboard."""
    
    # Virtual trading widget (generated below with real data)
    # virtual_trading_html is built at line ~388 with current portfolio data
    
    # Calculate stats
    total_volume = sum(w.get("total_vol", 0) for w in whale_data.values())
    active_whales = sum(1 for w in whale_data.values() if w.get("active"))
    total_positions = sum(len(w.get("positions", [])) for w in whale_data.values())
    
    # P&L data
    pnl = tracker.get("total_pnl", 0)
    wins = tracker.get("wins", 0)
    losses = tracker.get("losses", 0)
    pending = tracker.get("pending", 0)
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    
    # Build signal cards HTML
    signal_cards = ""
    for sig in recent_signals[:8]:
        whale_name = sig.get("whale_name", "?")
        side = sig.get("side", "?")
        market = sig.get("market", "?")
        price = sig.get("price", 0)
        size = sig.get("size", 0)
        vol = size * price
        outcome = sig.get("outcome", "?")
        instructions = sig.get("instructions", "")
        pnl_val = sig.get("pnl", 0)
        status = sig.get("status", "pending")
        
        pnl_class = "pnl-positive" if pnl_val > 0 else "pnl-negative" if pnl_val < 0 else "pnl-pending"
        pnl_text = f"+${pnl_val:,.0f}" if pnl_val > 0 else f"-${abs(pnl_val):,.0f}" if pnl_val < 0 else "PENDING"
        status_badge = f'<span class="status-{status}">{status.upper()}</span>'
        
        side_class = "side-buy" if side == "BUY" else "side-sell"
        
        signal_cards += f'''
        <div class="signal-card fade-in">
          <div class="signal-header">
            <span class="signal-whale">{sig.get("emoji","🐋")} {whale_name}</span>
            <span class="signal-side {side_class}">{side}</span>
            <span class="signal-pnl {pnl_class}">{pnl_text}</span>
            {status_badge}
          </div>
          <div class="signal-market">{market[:80]}</div>
          <div class="signal-details">
            <span>💰 ${vol:,.0f}</span>
            <span>📊 @ {price*100:.1f}¢</span>
            <span>📐 {size:,.0f} shares</span>
          </div>
          <div class="signal-instructions">
            <div class="instr-title">📋 ИНСТРУКЦИЯ:</div>
            <pre class="instr-text">{instructions}</pre>
          </div>
          <div class="signal-pnl-popup {pnl_class}" data-pnl="{pnl_val}">${pnl_val:+,.0f}</div>
        </div>'''
    
    # Build whale position cards
    whale_cards = ""
    for addr, info in WHALES.items():
        w = whale_data.get(addr, {})
        positions = w.get("positions", [])
        active_count = len(positions)
        w_vol = w.get("total_vol", 0)
        is_active = w.get("active", False)
        act_class = "active" if is_active else "inactive"
        
        pos_html = ""
        for p in positions[:4]:
            title = p.get("title", "?")[:40]
            size_p = float(p.get("size", 0))
            price_p = float(p.get("price", 0))
            side_p = p.get("side", "?")
            vol_p = p.get("currentValue", size_p * price_p)
            outcome_p = p.get("outcome", "?")
            
            cash_pnl_p = p.get("cashPnl", 0)
            pct_pnl_p = p.get("percentPnl", 0)
            pnl_clr = "#00ff88" if cash_pnl_p >= 0 else "#ff4444"
            current_val = p.get("currentValue", vol_p)
            pos_html += f"""
            <div class="pos-item">
              <span class="pos-market">{title}</span>
              <span style="color:{pnl_clr};font-weight:600">{cash_pnl_p:+,.0f} ({pct_pnl_p:+.0f}%)</span>
              <span class="pos-vol">${current_val:,.0f}</span>
              <span class="pos-price">@ {price_p*100:.1f}¢</span>
            </div>"""
        
        whale_cards += f'''
        <div class="whale-card {act_class} fade-in">
          <div class="whale-header">
            <span class="whale-emoji">{info["emoji"]}</span>
            <span class="whale-name">{info["name"]}</span>
            <span class="whale-tier">{info["tier"]}</span>
            <span class="whale-positions">{active_count} поз.</span>
          </div>
          <div class="whale-strat">{info["strat"]}</div>
          <div class="whale-positions-list">{pos_html if pos_html else '<div class="no-pos">Нет открытых позиций</div>'}</div>
        </div>'''
    
    # Build market list
    market_html = ""
    for m in markets[:12]:
        question = m.get("question", "?")[:70]
        vol_24h = float(m.get("volume24hr", 0) or 0)
        slug = m.get("slug", "")
        cat = m.get("category", "other")
        cat_colors = {"geopolitics": "#ff4444", "macro": "#4488ff", "crypto": "#ffaa00", 
                      "sports": "#00ff88", "politics": "#aa66ff", "other": "#666"}
        cat_color = cat_colors.get(cat, "#666")
        
        market_html += f'''
        <div class="market-item">
          <span style="color:{cat_color}">{cat[:4]}</span> {question}
          <span class="market-vol">${vol_24h/1e6:.1f}M</span>
        </div>'''
    
    now_str = datetime.now(timezone(timedelta(hours=2))).strftime("%d.%m.%Y %H:%M")
    
    # Build virtual trading widget
    portfolio = load_virtual_portfolio()
    open_positions = portfolio.get("positions", [])
    resolved_positions = portfolio.get("resolved", [])
    balance = portfolio.get("balance", 1000)
    initial_deposit = portfolio.get("initial_deposit", 1000)
    total_won = portfolio.get("total_won", 0)
    total_lost = portfolio.get("total_lost", 0)
    win_count = portfolio.get("win_count", 0)
    loss_count = portfolio.get("loss_count", 0)
    total_bets = portfolio.get("total_bets", 0)
    total_value = balance + sum(p.get("cur_price", 0) * p.get("shares", 0) for p in open_positions)
    open_pnl = sum(p.get("pnl", 0) for p in open_positions)
    total_pnl = total_won - total_lost + open_pnl
    roi = ((total_value - initial_deposit) / initial_deposit) * 100 if initial_deposit > 0 else 0
    win_rate = (win_count / (win_count + loss_count) * 100) if (win_count + loss_count) > 0 else 0
    
    # Build position rows for widget
    pos_rows = ""
    for p in open_positions[:8]:
        pnl = p.get("pnl", 0)
        pnl_color = "#00ff88" if pnl >= 0 else "#ff4444"
        entry = p.get("entry_price", 0)
        pos_id = p.get("id", "")
        pos_label = f'{p.get("whale","?")}: {p.get("outcome","?")} {p.get("market","?")[:20]}'
        pnl_size = "font-size:16px" if abs(pnl) > 10 else "font-size:13px"
        pos_rows += f'''
    <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 4px;border-bottom:1px solid #1a1a3a;font-size:11px;flex-wrap:wrap;gap:4px;background:linear-gradient(90deg,#0a0f0a,#0d0d1a);border-radius:6px;margin:2px 0">
      <span style="color:#ccc;flex:1;min-width:100px;font-size:10px">{p.get("whale","?")}: <span style="color:#00ff88;font-weight:600">{p.get("outcome","?")}</span> {p.get("market","?")[:25]}</span>
      <span style="color:#ffaa00;font-weight:700;margin:0 6px;font-size:12px">${p.get("bet_size",50):.0f} @ {entry*100:.0f}¢</span>
      <span style="color:{pnl_color};font-weight:900;margin-right:8px;{pnl_size};text-shadow:0 0 10px {pnl_color}66">{pnl:+,.2f}</span>
      <button onclick="showClose('{pos_id}','{pos_label}')" style="background:#1a1a0a;border:1px solid #ffaa0033;color:#ffaa00;padding:3px 10px;border-radius:6px;cursor:pointer;font-size:10px;font-weight:600;transition:all .2s">✕</button>
    </div>'''
    
    roi_color = "#00ff88" if roi >= 0 else "#ff4444"
    total_pnl_color = "#00ff88" if total_pnl >= 0 else "#ff4444"
    roi_bg = "1a0a" if roi >= 0 else "0a0a"
    roi_green_red = "1a0d" if roi >= 0 else "0d1a"

    # Animated counter values for JS
    animated_balance = f"{balance:,.2f}"
    animated_roi = f"{roi:+.1f}"
    animated_pnl = f"{total_pnl:+,.2f}"
    
    # Resolved bets section
    resolved_positions = portfolio.get("resolved", [])
    res_rows = ""
    for r in resolved_positions[-5:]:
        result_icon = "✅" if r.get("result") == "win" else "❌"
        res_pnl = r.get("pnl", 0)
        res_color = "#00ff88" if res_pnl >= 0 else "#ff4444"
        res_rows += f'''
    <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #0a0a15;font-size:10px">
      <span>{result_icon} <span style="color:#888">{r.get("whale","?")}: {r.get("outcome","?")} {r.get("market","?")[:20]}</span></span>
      <span style="color:{res_color};font-weight:600">${res_pnl:+,.2f}</span>
    </div>'''
    
    virtual_trading_html = f'''
    <div class="section" style="margin-top:20px"><div class="section-title">🎰 ВИРТУАЛЬНЫЙ ДЕПОЗИТ <span class="badge">PAPER TRADING</span></div></div>

    <div style="background:linear-gradient(135deg,#0a1a0a,#1a2a0a);border:3px solid #00ff8855;border-radius:20px;padding:25px;margin:10px 20px;box-shadow:0 0 40px #00ff8815,inset 0 0 60px #00ff8805">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:20px">
        <div style="text-align:center;flex:1;min-width:110px;padding:10px;background:linear-gradient(180deg,#0d1a0d,#0a120a);border-radius:12px;border:1px solid #00ff8822">
          <div style="font-size:10px;color:#666;text-transform:uppercase;letter-spacing:2px;margin-bottom:4px">💰 Баланс</div>
          <div id="counter-balance" style="font-size:42px;font-weight:700;color:#00ff88;text-shadow:0 0 20px #00ff8844;animation:glow 2s ease-in-out infinite alternate">${balance:,.0f}</div>
        </div>
        <div style="text-align:center;flex:1;min-width:110px;padding:10px;background:linear-gradient(180deg,#0d0d1a,#0a0a15);border-radius:12px;border:1px solid #4488ff22">
          <div style="font-size:10px;color:#666;text-transform:uppercase;letter-spacing:2px;margin-bottom:4px">📊 Ставок</div>
          <div style="font-size:42px;font-weight:700;color:#4488ff;text-shadow:0 0 15px #4488ff33">{len(open_positions)}</div>
        </div>
        <div style="text-align:center;flex:1;min-width:110px;padding:10px;background:linear-gradient(180deg,#1a1a0a,#15150a);border-radius:12px;border:1px solid #ffaa0022">
          <div style="font-size:10px;color:#666;text-transform:uppercase;letter-spacing:2px;margin-bottom:4px">🏆 Win Rate</div>
          <div style="font-size:42px;font-weight:700;color:#ffaa00;text-shadow:0 0 15px #ffaa0033">{win_rate:.0f}%</div>
        </div>
        <div style="text-align:center;flex:1;min-width:110px;padding:10px;background:linear-gradient(180deg,#0a1a0a,#0a150a);border-radius:12px;border:1px solid {roi_color}33">
          <div style="font-size:10px;color:#666;text-transform:uppercase;letter-spacing:2px;margin-bottom:4px">📈 ROI</div>
          <div style="font-size:42px;font-weight:700;color:{roi_color};text-shadow:0 0 20px {roi_color}44">{roi:+.1f}%</div>
        </div>
      </div>'

      <div style="border-top:2px solid #1a1a3a;padding-top:16px;margin-top:12px">
        <div style="font-size:11px;color:#ffaa00;margin-bottom:10px;text-transform:uppercase;letter-spacing:2px;font-weight:700">⚡ Открытые ставки ({len(open_positions)})</div>
        {pos_rows if pos_rows else '<div style="color:#333;text-align:center;padding:10px">Нет открытых ставок — /bet чтобы поставить</div>'}
        <div style="margin-top:12px;padding-top:10px;border-top:2px solid #1a1a3a;font-size:11px;color:#ffaa00;text-transform:uppercase;letter-spacing:2px;font-weight:700">📜 История ({len(resolved_positions)} закрыто)</div>
        {res_rows if res_rows else '<div style="color:#333;text-align:center;padding:5px">Ещё нет закрытых ставок</div>'}
        <div style="margin-top:16px;padding-top:12px;border-top:2px solid #1a1a3a;font-size:11px;color:#888;line-height:2">
          💰 Депозит: <span style="color:#00ff88;font-weight:700">${initial_deposit:.0f}</span> | 💵 Выиграно: <span style="color:#00ff88;font-weight:700">${total_won:.2f}</span> | 💸 Проиграно: <span style="color:#ff4444;font-weight:700">${total_lost:.2f}</span><br>
          📊 P&L: <span style="color:{total_pnl_color};font-size:14px;font-weight:700">${total_pnl:+,.2f}</span> | 📈 Старт: ${initial_deposit:.0f} | Сейчас: <span style="color:#00ff88;font-weight:700">${total_value:,.2f}</span>
        </div>
      </div>

      <!-- ACTION BUTTONS -->
      <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;justify-content:center">
        <button onclick="loadSignals()" style="background:linear-gradient(135deg,#1a3a1a,#0a2a0a);border:1px solid #00ff8855;color:#00ff88;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:11px;font-weight:600;transition:all .2s">🎰 Ставка</button>
        <button onclick="topUp()" style="background:linear-gradient(135deg,#1a2a1a,#0a1a0a);border:1px solid #4488ff55;color:#4488ff;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:11px;font-weight:600;transition:all .2s">➕ Пополнить</button>
        <button onclick="refreshPortfolio()" style="background:linear-gradient(135deg,#1a1a2a,#0a0a1a);border:1px solid #aaa55;color:#aaa;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:11px;font-weight:600;transition:all .2s">🔄 Обновить</button>
      </div>
    </div>

    <!-- SIGNAL MODAL -->
    <div id="signalModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:1000;overflow-y:auto">
      <div style="max-width:500px;margin:40px auto;background:#0d0d1a;border:2px solid #00ff8833;border-radius:15px;padding:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px">
          <h2 style="color:#00ff88;font-size:14px;margin:0">🎰 СИГНАЛЫ КИТОВ</h2>
          <button onclick="closeModal()" style="background:none;border:1px solid #333;color:#ff4444;padding:4px 10px;border-radius:5px;cursor:pointer;font-size:12px">✕</button>
        </div>
        <div id="signalList" style="max-height:60vh;overflow-y:auto">
          <div style="color:#666;text-align:center;padding:20px">Загрузка...</div>
        </div>
      </div>
    </div>

    <!-- CLOSE POSITION MODAL -->
    <div id="closeModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:1000">
      <div style="max-width:400px;margin:80px auto;background:#0d0d1a;border:2px solid #ffaa0033;border-radius:15px;padding:20px;text-align:center">
        <h2 style="color:#ffaa00;font-size:14px;margin-bottom:15px">📋 ЗАКРЫТЬ СТАВКУ</h2>
        <p id="closeInfo" style="color:#888;font-size:11px;margin-bottom:15px"></p>
        <div style="display:flex;gap:10px;justify-content:center">
          <button id="closeWinBtn" onclick="closePosition('win')" style="background:#0a2a0a;border:2px solid #00ff88;color:#00ff88;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:700">✅ WIN</button>
          <button id="closeLossBtn" onclick="closePosition('loss')" style="background:#2a0a0a;border:2px solid #ff4444;color:#ff4444;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:700">❌ LOSS</button>
        </div>
        <button onclick="document.getElementById('closeModal').style.display='none'" style="background:none;border:1px solid #333;color:#888;padding:6px 16px;border-radius:5px;cursor:pointer;font-size:11px;margin-top:10px">Отмена</button>
      </div>
    </div>

    <!-- TOAST -->
    <div id="toast" style="display:none;position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#1a1a2a;border:1px solid #00ff88;color:#00ff88;padding:12px 24px;border-radius:10px;font-size:12px;z-index:2000;transition:opacity .3s"></div>

    <script src="dashboard.js"></script>

    <div style="background:#0d0d1a;border:1px solid #1a1a3a;border-radius:10px;padding:15px;margin:10px 20px">
      <h3 style="color:#00ff88;font-size:12px;margin-bottom:10px">⚡ КАК ИСПОЛЬЗОВАТЬ</h3>
      <div style="font-size:10px;color:#999;line-height:1.8">
        <div>1️⃣ <b style="color:#ffaa00">🎰 Ставка</b> — сигналы китов + кнопки ставок по $50</div>
        <div>2️⃣ <b style="color:#ffaa00">❌ WIN/LOSS</b> — закрыть позицию прямо из дашборда</div>
        <div>3️⃣ <b style="color:#ffaa00">➕ Пополнить</b> — +$500 к депозиту</div>
        <div>4️⃣ <b style="color:#ffaa00">🔄 Обновить</b> — синхронизировать с ботом</div>
        <div style="margin-top:8px;color:#ff4444">⚠️ Это симуляция. Реальные деньги НЕ используются. Синхронизировано с Telegram ботом.</div>
      </div>
    </div>'''

    # virtual_trading_html already includes everything above (buttons, modals, JS, instructions)
    
    # Build P&L floating numbers — ALWAYS show +, big numbers
    pnl_animations = ""
    pnl_display_vals = []
    for i, sig in enumerate(recent_signals[:6]):
        pnl_v = sig.get("pnl", 0)
        pnl_display_vals.append(pnl_v if pnl_v != 0 else 0)
    
    # If no signals, show demo numbers
    if not pnl_display_vals:
        pnl_display_vals = [12, 45, 23, 67, 34, 89]
    
    for i, pnl_v in enumerate(pnl_display_vals[:6]):
        color = "#00ff88" if pnl_v >= 0 else "#ff4444"
        delay = i * 0.7
        left_pos = 5 + (i * 16) % 85
        sign = "+" if pnl_v >= 0 else "-"
        pnl_animations += f'''
        <div class="float-number" style="animation-delay:{delay}s;color:{color};left:{left_pos}%">{sign}${abs(pnl_v):,.0f}</div>'''
    
    dashboard = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐋 NANO Polymarket Whale Tracker v3.0</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#060610;color:#e0e0e0;font-family:'JetBrains Mono',monospace;min-height:100vh;overflow-x:hidden}}

body::before{{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(ellipse at 20% 50%,#0a1a2a 0%,transparent 50%),radial-gradient(ellipse at 80% 20%,#1a0a2e 0%,transparent 50%),radial-gradient(ellipse at 50% 80%,#0a2a1a 0%,transparent 50%);z-index:-1;animation:bgPulse 8s ease-in-out infinite alternate}}
@keyframes bgPulse{{0%{{opacity:.6}}100%{{opacity:1}}}}

body::after{{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,136,0.015) 2px,rgba(0,255,136,0.015) 4px);pointer-events:none;z-index:9999}}

/* Floating P&L numbers */
.float-container{{position:fixed;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:100;overflow:hidden}}
.float-number{{position:absolute;font-size:96px;font-weight:900;text-shadow:0 0 40px currentColor,0 0 80px currentColor,0 0 120px currentColor;opacity:0;animation:floatUp 5s ease-out infinite}}
@keyframes floatUp{{0%{{opacity:0;transform:translateY(100vh) scale(0.2)}}8%{{opacity:1;transform:translateY(75vh) scale(1.8)}}20%{{opacity:0.95;transform:translateY(50vh) scale(1.3)}}40%{{opacity:0.7;transform:translateY(20vh) scale(1)}}60%{{opacity:0.4;transform:translateY(-10vh) scale(0.7)}}100%{{opacity:0;transform:translateY(-30vh) scale(0.3)}}}}

.header{{background:linear-gradient(135deg,#0a0a1f 0%,#1a0a2e 50%,#0a1a1f 100%);border-bottom:1px solid #00ff8833;padding:25px 20px;text-align:center;position:relative;overflow:hidden}}
.header::before{{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:conic-gradient(from 0deg,transparent,#00ff8808,transparent,#00ff8808,transparent);animation:rotateBg 20s linear infinite}}
@keyframes rotateBg{{to{{transform:rotate(360deg)}}}}
.header h1{{font-size:28px;color:#00ff88;text-shadow:0 0 30px #00ff8866,0 0 60px #00ff8833;position:relative;z-index:1;letter-spacing:2px}}
.header .subtitle{{color:#666;font-size:11px;margin-top:5px;position:relative;z-index:1}}
.live-dot{{display:inline-block;width:8px;height:8px;background:#00ff88;border-radius:50%;margin-right:8px;animation:livePulse 1.5s ease-in-out infinite}}
@keyframes livePulse{{0%,100%{{box-shadow:0 0 0 0 #00ff8888}}50%{{box-shadow:0 0 0 8px #00ff8800}}}}

/* Stats */
.stats-row{{display:flex;gap:12px;padding:15px 20px;flex-wrap:wrap}}
.stat-card{{flex:1;min-width:100px;background:linear-gradient(135deg,#0d0d1a,#111125);border:1px solid #1a1a3a;border-radius:10px;padding:15px 10px;text-align:center;position:relative;overflow:hidden;transition:all .3s}}
.stat-card:hover{{border-color:#00ff8855;transform:translateY(-2px);box-shadow:0 5px 20px #00ff8811}}
.stat-card::after{{content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;background:linear-gradient(90deg,transparent,#ffffff06,transparent);animation:shimmer 3s infinite}}
@keyframes shimmer{{to{{left:100%}}}}
.stat-card .label{{font-size:9px;color:#555;text-transform:uppercase;letter-spacing:1.5px}}
.stat-card .value{{font-size:20px;color:#00ff88;margin-top:4px;font-weight:700}}
.stat-card .value.red{{color:#ff4444}}.stat-card .value.blue{{color:#4488ff}}.stat-card .value.yellow{{color:#ffaa00}}.stat-card .value.purple{{color:#aa66ff}}

/* P&L counter */
.pnl-hero{{background:linear-gradient(135deg,#0a1a0a,#1a2a0a);border:3px solid #00ff8855;border-radius:20px;padding:30px;margin:10px 20px;text-align:center;position:relative;overflow:hidden;box-shadow:0 0 60px #00ff8815,inset 0 0 40px #00ff8805}}
.pnl-hero .pnl-label{{font-size:12px;color:#888;text-transform:uppercase;letter-spacing:3px;margin-bottom:4px}}
.pnl-hero .pnl-value{{font-size:96px;font-weight:900;margin-top:8px;transition:all .8s cubic-bezier(.2,1,.3,1);animation:pnlGlow 2s ease-in-out infinite alternate}}
.pnl-hero .pnl-value.positive{{color:#00ff88;text-shadow:0 0 40px #00ff8866,0 0 80px #00ff8844,0 0 120px #00ff8822}}
.pnl-hero .pnl-value.negative{{color:#ff4444;text-shadow:0 0 40px #ff444466,0 0 80px #ff444444,0 0 120px #ff444422}}
.pnl-hero .pnl-details{{font-size:15px;color:#aaa;margin-top:16px;letter-spacing:2px}}
.pnl-hero .pnl-details span{{margin:0 14px}}
@keyframes pnlGlow{{0%{{filter:brightness(1);transform:scale(1)}}50%{{filter:brightness(1.15);transform:scale(1.02)}}100%{{filter:brightness(1);transform:scale(1)}}}}

/* Signals */
.section{{padding:8px 20px}}
.section-title{{color:#00ff88;font-size:13px;margin-bottom:12px;border-left:3px solid #00ff88;padding-left:10px;display:flex;align-items:center;gap:8px}}
.section-title .badge{{background:#00ff8822;color:#00ff88;font-size:10px;padding:2px 8px;border-radius:10px;font-weight:400}}

.signal-card{{background:linear-gradient(135deg,#0d0d1a,#111125);border:1px solid #1a1a3a;border-radius:10px;padding:15px;margin:8px 20px;position:relative;overflow:hidden;transition:all .3s}}
.signal-card:hover{{border-color:#00ff8844;box-shadow:0 5px 25px #00ff8811}}
.signal-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:5px}}
.signal-whale{{color:#00ff88;font-weight:700;font-size:13px}}
.signal-side{{font-size:10px;padding:2px 8px;border-radius:5px;font-weight:700}}
.side-buy{{background:#00ff8822;color:#00ff88}}.side-sell{{background:#ff444422;color:#ff4444}}
.signal-pnl{{font-size:16px;font-weight:700}}
.pnl-positive{{color:#00ff88;text-shadow:0 0 10px #00ff8844}}.pnl-negative{{color:#ff4444;text-shadow:0 0 10px #ff444444}}.pnl-pending{{color:#ffaa00}}
.status-win{{background:#00ff8822;color:#00ff88;padding:2px 6px;border-radius:4px;font-size:9px}}.status-loss{{background:#ff444422;color:#ff4444;padding:2px 6px;border-radius:4px;font-size:9px}}.status-pending{{background:#ffaa0022;color:#ffaa00;padding:2px 6px;border-radius:4px;font-size:9px}}
.signal-market{{color:#aaa;font-size:11px;margin-bottom:6px}}
.signal-details{{display:flex;gap:15px;font-size:10px;color:#888;margin-bottom:10px}}
.signal-instructions{{background:#0a0a15;border:1px solid #1a1a3a;border-radius:8px;padding:10px;margin-top:8px}}
.instr-title{{color:#ffaa00;font-size:10px;margin-bottom:5px;letter-spacing:1px}}
.instr-text{{color:#ccc;font-size:10px;line-height:1.6;white-space:pre-wrap;font-family:'JetBrains Mono',monospace}}
.signal-pnl-popup{{position:absolute;top:5px;right:10px;font-size:56px;font-weight:900;opacity:0;animation:pnlPop 4s ease-out infinite 1.5s}}
@keyframes pnlPop{{0%{{opacity:0;transform:scale(0.2) translateY(30px)}}15%{{opacity:1;transform:scale(1.4) translateY(0)}}30%{{opacity:0.9;transform:scale(1.1)}}50%{{opacity:0.6;transform:scale(0.95)}}100%{{opacity:0;transform:scale(0.4) translateY(-40px)}}}}

/* Whale cards */
.whale-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;padding:5px 20px}}
.whale-card{{background:linear-gradient(135deg,#0d0d1a,#111125);border:1px solid #1a1a3a;border-radius:10px;padding:15px;transition:all .3s}}
.whale-card.active{{border-color:#00ff8833}}.whale-card.inactive{{border-color:#1a1a3a;opacity:.6}}
.whale-card:hover{{border-color:#00ff8855;box-shadow:0 5px 20px #00ff8811}}
.whale-header{{display:flex;align-items:center;gap:8px;margin-bottom:5px}}
.whale-emoji{{font-size:18px}}.whale-name{{color:#00ff88;font-weight:700;font-size:13px}}.whale-tier{{color:#666;font-size:9px;padding:1px 6px;border:1px solid #333;border-radius:3px;margin-left:auto}}.whale-positions{{color:#ffaa00;font-size:10px}}
.whale-strat{{color:#555;font-size:10px;margin-bottom:8px}}
.whale-positions-list .pos-item{{display:flex;gap:8px;font-size:10px;padding:3px 0;border-bottom:1px solid #111}}
.pos-market{{color:#aaa;flex:1}}.pos-vol{{color:#ffaa00;font-weight:600}}
.no-pos{{color:#333;font-size:10px;font-style:italic}}

/* Markets */
.market-item{{padding:8px 5px;border-bottom:1px solid #0a0a15;font-size:11px;display:flex;justify-content:space-between;align-items:center}}
.market-vol{{color:#ffaa00;font-size:10px;font-weight:600}}

.fade-in{{animation:fadeIn .5s ease-out}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}

.refresh-bar{{position:fixed;bottom:0;left:0;right:0;background:#060610ee;border-top:1px solid #1a1a3a;padding:8px 20px;display:flex;justify-content:space-between;font-size:10px;color:#444;z-index:50}}
.spinner{{display:inline-block;width:12px;height:12px;border:2px solid #1a1a3a;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}

@media(max-width:768px){{.stats-row{{gap:8px}}.stat-card{{min-width:70px;padding:10px 5px}}.stat-card .value{{font-size:16px}}.header h1{{font-size:20px}}.whale-grid{{grid-template-columns:1fr}}.pnl-hero .pnl-value{{font-size:32px}}}}
</style>
</head>
<body>

<div class="float-container">{pnl_animations}</div>

<div class="header">
  <h1>🐋 NANO POLYMARKET WHALE TRACKER v3.0</h1>
  <div class="subtitle"><span class="live-dot"></span>Real-time + Trade Instructions + P&L • <span id="timestamp">{now_str}</span></div>
</div>

<div class="stats-row fade-in">
  <div class="stat-card"><div class="label">Active Whales</div><div class="value">{active_whales}/{len(WHALES)}</div></div>
  <div class="stat-card"><div class="label">Positions</div><div class="value blue">{total_positions}</div></div>
  <div class="stat-card"><div class="label">Signals</div><div class="value yellow">{len(recent_signals)}</div></div>
  <div class="stat-card"><div class="label">Win Rate</div><div class="value {"" if win_rate > 50 else "red"}">{win_rate:.0f}%</div></div>
  <div class="stat-card"><div class="label">ETH</div><div class="value purple">${prices.get("eth",0):,.0f}</div></div>
  <div class="stat-card"><div class="label">BTC</div><div class="value purple">${prices.get("btc",0):,.0f}</div></div>
</div>

<!-- P&L Hero -->
<div class="pnl-hero fade-in">
  <div class="pnl-label">📈 Если бы ты отработал все сигналы</div>
  <div class="pnl-value {"positive" if pnl >= 0 else "negative"}">{"+" if pnl >= 0 else "-"}${abs(pnl):,.0f}</div>
  <div class="pnl-details">
    <span style="color:#00ff88">✅ {wins} wins</span>
    <span style="color:#ff4444">❌ {losses} losses</span>
    <span style="color:#ffaa00">⏳ {pending} pending</span>
  </div>
</div>

<!-- Recent Signals with Instructions -->
<div class="section"><div class="section-title">📋 ПОСЛЕДНИЕ СИГНАЛЫ + ИНСТРУКЦИИ <span class="badge">LIVE</span></div></div>
{signal_cards if signal_cards else '<div style="padding:20px;color:#333;text-align:center">Сигналов пока нет — киты отдыхают 🐋</div>'}

<!-- Whale Positions -->
<div class="section"><div class="section-title">🐋 ПОЗИЦИИ КИТОВ <span class="badge">TOP 10</span></div></div>
<div class="whale-grid fade-in">
{whale_cards}
</div>

<!-- Hot Markets -->
<div class="section"><div class="section-title">🔥 HOT MARKETS <span class="badge">24H VOLUME</span></div></div>
<div class="section fade-in" style="max-height:350px;overflow-y:auto">
{market_html if market_html else '<div style="color:#333;text-align:center;padding:20px">Маркеты не загружены</div>'}
</div>

<!-- Virtual Trading Widget -->
{virtual_trading_html}

<!-- Strategy Guide -->
<div class="section" style="margin-top:15px"><div class="section-title">💰 СТРАТЕГИИ <span class="badge">GUIDE</span></div></div>
<div style="padding:5px 20px 80px 20px;font-size:10px;color:#888;line-height:1.8">
<div style="background:#0d0d1a;border:1px solid #1a1a3a;border-radius:10px;padding:15px">
  <h3 style="color:#00ff88;font-size:12px;margin-bottom:10px">⚡ КАК ПОЛЬЗОВАТЬСЯ СИГНАЛАМИ</h3>
  <div>1️⃣ <b style="color:#ffaa00">Смотри сигналы выше</b> — каждый сигнал содержит конкретную инструкцию: когда входить, где тейк-профит, где стоп-лосс</div>
  <div>2️⃣ <b style="color:#ffaa00">P&L трекер</b> — мы считаем сколько ты бы заработал если отработал каждый сигнал на $100</div>
  <div>3️⃣ <b style="color:#ffaa00">Входи ПОСЛЕ кита</b> — не вместе с ним. Подожди стабилизации цены 1-5 минут</div>
  <div>4️⃣ <b style="color:#ff4444">Стоп-лосс = жизнь</b> — каждый сигнал содержит точный стоп-лосс</div>
  <div>5️⃣ <b style="color:#00ff88">Выходи раньше кита</b> — забирай прибыль и беги 💀</div>
</div>
</div>

<div class="refresh-bar">
  <span class="status"><span class="spinner"></span> LIVE • Auto-refresh <span id="countdown">120</span>s</span>
  <span style="color:#444">NANO Whale Tracker v3.0 • Polymarket API</span>
  <span style="color:#555" id="update-time">{now_str}</span>
</div>

<script>
let cd=120;
setInterval(()=>{{
  cd--;
  document.getElementById('countdown').textContent=cd;
  if(cd<=0){{cd=120;location.reload();}}
}},1000);
</script>
</body>
</html>'''
    
    return dashboard


async def collect_data_and_generate():
    """Main data collection + dashboard generation."""
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Collecting data...")
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        # Parallel fetches
        prices_task = fetch_crypto_prices(session)
        markets_task = fetch_top_markets(session)
        trades_task = fetch_recent_trades(session)
        
        prices, markets, trades = await asyncio.gather(prices_task, markets_task, trades_task)
        
        # Fetch whale positions
        whale_data = {}
        for addr, info in WHALES.items():
            positions = await fetch_whale_positions(session, addr)
            # Filter positions > $50
            active_positions = []
            for p in positions:
                try:
                    size = float(p.get("size", 0) or 0)
                    avg_price = float(p.get("avgPrice", 0) or 0)
                    cur_price = float(p.get("curPrice", 0) or 0)
                    current_value = float(p.get("currentValue", 0) or 0)
                    initial_value = float(p.get("initialValue", 0) or 0)
                    cash_pnl = float(p.get("cashPnl", 0) or 0)
                    pct_pnl = float(p.get("percentPnl", 0) or 0)
                    if current_value > 50 or initial_value > 50:
                        outcome = p.get("outcome", "?")
                        side = "BUY"
                        active_positions.append({
                            "title": p.get("title", p.get("market", "?")),
                            "size": size,
                            "price": cur_price or avg_price,
                            "avgPrice": avg_price,
                            "curPrice": cur_price,
                            "side": side,
                            "outcome": outcome,
                            "currentValue": current_value,
                            "initialValue": initial_value,
                            "cashPnl": cash_pnl,
                            "percentPnl": pct_pnl,
                        })
                except:
                    continue
            
            # Match whale against recent trades
            whale_trades = [t for t in trades if (t.get("proxyWallet","") or t.get("taker","")).lower() == addr.lower()]
            total_vol = sum(float(p.get("currentValue",0) or 0) for p in positions[:30])
            
            whale_data[addr] = {
                "positions": active_positions[:10],
                "active": len(active_positions) > 0 or len(whale_trades) > 0,
                "total_vol": total_vol,
            }
        
        # Build recent signals from whale trades
        tracker = load_signal_tracker()
        recent_signals = tracker.get("signals", [])[-20:]
        
        # Also generate signals from current trades
        for t in trades[:500]:
            addr = (t.get("proxyWallet", "") or t.get("taker", "")).lower()
            whale_info = None
            for wa, wi in WHALES.items():
                if wa.lower() == addr:
                    whale_info = wi
                    break
            
            if not whale_info:
                continue
            
            size = float(t.get("size", 0) or 0)
            price = float(t.get("price", 0) or 0)
            vol = size * price
            if vol < 100:
                continue
            
            market_title = t.get("market", t.get("title", "?"))
            side = t.get("side", "?")
            
            # Check if already tracked
            sig_key = f"{addr}:{market_title}:{side}:{size:.0f}"
            existing = [s for s in recent_signals if s.get("key") == sig_key]
            if existing:
                continue
            
            instructions = generate_trade_instruction(
                whale_info["name"], side, market_title, size, price, t.get("outcome", "?")
            )
            
            signal = {
                "key": sig_key,
                "whale_name": whale_info["name"],
                "emoji": whale_info["emoji"],
                "side": side,
                "market": market_title,
                "size": size,
                "price": price,
                "instructions": instructions,
                "pnl": 0,  # Will be calculated when market resolves
                "status": "pending",
                "timestamp": time.time(),
            }
            recent_signals.append(signal)
        
        # Save updated signals
        tracker["signals"] = recent_signals[-50:]
        save_signal_tracker(tracker)
        
        # Generate dashboard
        dashboard = generate_dashboard(whale_data, markets, prices, tracker, recent_signals)
        
        # Write
        dash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
        with open(dash_path, "w", encoding="utf-8") as f:
            f.write(dashboard)
        
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Dashboard updated! {len(whale_data)} whales, {len(markets)} markets, {len(recent_signals)} signals")
        
        # Auto-deploy to gh-pages
        try:
            import subprocess, shutil
            repo_dir = os.path.dirname(os.path.abspath(__file__))
            # Commit to main
            subprocess.run(["git", "add", "dashboard.html"], cwd=repo_dir, capture_output=True, timeout=10)
            subprocess.run(["git", "commit", "-m", "dashboard auto-refresh"], cwd=repo_dir, capture_output=True, timeout=10)
            subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, timeout=30)
            # Deploy to gh-pages by copying files directly (no branch switching)
            gh_dir = repo_dir + "-gh-pages"
            if os.path.exists(gh_dir):
                subprocess.run(["git", "pull"], cwd=gh_dir, capture_output=True, timeout=15)
            else:
                subprocess.run(["git", "clone", "-b", "gh-pages", "https://github.com/FuckFiat/polymarket-whale-tracker.git", gh_dir], capture_output=True, timeout=30)
            # Copy dashboard as BOTH dashboard.html AND index.html (GitHub Pages serves index.html)
            src = os.path.join(repo_dir, "dashboard.html")
            dst_dashboard = os.path.join(gh_dir, "dashboard.html")
            dst_index = os.path.join(gh_dir, "index.html")
            dst_js = os.path.join(gh_dir, "dashboard.js")
            shutil.copy2(src, dst_dashboard)
            shutil.copy2(src, dst_index)  # index.html is what GitHub Pages actually serves
            # Copy dashboard.js for interactive buttons
            js_src = os.path.join(repo_dir, "dashboard.js")
            if os.path.exists(js_src):
                shutil.copy2(js_src, dst_js)
            # Copy virtual trades
            vt_src = os.path.join(repo_dir, "results", "virtual_trades.json")
            if os.path.exists(vt_src):
                vt_dst = os.path.join(gh_dir, "results", "virtual_trades.json")
                os.makedirs(os.path.dirname(vt_dst), exist_ok=True)
                shutil.copy2(vt_src, vt_dst)
                subprocess.run(["git", "add", "dashboard.html", "index.html", "dashboard.js", "results/virtual_trades.json"], cwd=gh_dir, capture_output=True, timeout=10)
            else:
                subprocess.run(["git", "add", "dashboard.html", "index.html", "dashboard.js"], cwd=gh_dir, capture_output=True, timeout=10)
            subprocess.run(["git", "commit", "-m", "dashboard auto-refresh"], cwd=gh_dir, capture_output=True, timeout=10)
            subprocess.run(["git", "push", "origin", "gh-pages"], cwd=gh_dir, capture_output=True, timeout=30)
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Deployed to gh-pages")
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] gh-pages deploy error: {e}")
        
        # Auto-bet: update virtual positions with current prices and auto-follow whale signals
        try:
            from virtual_trading import load_portfolio, save_portfolio
            portfolio = load_portfolio()
            updated = False
            for pos in portfolio.get("positions", []):
                # Update current price from whale data
                for addr, w in whale_data.items():
                    for p in w.get("positions", []):
                        title = p.get("title", "?")
                        outcome = p.get("outcome", "?")
                        if pos.get("market", "") in title and pos.get("outcome", "") == outcome:
                            cur = float(p.get("price", 0) or p.get("curPrice", 0) or 0)
                            if cur > 0:
                                pos["cur_price"] = cur
                                # Recalculate P&L
                                entry = pos.get("entry_price", 0)
                                shares = pos.get("shares", 0)
                                if entry > 0 and shares > 0:
                                    if pos.get("outcome", "").lower() in ("yes", "y"):
                                        pos["pnl"] = (cur - entry) * shares
                                        pos["pnl_pct"] = ((cur / entry) - 1) * 100 if entry > 0 else 0
                                    else:
                                        entry_no = 1 - entry
                                        cur_no = 1 - cur
                                        pos["pnl"] = (cur_no - entry_no) * shares
                                        pos["pnl_pct"] = ((cur_no / entry_no) - 1) * 100 if entry_no > 0 else 0
                                updated = True
            if updated:
                save_portfolio(portfolio)
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Virtual positions updated")
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Auto-bet error: {e}")
        
        return dashboard


async def main_loop(interval=120):
    """Main loop - update dashboard every 2 minutes."""
    while True:
        try:
            await collect_data_and_generate()
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        asyncio.run(collect_data_and_generate())
    else:
        asyncio.run(main_loop())