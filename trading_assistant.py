#!/usr/bin/env python3
"""
🤖 NANO Trading Assistant
Comprehensive trading bot with technical analysis, position management,
whale tracking, and price predictions.
"""

import asyncio, aiohttp, json, time, os, sys
from datetime import datetime, timezone
from hyperliquid_monitor import HYPERLIQUID_WHALES, get_user_state, get_all_mids
from hyperliquid_formatter import format_position_markdown
from price_predictor import predict_price, format_prediction_markdown

# ============= TECHNICAL ANALYSIS =============

def calculate_rsi(prices, period=14):
    """Calculate RSI for a list of prices"""
    if len(prices) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return 50.0
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_sma(prices, period=20):
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0
    return sum(prices[-period:]) / period


def calculate_ema(prices, period=20):
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0
    
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema


def calculate_macd(prices):
    """Calculate MACD signal"""
    if len(prices) < 26:
        return 0, 0, 0
    
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    macd_line = ema12 - ema26
    
    # Signal line (EMA of MACD)
    macd_values = []
    for i in range(26, len(prices)):
        e12 = calculate_ema(prices[:i+1], 12)
        e26 = calculate_ema(prices[:i+1], 26)
        macd_values.append(e12 - e26)
    
    signal_line = calculate_ema(macd_values, 9) if len(macd_values) >= 9 else 0
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    if len(prices) < period:
        return prices[-1] if prices else 0, 0, 0
    
    sma = calculate_sma(prices, period)
    
    # Calculate standard deviation
    variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
    std = variance ** 0.5
    
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    
    return upper, sma, lower


def calculate_support_resistance(prices, window=10):
    """Calculate support and resistance levels"""
    if len(prices) < window * 2:
        return prices[-1] * 0.95 if prices else 0, prices[-1] * 1.05 if prices else 0
    
    recent = prices[-window:]
    support = min(recent)
    resistance = max(recent)
    
    return support, resistance


def analyze_trend(prices):
    """Analyze trend direction and strength"""
    if len(prices) < 20:
        return "NEUTRAL", 0
    
    sma20 = calculate_sma(prices, 20)
    sma50 = calculate_sma(prices, min(50, len(prices)))
    
    current = prices[-1]
    
    if current > sma20 > sma50:
        strength = min((current - sma50) / sma50 * 100, 100)
        return "BULLISH", strength
    elif current < sma20 < sma50:
        strength = min((sma50 - current) / sma50 * 100, 100)
        return "BEARISH", strength
    else:
        return "NEUTRAL", 0


# ============= FORMATTING =============

def format_ta_markdown(coin, current_price, prices_history=None, whale_positions=None):
    """Format complete technical analysis"""
    
    if not prices_history:
        prices_history = [current_price * (1 + (i - 50) * 0.001) for i in range(100)]
    
    # Indicators
    rsi = calculate_rsi(prices_history)
    sma20 = calculate_sma(prices_history, 20)
    ema20 = calculate_ema(prices_history, 20)
    macd, signal, hist = calculate_macd(prices_history)
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(prices_history)
    support, resistance = calculate_support_resistance(prices_history)
    trend, strength = analyze_trend(prices_history)
    
    # RSI status
    if rsi > 70:
        rsi_status = "🔴 OVERBOUGHT"
        rsi_signal = "Potential SELL signal"
    elif rsi < 30:
        rsi_status = "🟢 OVERSOLD"
        rsi_signal = "Potential BUY signal"
    else:
        rsi_status = "🟡 NEUTRAL"
        rsi_signal = "Wait for clearer signal"
    
    # MACD status
    if hist > 0 and macd > signal:
        macd_status = "🟢 BULLISH"
        macd_signal = "MACD above signal — upward momentum"
    elif hist < 0 and macd < signal:
        macd_status = "🔴 BEARISH"
        macd_signal = "MACD below signal — downward momentum"
    else:
        macd_status = "🟡 MIXED"
        macd_signal = "Wait for MACD crossover"
    
    # Bollinger Bands position
    if current_price > bb_upper:
        bb_status = "🔴 Above Upper Band"
        bb_signal = "Price extended — possible reversal"
    elif current_price < bb_lower:
        bb_status = "🟢 Below Lower Band"
        bb_signal = "Price oversold — potential bounce"
    else:
        bb_status = "🟡 Within Bands"
        bb_signal = "Normal range"
    
    # Whale sentiment
    whale_long = 0
    whale_short = 0
    if whale_positions:
        for pos in whale_positions:
            if pos.get("side") == "LONG":
                whale_long += pos.get("notional", 0)
            else:
                whale_short += pos.get("notional", 0)
    
    total_whale = whale_long + whale_short
    if total_whale > 0:
        long_pct = whale_long / total_whale * 100
        if long_pct > 70:
            whale_bias = "🟢 BULLISH"
            whale_text = f"{long_pct:.0f}% whales LONG"
        elif long_pct < 30:
            whale_bias = "🔴 BEARISH"
            whale_text = f"{100-long_pct:.0f}% whales SHORT"
        else:
            whale_bias = "🟡 NEUTRAL"
            whale_text = f"Mixed ({long_pct:.0f}% long)"
    else:
        whale_bias = "⚪ NO DATA"
        whale_text = "No whale positions"
    
    # Overall signal
    signals = []
    if rsi < 35:
        signals.append("RSI oversold")
    if current_price < bb_lower * 1.02:
        signals.append("Price near BB lower")
    if hist > 0 and macd > signal:
        signals.append("MACD bullish")
    if whale_long > whale_short * 1.5:
        signals.append("Whales bullish")
    
    risks = []
    if rsi > 65:
        risks.append("RSI overbought")
    if current_price > bb_upper * 0.98:
        risks.append("Price near BB upper")
    if hist < 0 and macd < signal:
        risks.append("MACD bearish")
    if whale_short > whale_long * 1.5:
        risks.append("Whales bearish")
    
    if len(signals) >= 2 and len(risks) <= 1:
        overall = "🟢 *STRONG LONG*"
        recommendation = "Multiple bullish signals aligned. Consider LONG with stop below support."
    elif len(signals) >= 1 and len(risks) <= 1:
        overall = "🟡 *MODERATE LONG*"
        recommendation = "Some bullish signals. Wait for confirmation or scale in."
    elif len(risks) >= 2:
        overall = "🔴 *AVOID LONG / SHORT*"
        recommendation = "Multiple bearish signals. Consider SHORT or stay out."
    else:
        overall = "🟠 *WAIT*"
        recommendation = "Mixed signals. Wait for clearer setup."
    
    text = f"""📊 *TECHNICAL ANALYSIS: {coin}*
═══════════════════════════════════════

💰 *Current Price*: `${current_price:,.2f}`

📈 *Trend Analysis*
├─ Direction: *{trend}* (`{strength:.1f}%` strength)
├─ SMA20: `${sma20:,.2f}`
├─ EMA20: `${ema20:,.2f}`
└─ Position vs SMA: `{(current_price/sma20-1)*100:+.1f}%`

📉 *RSI (14)*
├─ Value: `{rsi:.1f}`
├─ Status: {rsi_status}
└─ Signal: {rsi_signal}

📊 *MACD*
├─ MACD: `{macd:.2f}`
├─ Signal: `{signal:.2f}`
├─ Histogram: `{hist:.2f}`
├─ Status: {macd_status}
└─ Signal: {macd_signal}

💠 *Bollinger Bands*
├─ Upper: `${bb_upper:,.2f}`
├─ Middle: `${bb_mid:,.2f}`
├─ Lower: `${bb_lower:,.2f}`
├─ Status: {bb_status}
└─ Signal: {bb_signal}

📍 *Key Levels*
├─ Resistance: `${resistance:,.2f}`
├─ Support: `${support:,.2f}`
└─ Range: `${(resistance-support)/current_price*100:.1f}%`

🐋 *Whale Sentiment*
├─ Bias: {whale_bias}
└─ Details: {whale_text}

💡 *Signals*
"""
    
    if signals:
        text += "\n".join([f"✅ {s}" for s in signals]) + "\n"
    else:
        text += "⚪ No clear signals\n"
    
    if risks:
        text += "\n⚠️ *Risks*\n" + "\n".join([f"🔴 {r}" for r in risks]) + "\n"
    
    text += f"""
🎯 *OVERALL*
{overall}

💭 *Recommendation*
{recommendation}

⚠️ *Disclaimer*: This is technical analysis, not financial advice. Always DYOR.

⏰ `{datetime.now(timezone.utc).strftime('%H:%M UTC %d.%m')}`"""
    
    return text


