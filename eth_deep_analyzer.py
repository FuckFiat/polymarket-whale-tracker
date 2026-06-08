#!/usr/bin/env python3
"""
🚀 ETH Deep Market Analyzer
Полный анализ ETH для точного входа в рынок
"""

import aiohttp
import asyncio
from datetime import datetime, timezone

# Hyperliquid API endpoints
HL_API = "https://api.hyperliquid.xyz"
HL_INFO = "https://api.hyperliquid.xyz/info"
HL_EXCHANGE = "https://api.hyperliquid.xyz/exchange"

class ETHDeepAnalyzer:
    def __init__(self):
        self.data = {}
        
    async def fetch_all_data(self, session):
        """Fetch all ETH market data"""
        await asyncio.gather(
            self.fetch_price(session),
            self.fetch_orderbook(session),
            self.fetch_funding(session),
            self.fetch_open_interest(session),
            self.fetch_recent_trades(session),
            self.fetch_liquidations(session),
            self.fetch_whale_positions(session),
        )
        
    async def fetch_price(self, session):
        """Current ETH price"""
        try:
            async with session.post(HL_INFO, json={"type": "allMids"}) as r:
                data = await r.json()
                self.data['price'] = float(data.get('ETH', 0))
        except:
            self.data['price'] = 0
            
    async def fetch_orderbook(self, session):
        """Order book depth"""
        try:
            async with session.post(HL_INFO, json={"type": "l2Book", "coin": "ETH"}) as r:
                data = await r.json()
                levels = data.get('levels', [])
                if len(levels) >= 2:
                    bids = levels[0]  # bids
                    asks = levels[1]  # asks
                    
                    # Top 5 levels
                    bid_data = []
                    ask_data = []
                    
                    for i in range(min(5, len(bids))):
                        bid_data.append({
                            'px': float(bids[i].get('px', 0)),
                            'sz': float(bids[i].get('sz', 0)),
                            'total': float(bids[i].get('px', 0)) * float(bids[i].get('sz', 0))
                        })
                    
                    for i in range(min(5, len(asks))):
                        ask_data.append({
                            'px': float(asks[i].get('px', 0)),
                            'sz': float(asks[i].get('sz', 0)),
                            'total': float(asks[i].get('px', 0)) * float(asks[i].get('sz', 0))
                        })
                    
                    self.data['orderbook'] = {
                        'bids': bid_data,
                        'asks': ask_data,
                        'spread': ask_data[0]['px'] - bid_data[0]['px'] if ask_data and bid_data else 0,
                        'spread_pct': ((ask_data[0]['px'] - bid_data[0]['px']) / bid_data[0]['px'] * 100) if bid_data else 0
                    }
        except Exception as e:
            self.data['orderbook'] = {'bids': [], 'asks': [], 'spread': 0, 'spread_pct': 0}
            
    async def fetch_funding(self, session):
        """Funding rates"""
        try:
            async with session.post(HL_INFO, json={"type": "funding"}) as r:
                data = await r.json()
                for item in data:
                    if item.get('coin') == 'ETH':
                        self.data['funding'] = {
                            'rate': float(item.get('funding', 0)),
                            'mark_px': float(item.get('markPx', 0)),
                            'premium': float(item.get('premium', 0)),
                            'time': item.get('time', 0)
                        }
                        return
                self.data['funding'] = {'rate': 0, 'mark_px': 0, 'premium': 0, 'time': 0}
        except:
            self.data['funding'] = {'rate': 0, 'mark_px': 0, 'premium': 0, 'time': 0}
            
    async def fetch_open_interest(self, session):
        """Open Interest data"""
        try:
            async with session.post(HL_INFO, json={"type": "meta"}) as r:
                data = await r.json()
                universe = data.get('universe', [])
                for asset in universe:
                    if asset.get('name') == 'ETH':
                        self.data['oi'] = {
                            'total': float(asset.get('openInterest', 0)),
                            'mark_px': float(asset.get('markPx', 0)),
                            'funding': float(asset.get('funding', 0)),
                            'max_leverage': float(asset.get('maxLeverage', 0))
                        }
                        return
                self.data['oi'] = {'total': 0, 'mark_px': 0, 'funding': 0, 'max_leverage': 0}
        except:
            self.data['oi'] = {'total': 0, 'mark_px': 0, 'funding': 0, 'max_leverage': 0}
            
    async def fetch_recent_trades(self, session):
        """Recent trades for volume analysis"""
        try:
            async with session.post(HL_INFO, json={"type": "recentTrades", "coin": "ETH"}) as r:
                data = await r.json()
                trades = []
                buy_vol = 0
                sell_vol = 0
                
                for trade in data[:50]:  # Last 50 trades
                    side = trade.get('side', 'N/A')
                    size = float(trade.get('sz', 0))
                    px = float(trade.get('px', 0))
                    
                    if side == 'B':
                        buy_vol += size * px
                    else:
                        sell_vol += size * px
                        
                    trades.append({'side': side, 'size': size, 'px': px})
                
                total_vol = buy_vol + sell_vol
                buy_pct = (buy_vol / total_vol * 100) if total_vol > 0 else 50
                
                self.data['trades'] = {
                    'buy_volume': buy_vol,
                    'sell_volume': sell_vol,
                    'buy_pct': buy_pct,
                    'sell_pct': 100 - buy_pct,
                    'delta': buy_vol - sell_vol,
                    'count': len(data)
                }
        except:
            self.data['trades'] = {'buy_volume': 0, 'sell_volume': 0, 'buy_pct': 50, 'sell_pct': 50, 'delta': 0, 'count': 0}
            
    async def fetch_liquidations(self, session):
        """Recent liquidations"""
        try:
            # Get clearinghouse state for liquidations
            async with session.post(HL_INFO, json={"type": "clearinghouseState", "user": "0x0000000000000000000000000000000000000000"}) as r:
                data = await r.json()
                # This endpoint doesn't give liquidations directly
                # We'll estimate from positions
                self.data['liquidations'] = {'count': 0, 'total': 0, 'long_liq': 0, 'short_liq': 0}
        except:
            self.data['liquidations'] = {'count': 0, 'total': 0, 'long_liq': 0, 'short_liq': 0}
            
    async def fetch_whale_positions(self, session):
        """Whale positioning"""
        from hyperliquid_monitor import HYPERLIQUID_WHALES, get_user_state
        
        whale_data = {
            'longs': [],
            'shorts': [],
            'total_long': 0,
            'total_short': 0,
            'avg_long_entry': 0,
            'avg_short_entry': 0,
            'max_leverage_long': 0,
            'max_leverage_short': 0,
            'total_pnl': 0
        }
        
        total_long_entry = 0
        total_short_entry = 0
        long_count = 0
        short_count = 0
        
        for addr, info in HYPERLIQUID_WHALES.items():
            try:
                user_state = await get_user_state(session, addr)
                if not user_state:
                    continue
                    
                positions = user_state.get("assetPositions", [])
                for pos in positions:
                    p = pos.get("position", {})
                    if p.get("coin") == "ETH":
                        size = float(p.get("szi", "0"))
                        entry = float(p.get("entryPx", "0"))
                        pnl = float(p.get("unrealizedPnl", "0"))
                        lev = float(p.get("leverage", {}).get("value", "1")) if isinstance(p.get("leverage"), dict) else 1
                        liq = float(p.get("liquidationPx", 0)) if p.get("liquidationPx") else 0
                        
                        position_data = {
                            'name': info['name'],
                            'size': abs(size),
                            'entry': entry,
                            'pnl': pnl,
                            'leverage': lev,
                            'liq': liq,
                            'account_value': float(user_state.get("marginSummary", {}).get("accountValue", 0))
                        }
                        
                        if size > 0:
                            whale_data['longs'].append(position_data)
                            whale_data['total_long'] += abs(size)
                            total_long_entry += entry * abs(size)
                            long_count += 1
                            if lev > whale_data['max_leverage_long']:
                                whale_data['max_leverage_long'] = lev
                        else:
                            whale_data['shorts'].append(position_data)
                            whale_data['total_short'] += abs(size)
                            total_short_entry += entry * abs(size)
                            short_count += 1
                            if lev > whale_data['max_leverage_short']:
                                whale_data['max_leverage_short'] = lev
                        
                        whale_data['total_pnl'] += pnl
            except:
                continue
        
        if long_count > 0:
            whale_data['avg_long_entry'] = total_long_entry / whale_data['total_long']
        if short_count > 0:
            whale_data['avg_short_entry'] = total_short_entry / whale_data['total_short']
            
        self.data['whales'] = whale_data


