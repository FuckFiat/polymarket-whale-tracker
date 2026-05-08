# Improved Hyperliquid Position Formatter with ETH Long Analysis

from datetime import datetime, timezone

def format_position_markdown(coin, size, entry_px, unrealized_pnl, cur_px, leverage, liquidation_px=None, margin_used=0):
    """Format a position with full analysis for Telegram Markdown"""
    side = "LONG" if float(size) > 0 else "SHORT"
    abs_size = abs(float(size))
    notional = abs_size * float(cur_px)
    pnl = float(unrealized_pnl)
    entry = float(entry_px)
    
    # Liquidation
    if liquidation_px and liquidation_px not in ("None", "N/A", None, ""):
        try:
            liq_price = float(liquidation_px)
        except (ValueError, TypeError):
            liq_price = None
    else:
        liq_price = None
    
    if liq_price is None and float(leverage) > 0:
        if float(size) > 0:
            liq_price = entry * (1 - 1/(float(leverage) * 2))
        else:
            liq_price = entry * (1 + 1/(float(leverage) * 2))
    
    # Distance to liquidation
    liq_distance = None
    if liq_price and float(cur_px) > 0:
        if float(size) > 0:
            liq_distance = (float(cur_px) - liq_price) / float(cur_px) * 100
        else:
            liq_distance = (liq_price - float(cur_px)) / float(cur_px) * 100
    
    return {
        "coin": coin,
        "side": side,
        "size": abs_size,
        "entry": entry,
        "current": float(cur_px),
        "pnl": pnl,
        "notional": notional,
        "leverage": float(leverage),
        "liq_price": liq_price,
        "liq_distance": liq_distance,
        "margin_used": float(margin_used) if margin_used else 0,
    }


def format_alert_enhanced(alert):
    """Enhanced alert formatter with Markdown and ETH Long Analysis"""
    
    if alert["type"] == "new_position":
        icon = "🆕"
        title = "*NEW POSITION*"
    elif alert["type"] == "size_change":
        icon = "🔄"
        title = "*SIZE CHANGE*"
    elif alert["type"] == "liquidation_risk":
        icon = "⚠️"
        title = "*⚠️ LIQUIDATION RISK*"
    elif alert["type"] == "new_whale":
        icon = "🐋"
        title = "*NEW WHALE DETECTED*"
    else:
        icon = "📊"
        title = "*POSITION UPDATE*"
    
    # PnL formatting
    pnl = alert["pnl"]
    if pnl > 0:
        pnl_str = f"`+${pnl:,.0f}`"
        pnl_icon = "🟢"
    elif pnl < 0:
        pnl_str = f"`-${abs(pnl):,.0f}`"
        pnl_icon = "🔴"
    else:
        pnl_str = "`$0`"
        pnl_icon = "⚪"
    
    # Side
    side = alert["side"]
    side_icon = "🟢 *LONG*" if side == "LONG" else "🔴 *SHORT*"
    
    # Notional
    notional = alert["notional"]
    if notional >= 1_000_000:
        notional_str = f"`${notional/1_000_000:.1f}M`"
    elif notional >= 1_000:
        notional_str = f"`${notional/1_000:.1f}K`"
    else:
        notional_str = f"`${notional:,.0f}`"
    
    # Account value
    av = alert["account_value"]
    if av >= 1_000_000:
        av_str = f"`${av/1_000_000:.1f}M`"
    else:
        av_str = f"`${av:,.0f}`"
    
    # Entry/Current
    entry = alert["entry"]
    current = alert["current"]
    if entry >= 1000:
        entry_str = f"`${entry:,.0f}`"
        cur_str = f"`${current:,.0f}`"
    elif entry >= 1:
        entry_str = f"`${entry:,.2f}`"
        cur_str = f"`${current:,.2f}`"
    else:
        entry_str = f"`${entry:,.4f}`"
        cur_str = f"`${current:,.4f}`"
    
    # ROI
    if entry > 0:
        if side == "LONG":
            roi = (current - entry) / entry * 100
        else:
            roi = (entry - current) / entry * 100
    else:
        roi = 0
    
    if roi > 0:
        roi_str = f"🟢 `+{roi:.1f}%`"
    elif roi < 0:
        roi_str = f"🔴 `{roi:.1f}%`"
    else:
        roi_str = "⚪ `0%`"
    
    # Liquidation
    liq = alert.get("liq_price")
    liq_dist = alert.get("liq_distance")
    margin = alert.get("margin_used", 0)
    
    if liq and liq > 0:
        if liq >= 1000:
            liq_str = f"`${liq:,.0f}`"
        else:
            liq_str = f"`${liq:,.2f}`"
        
        if liq_dist is not None:
            if liq_dist < 5:
                liq_risk = f"🔴 *CRITICAL* `{liq_dist:.1f}%`"
            elif liq_dist < 15:
                liq_risk = f"🟠 *HIGH* `{liq_dist:.1f}%`"
            elif liq_dist < 30:
                liq_risk = f"🟡 *MEDIUM* `{liq_dist:.1f}%`"
            else:
                liq_risk = f"🟢 *SAFE* `{liq_dist:.1f}%`"
        else:
            liq_risk = "—"
    else:
        liq_str = "N/A"
        liq_risk = "—"
    
    # Long Analysis
    long_signal = ""
    if side == "LONG":
        entry_discount = (current - entry) / current * 100 if current > 0 else 0
        if entry_discount > 5:
            long_signal = f"\n📉 *Discount*: `{entry_discount:.1f}%` below entry — *potential accumulation zone*"
        elif entry_discount < -10:
            long_signal = f"\n📈 *Premium*: `{abs(entry_discount):.1f}%` above entry — *consider DCA*"
        
        if liq_dist and liq_dist < 20:
            long_signal += f"\n⚠️ *Caution*: Close to liq — wait for bounce"
        elif liq_dist and liq_dist > 40 and roi < -5:
            long_signal += f"\n✅ *Signal*: Deep discount with safe margin — *LONG opportunity*"
    
    text = f"""{icon} {title}

👤 *Whale*: `{alert['whale']}`
💰 *Account*: {av_str}

📊 *Position*
├─ Side: {side_icon}
├─ Coin: `#{alert['coin']}`
├─ Size: `{alert["size"]:,.4f}`
├─ Notional: {notional_str}
└─ Leverage: `{alert['leverage']:.0f}x`

📈 *Price Action*
├─ Entry: {entry_str}
├─ Current: {cur_str}
└─ ROI: {roi_str}

💵 *PnL*: {pnl_icon} {pnl_str}

💀 *Liquidation*
├─ Price: {liq_str}
├─ Distance: {liq_risk}
└─ Margin Used: `${margin:,.0f}`
{long_signal}

⏰ `{datetime.now(timezone.utc).strftime('%H:%M UTC %d.%m')}`"""
    
    return text


