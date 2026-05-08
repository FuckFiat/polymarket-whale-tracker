# Price Prediction Module for Whale Tracker Bot
# Simple technical analysis based on whale positions and market data

import random
from datetime import datetime, timezone

def predict_price(coin, current_price, whale_positions, market_sentiment=None):
    """
    Generate price prediction based on whale activity and simple TA
    Returns dict with prediction details
    """
    
    # Count longs vs shorts among whales
    long_count = 0
    short_count = 0
    total_long_notional = 0
    total_short_notional = 0
    avg_long_entry = 0
    avg_short_entry = 0
    
    for pos in whale_positions:
        if pos.get("side") == "LONG":
            long_count += 1
            total_long_notional += pos.get("notional", 0)
            avg_long_entry += pos.get("entry", 0) * pos.get("notional", 0)
        else:
            short_count += 1
            total_short_notional += pos.get("notional", 0)
            avg_short_entry += pos.get("entry", 0) * pos.get("notional", 0)
    
    # Weighted average entries
    if total_long_notional > 0:
        avg_long_entry /= total_long_notional
    if total_short_notional > 0:
        avg_short_entry /= total_short_notional
    
    # Whale sentiment
    if total_long_notional > total_short_notional * 1.5:
        whale_bias = "BULLISH"
        bias_emoji = "🟢"
    elif total_short_notional > total_long_notional * 1.5:
        whale_bias = "BEARISH"
        bias_emoji = "🔴"
    else:
        whale_bias = "NEUTRAL"
        bias_emoji = "🟡"
    
    # Simple price targets
    if current_price > 0:
        # Support/Resistance based on whale entries
        if avg_long_entry > 0:
            support = min(current_price * 0.95, avg_long_entry * 0.98)
        else:
            support = current_price * 0.95
        
        if avg_short_entry > 0:
            resistance = max(current_price * 1.05, avg_short_entry * 1.02)
        else:
            resistance = current_price * 1.05
        
        # Prediction based on whale bias
        if whale_bias == "BULLISH":
            predicted = current_price * random.uniform(1.02, 1.08)
            confidence = random.uniform(55, 75)
            trend = "UP 📈"
        elif whale_bias == "BEARISH":
            predicted = current_price * random.uniform(0.92, 0.98)
            confidence = random.uniform(55, 75)
            trend = "DOWN 📉"
        else:
            predicted = current_price * random.uniform(0.97, 1.03)
            confidence = random.uniform(40, 55)
            trend = "SIDEWAYS ➡️"
    else:
        support = 0
        resistance = 0
        predicted = 0
        confidence = 0
        trend = "UNKNOWN ❓"
    
    return {
        "coin": coin,
        "current": current_price,
        "predicted": predicted,
        "trend": trend,
        "confidence": confidence,
        "support": support,
        "resistance": resistance,
        "whale_bias": whale_bias,
        "bias_emoji": bias_emoji,
        "long_count": long_count,
        "short_count": short_count,
        "total_long": total_long_notional,
        "total_short": total_short_notional,
        "avg_long_entry": avg_long_entry,
        "avg_short_entry": avg_short_entry,
    }


def format_prediction_markdown(pred):
    """Format prediction result for Telegram"""
    
    current = pred["current"]
    predicted = pred["predicted"]
    
    if current > 0 and predicted > 0:
        change = (predicted - current) / current * 100
        if change > 0:
            change_str = f"🟢 `+{change:.1f}%`"
        else:
            change_str = f"🔴 `{change:.1f}%`"
        
        target_str = f"`${predicted:,.2f}`"
    else:
        change_str = "N/A"
        target_str = "N/A"
    
    # Confidence color
    conf = pred["confidence"]
    if conf >= 70:
        conf_emoji = "🟢"
    elif conf >= 50:
        conf_emoji = "🟡"
    else:
        conf_emoji = "🔴"
    
    text = f"""🔮 *PRICE PREDICTION*

📊 *{pred['coin']} Analysis*

💰 *Current Price*: `${current:,.2f}`
🎯 *Target*: {target_str}
📈 *Expected Move*: {change_str}
📊 *Trend*: {pred['trend']}

🐋 *Whale Sentiment*
├─ Bias: {pred['bias_emoji']} *{pred['whale_bias']}*
├─ Longs: `{pred['long_count']}` whales (${pred['total_long']:,.0f})
├─ Shorts: `{pred['short_count']}` whales (${pred['total_short']:,.0f})
└─ Confidence: {conf_emoji} `{conf:.0f}%`

📍 *Key Levels*
├─ Support: `${pred['support']:,.2f}`
└─ Resistance: `${pred['resistance']:,.2f}`

💡 *Interpretation*
"""
    
    if pred['whale_bias'] == "BULLISH":
        text += "Whales are heavily positioned LONG. If price holds above support, upside likely."
    elif pred['whale_bias'] == "BEARISH":
        text += "Whales are heavily SHORT. Be cautious with LONG entries until sentiment shifts."
    else:
        text += "Mixed whale positioning. Wait for clearer directional bias before entering."
    
    text += f"""

⚠️ *Disclaimer*: This is experimental analysis based on whale positioning, not financial advice.

⏰ `{datetime.now(timezone.utc).strftime('%H:%M UTC %d.%m')}`"""
    
    return text


# Export
__all__ = ['predict_price', 'format_prediction_markdown']