def format_eth_deep_analysis(data):
    """Format comprehensive ETH analysis for Telegram"""
    
    price = data.get('price', 0)
    funding = data.get('funding', {})
    oi = data.get('oi', {})
    trades = data.get('trades', {})
    whales = data.get('whales', {})
    orderbook = data.get('orderbook', {})
    
    # Calculate signals
    signals = []
    warnings = []
    
    # Funding signal
    funding_rate = funding.get('rate', 0)
    if funding_rate > 0.0001:
        signals.append("🟢 Положительный funding — быки платят медведям")
    elif funding_rate < -0.0001:
        warnings.append("🔴 Отрицательный funding — медведи платят быкам")
    
    # OI signal
    oi_total = oi.get('total', 0)
    if oi_total > 500000:  # > 500K ETH
        signals.append(f"🟢 Высокий OI: {oi_total/1000:.1f}K ETH — сильный интерес")
    
    # Trade delta
    buy_pct = trades.get('buy_pct', 50)
    if buy_pct > 55:
        signals.append(f"🟢 Давление покупателей: {buy_pct:.1f}%")
    elif buy_pct < 45:
        warnings.append(f"🔴 Давление продавцов: {100-buy_pct:.1f}%")
    
    # Whale sentiment
    total_long = whales.get('total_long', 0)
    total_short = whales.get('total_short', 0)
    whale_total = total_long + total_short
    
    if whale_total > 0:
        long_pct = (total_long / whale_total) * 100
        if long_pct > 60:
            signals.append(f"🟢 Киты в LONG: {long_pct:.0f}%")
        elif long_pct < 40:
            warnings.append(f"🔴 Киты в SHORT: {100-long_pct:.0f}%")
    
    # Entry analysis
    avg_long = whales.get('avg_long_entry', 0)
    avg_short = whales.get('avg_short_entry', 0)
    
    long_discount = ((price - avg_long) / price * 100) if avg_long > 0 and price > 0 else 0
    short_premium = ((avg_short - price) / price * 100) if avg_short > 0 and price > 0 else 0
    
    # Recommendation
    score = len(signals) - len(warnings)
    if score >= 3:
        recommendation = "🟢 *СИЛЬНЫЙ ЛОНГ*"
        entry_zone = f"${price * 0.98:.0f} - ${price:.0f}"
        stop_loss = f"${price * 0.95:.0f}"
        take_profit = f"${price * 1.05:.0f}"
    elif score >= 1:
        recommendation = "🟡 *УМЕРЕННЫЙ ЛОНГ*"
        entry_zone = f"${price * 0.99:.0f} - ${price * 1.01:.0f}"
        stop_loss = f"${price * 0.94:.0f}"
        take_profit = f"${price * 1.04:.0f}"
    elif score <= -2:
        recommendation = "🔴 *ШОРТ / ВНЕ РЫНКА*"
        entry_zone = "Ожидать падения"
        stop_loss = "—"
        take_profit = "—"
    else:
        recommendation = "🟠 *НЕЙТРАЛЬНО / ЖДАТЬ*"
        entry_zone = f"${price * 0.97:.0f} - ${price * 1.03:.0f}"
        stop_loss = f"${price * 0.93:.0f}"
        take_profit = f"${price * 1.07:.0f}"
    
    # Format orderbook
    ob_text = ""
    if orderbook.get('bids') and orderbook.get('asks'):
        bids = orderbook['bids']
        asks = orderbook['asks']
        spread = orderbook.get('spread', 0)
        spread_pct = orderbook.get('spread_pct', 0)
        
        ob_text = f"""📊 *Order Book (Топ 5)*

🟢 *Bids (Покупатели)*
"""
        for i, bid in enumerate(bids[:5]):
            ob_text += f"  {i+1}. `${bid['px']:,.2f}` — `{bid['sz']:,.2f}` ETH (${bid['total']:,.0f})\n"
        
        ob_text += f"""
🔴 *Asks (Продавцы)*
"""
        for i, ask in enumerate(asks[:5]):
            ob_text += f"  {i+1}. `${ask['px']:,.2f}` — `{ask['sz']:,.2f}` ETH (${ask['total']:,.0f})\n"
        
        ob_text += f"""
📐 *Spread*: `${spread:.2f}` ({spread_pct:.3f}%)
"""
    
    # Format whale positions
    whale_text = ""
    longs = whales.get('longs', [])
    shorts = whales.get('shorts', [])
    
    if longs:
        whale_text += "\n🟢 *LONG Позиции Китов*\n"
        for w in sorted(longs, key=lambda x: x['size'], reverse=True)[:5]:
            pnl_icon = "🟢" if w['pnl'] > 0 else "🔴"
            whale_text += f"  • {w['name']}: `{w['size']:.2f}` ETH @ `${w['entry']:,.0f}` {pnl_icon} `${w['pnl']:,.0f}`\n"
    
    if shorts:
        whale_text += "\n🔴 *SHORT Позиции Китов*\n"
        for w in sorted(shorts, key=lambda x: x['size'], reverse=True)[:5]:
            pnl_icon = "🟢" if w['pnl'] > 0 else "🔴"
            whale_text += f"  • {w['name']}: `{w['size']:.2f}` ETH @ `${w['entry']:,.0f}` {pnl_icon} `${w['pnl']:,.0f}`\n"
    
    text = f"""🚀 *ETH ГЛУБОКИЙ АНАЛИЗ*
═══════════════════════════════════════

💰 *Цена*: `${price:,.2f}`
📊 *Mark Price*: `${funding.get('mark_px', 0):,.2f}`
💎 *Premium*: `{funding.get('premium', 0):,.4f}`

{ob_text}

💸 *Funding Rate*
├─ Текущий: `{funding_rate*100:.4f}%`
├─ Направление: {"🟢 Быки → Медведи" if funding_rate > 0 else "🔴 Медведи → Быки"}
└─ Статус: {"Перегрето" if abs(funding_rate) > 0.001 else "Норма"}

📈 *Open Interest*
├─ Всего: `{oi_total/1000:.1f}K` ETH
├─ В USD: `${oi_total * price / 1_000_000:.1f}M`
└─ Макс плечо: `{oi.get('max_leverage', 0):.0f}x`

🔄 *Объём (Последние трейды)*
├─ Покупки: `${trades.get('buy_volume', 0)/1_000:.0f}K` ({buy_pct:.1f}%)
├─ Продажи: `${trades.get('sell_volume', 0)/1_000:.0f}K` ({100-buy_pct:.1f}%)
├─ Дельта: `{"🟢" if trades.get('delta', 0) > 0 else "🔴"} ${trades.get('delta', 0)/1_000:.0f}K`
└─ Трейдов: `{trades.get('count', 0)}`

🐋 *Whale Sentiment*
├─ LONG: `{total_long:.2f}` ETH ({long_pct:.0f}%)
├─ SHORT: `{total_short:.2f}` ETH ({100-long_pct:.0f}%)
├─ Ср. вход LONG: `${avg_long:,.0f}`
├─ Ср. вход SHORT: `${avg_short:,.0f}`
├─ Дисконт LONG: `{long_discount:.1f}%`
└─ Премия SHORT: `{short_premium:.1f}%`
{whale_text}

🎯 *Сигналы*
"""
    
    if signals:
        text += "\n".join([f"✅ {s}" for s in signals]) + "\n"
    if warnings:
        text += "\n".join([f"⚠️ {w}" for w in warnings]) + "\n"
    
    text += f"""
💡 *РЕКОМЕНДАЦИЯ*
{recommendation}

📍 *Зона входа*: {entry_zone}
🛑 *Стоп-лосс*: {stop_loss}
🎯 *Тейк-профит*: {take_profit}

⚠️ *Важно*: Анализ на основе публичных данных. DYOR!

⏰ `{datetime.now(timezone.utc).strftime('%H:%M UTC %d.%m.%Y')}`
"""
    
    return text


async def get_eth_full_analysis():
    """Get full ETH analysis"""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        analyzer = ETHDeepAnalyzer()
        await analyzer.fetch_all_data(session)
        return format_eth_deep_analysis(analyzer.data)


# Export
__all__ = ['ETHDeepAnalyzer', 'format_eth_deep_analysis', 'get_eth_full_analysis']