def format_hl_summary_markdown(positions_data):
    """Format a summary of all HL whale positions with Long/Short analysis"""
    
    if not positions_data:
        return "📊 *No active positions found*"
    
    # Aggregate by coin
    coin_stats = {}
    total_long = 0
    total_short = 0
    total_pnl = 0
    
    for pos in positions_data:
        coin = pos["coin"]
        side = pos["side"]
        notional = pos.get("notional", 0)
        pnl = pos.get("pnl", 0)
        
        if coin not in coin_stats:
            coin_stats[coin] = {"long": 0, "short": 0, "count": 0, "pnl": 0}
        
        if side == "LONG":
            coin_stats[coin]["long"] += notional
            total_long += notional
        else:
            coin_stats[coin]["short"] += notional
            total_short += notional
        
        coin_stats[coin]["count"] += 1
        coin_stats[coin]["pnl"] += pnl
        total_pnl += pnl
    
    # Build summary
    if total_pnl > 0:
        total_pnl_str = f"🟢 `+${total_pnl:,.0f}`"
    else:
        total_pnl_str = f"🔴 `${total_pnl:,.0f}`"
    
    text = f"""📊 *HYPERLIQUID WHALE ANALYSIS*

💰 *Portfolio Overview*
├─ Total Long: `${total_long:,.0f}`
├─ Total Short: `${total_short:,.0f}`
├─ Net Exposure: `${total_long - total_short:,.0f}`
└─ Total PnL: {total_pnl_str}

🎯 *Top Positions by Coin*"""
    
    # Sort by total notional
    sorted_coins = sorted(coin_stats.items(), key=lambda x: x[1]["long"] + x[1]["short"], reverse=True)
    
    for coin, stats in sorted_coins[:10]:
        total = stats["long"] + stats["short"]
        long_pct = (stats["long"] / total * 100) if total > 0 else 0
        
        if stats["pnl"] > 0:
            pnl_icon = "🟢"
        elif stats["pnl"] < 0:
            pnl_icon = "🔴"
        else:
            pnl_icon = "⚪"
        
        # Signal
        if long_pct > 70:
            signal = "🟢 *BULLISH*"
        elif long_pct < 30:
            signal = "🔴 *BEARISH*"
        else:
            signal = "🟡 *NEUTRAL*"
        
        text += f"""
┌─ `#{coin}`
├─ Positions: `{stats['count']}`
├─ Long: `{long_pct:.0f}%` · Short: `{100-long_pct:.0f}%`
├─ Total: `${total:,.0f}`
├─ PnL: {pnl_icon} `${stats['pnl']:,.0f}`
└─ Signal: {signal}"""
    
    # Long recommendations
    long_opportunities = []
    for pos in positions_data:
        if pos["side"] == "LONG" and pos.get("liq_distance", 0) > 30:
            if pos.get("pnl", 0) < -1000:  # Deep discount
                long_opportunities.append(pos)
    
    if long_opportunities:
        text += "\n\n🚀 *LONG OPPORTUNITIES*"
        for pos in long_opportunities[:5]:
            discount = (pos["current"] - pos["entry"]) / pos["current"] * 100 if pos["current"] > 0 else 0
            text += f"""
┌─ `#{pos['coin']}`
├─ Entry: `${pos['entry']:,.2f}`
├─ Current: `${pos['current']:,.2f}`
├─ Discount: `{discount:.1f}%`
└─ Safe Margin: `{pos.get('liq_distance', 0):.1f}%`"""
    
    text += f"\n\n⏰ `{datetime.now(timezone.utc).strftime('%H:%M UTC %d.%m')}`"
    
    return text