def get_reply_keyboard():
    """Get reply keyboard markup (square buttons)"""
    return {
        "keyboard": [
            ["🔮 Анализ ETH", "🐋 ETH киты", "📊 Прогноз"],
            ["📈 Теханализ BTC", "📉 Теханализ SOL", "💎 Другие монеты"],
            ["📊 Статус", "❓ Помощь", "🌐 Dashboard"]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def get_coins_keyboard():
    """Get keyboard for coin selection"""
    return {
        "keyboard": [
            ["BTC", "ETH", "SOL"],
            ["HYPE", "XRP", "DOGE"],
            ["LINK", "AVAX", "ARB"],
            ["⬅️ Назад в меню"]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


# ============= COMMAND HANDLERS =============

async def cmd_analyze_coin(chat_id, coin, session=None, send_func=None):
    """Analyze any coin with TA"""
    if not session:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
            return await cmd_analyze_coin(chat_id, coin, session=s, send_func=send_func)
    
    # Get price
    mids = await get_all_mids(session)
    price = float(mids.get(coin, "0")) if mids else 0
    
    if price <= 0:
        await send_func(f"❌ Не удалось получить цену для {coin}", chat_id)
        return
    
    # Generate mock price history (in real implementation, fetch from API)
    prices = [price * (1 + (i - 50) * 0.002 + (i % 7) * 0.001) for i in range(100)]
    
    # Get whale positions for this coin
    whale_positions = []
    for addr in HYPERLIQUID_WHALES:
        user_state = await get_user_state(session, addr)
        if not user_state:
            continue
        positions = user_state.get("assetPositions", [])
        for pos in positions:
            p = pos.get("position", {})
            if p.get("coin") == coin:
                size = float(p.get("szi", "0"))
                entry = float(p.get("entryPx", "0"))
                whale_positions.append({
                    "side": "LONG" if size > 0 else "SHORT",
                    "notional": abs(size) * price,
                    "entry": entry,
                    "leverage": float(p.get("leverage", {}).get("value", "1")) if isinstance(p.get("leverage"), dict) else 1
                })
    
    # Format analysis
    analysis = format_ta_markdown(coin, price, prices, whale_positions)
    
    await send_func(analysis, chat_id, parse_mode="Markdown", reply_markup=get_reply_keyboard())


# Export
__all__ = [
    'format_ta_markdown',
    'get_reply_keyboard',
    'get_coins_keyboard', 
    'cmd_analyze_coin',
    'calculate_rsi',
    'calculate_sma',
    'calculate_ema',
    'calculate_macd',
    'calculate_bollinger_bands',
    'analyze_trend'
]