def format_eth_position_analysis(position):
    """Detailed ETH position analysis for long decision"""
    entry = position.get("entry", 0)
    current = position.get("current", 0)
    side = position.get("side", "?")
    leverage = position.get("leverage", 1)
    liq_dist = position.get("liq_distance", 0)
    pnl = position.get("pnl", 0)
    
    if entry <= 0 or current <= 0:
        return "❌ *Invalid position data*"
    
    # Calculate metrics
    if side == "LONG":
        roi = (current - entry) / entry * 100
        breakeven = entry
        support = entry * 0.95
        resistance = entry * 1.05
    else:
        roi = (entry - current) / entry * 100
        breakeven = entry
        support = entry * 1.05
        resistance = entry * 0.95
    
    # Long signal analysis
    signal = ""
    score = 0
    
    if side == "LONG":
        if current < entry * 0.98:
            signal += "\n✅ *Price below entry* — accumulation zone"
            score += 2
        if liq_dist > 40:
            signal += "\n✅ *Safe margin* — low liquidation risk"
            score += 2
        if leverage <= 5:
            signal += "\n✅ *Conservative leverage* — `{leverage:.0f}x`"
            score += 1
        elif leverage > 10:
            signal += "\n⚠️ *High leverage* — `{leverage:.0f}x`, use caution"
            score -= 1
        if pnl < -5000:
            signal += "\n📉 *Deep underwater* — whale is down, potential reversal"
            score += 1
    
    # Overall recommendation
    if score >= 4:
        rec = "🟢 *STRONG LONG*"
    elif score >= 2:
        rec = "🟡 *MODERATE LONG*"
    elif score > 0:
        rec = "🟠 *WEAK LONG*"
    else:
        rec = "🔴 *WAIT*"
    
    text = f"""📊 *ETH POSITION ANALYSIS*

📈 *Price Levels*
├─ Entry: `${entry:,.2f}`
├─ Current: `${current:,.2f}`
├─ Breakeven: `${breakeven:,.2f}`
├─ Support: `${support:,.2f}`
└─ Resistance: `${resistance:,.2f}`

📊 *Metrics*
├─ Side: `{'🟢 LONG' if side == 'LONG' else '🔴 SHORT'}`
├─ Leverage: `{leverage:.0f}x`
├─ ROI: `{roi:.1f}%`
├─ PnL: `${pnl:,.0f}`
└─ Liq Distance: `{liq_dist:.1f}%`

🎯 *Analysis*{signal}

💡 *Recommendation*: {rec}

⏰ `{datetime.now(timezone.utc).strftime('%H:%M UTC')}`"""
    
    return text


# Export functions
__all__ = [
    'format_position_markdown',
    'format_alert_enhanced', 
    'format_hl_summary_markdown',
    'format_eth_position_analysis'
]
