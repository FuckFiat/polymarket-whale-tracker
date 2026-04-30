#!/usr/bin/env python3
"""
🎰 NANO Virtual Trading System v2.0
Fixed P&L calculation, auto-betting from whale positions.
"""

import json, os, time, requests
from datetime import datetime, timezone, timedelta

TRADES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "virtual_trades.json")

DEFAULT_BALANCE = 1000.0
DEFAULT_BET_SIZE = 50.0

def load_portfolio():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE) as f:
            data = json.load(f)
        # Ensure all required fields exist
        defaults = {
            "balance": DEFAULT_BALANCE,
            "initial_deposit": DEFAULT_BALANCE,
            "positions": [],
            "resolved": [],
            "total_won": 0,
            "total_lost": 0,
            "total_bets": 0,
            "win_count": 0,
            "loss_count": 0,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "auto_betting": True,
            "max_bet_pct": 5,  # Max 5% of balance per bet
        }
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        return data
    return {
        "balance": DEFAULT_BALANCE,
        "initial_deposit": DEFAULT_BALANCE,
        "positions": [],
        "resolved": [],
        "total_won": 0,
        "total_lost": 0,
        "total_bets": 0,
        "win_count": 0,
        "loss_count": 0,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "auto_betting": True,
        "max_bet_pct": 5,
    }

def save_portfolio(portfolio):
    portfolio["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    with open(TRADES_FILE, "w") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

def place_bet(portfolio, whale_name, market, outcome, price, bet_size=None, cur_price=None):
    """Place a virtual bet. Returns position dict or error."""
    if bet_size is None:
        bet_size = min(DEFAULT_BET_SIZE, portfolio["balance"] * portfolio.get("max_bet_pct", 5) / 100)
    
    if portfolio["balance"] < bet_size:
        return {"error": f"Insufficient balance: ${portfolio['balance']:.2f} < ${bet_size:.2f}"}
    
    if price <= 0 or price > 1:
        return {"error": f"Invalid price: {price}"}
    
    # Deduct from balance
    shares = bet_size / price
    position = {
        "id": f"bet_{int(time.time())}_{len(portfolio['positions'])+len(portfolio['resolved'])+1}",
        "whale": whale_name,
        "market": market,
        "outcome": outcome,
        "entry_price": round(price, 6),
        "cur_price": round(cur_price or price, 6),
        "bet_size": round(bet_size, 2),
        "shares": round(shares, 4),
        "entry_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "status": "open",
        "pnl": 0,
        "pnl_pct": 0,
    }
    
    portfolio["balance"] = round(portfolio["balance"] - bet_size, 2)
    portfolio["positions"].append(position)
    portfolio["total_bets"] += 1
    save_portfolio(portfolio)
    return position

def close_position(portfolio, position_id, result="loss"):
    """Close a position. result='win' or 'loss'.
    
    P&L calculation:
    - YES @ 0.60, bet $50 → 83.33 shares
      - WIN: payout = 83.33 * $1.00 = $83.33, P&L = +$33.33
      - LOSS: payout = $0, P&L = -$50
    - NO @ 0.40, bet $50 → 125 shares  
      - WIN: payout = 125 * $1.00 = $125, P&L = +$75
      - LOSS: payout = $0, P&L = -$50
    """
    for i, pos in enumerate(portfolio["positions"]):
        if pos["id"] == position_id:
            pos["status"] = "resolved"
            pos["result"] = result
            pos["close_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            
            bet_size = pos["bet_size"]
            shares = pos["shares"]
            outcome = pos["outcome"].lower()
            
            if result == "win":
                # Winning bet: payout = shares * $1.00 per share
                payout = shares * 1.0
                pnl = payout - bet_size
            else:
                # Losing bet: total loss
                payout = 0
                pnl = -bet_size
            
            pos["pnl"] = round(pnl, 2)
            pos["pnl_pct"] = round((pnl / bet_size) * 100, 1) if bet_size > 0 else 0
            
            # Return payout to balance
            portfolio["balance"] = round(portfolio["balance"] + payout, 2)
            
            if pnl >= 0:
                portfolio["win_count"] += 1
                portfolio["total_won"] = round(portfolio["total_won"] + pnl, 2)
            else:
                portfolio["loss_count"] += 1
                portfolio["total_lost"] = round(portfolio["total_lost"] + abs(pnl), 2)
            
            portfolio["resolved"].append(pos)
            portfolio["positions"].pop(i)
            save_portfolio(portfolio)
            return pos
    
    return {"error": "Position not found"}

def update_prices(portfolio, whale_positions=None):
    """Update cur_price for open positions from API data."""
    updated = 0
    for pos in portfolio["positions"]:
        market_hint = pos["market"].lower()[:30]
        
        # Try to find matching market in whale positions data
        if whale_positions:
            for wp in whale_positions:
                title = wp.get("title", "").lower()
                if market_hint in title or title[:30] in market_hint:
                    price = float(wp.get("curPrice", 0) or wp.get("price", 0) or 0)
                    if price > 0:
                        pos["cur_price"] = round(price, 6)
                        # Recalculate P&L
                        if pos["outcome"].lower() in ("yes", "y"):
                            pos["pnl"] = round((price - pos["entry_price"]) * pos["shares"], 2)
                            pos["pnl_pct"] = round(((price / pos["entry_price"]) - 1) * 100, 1) if pos["entry_price"] > 0 else 0
                        else:
                            cur_no = 1 - price
                            entry_no = 1 - pos["entry_price"]
                            pos["pnl"] = round((cur_no - entry_no) * pos["shares"], 2)
                            pos["pnl_pct"] = round(((cur_no / entry_no) - 1) * 100, 1) if entry_no > 0 else 0
                        updated += 1
                        break
    
    if updated > 0:
        save_portfolio(portfolio)
    return updated

def get_stats(portfolio):
    """Get portfolio statistics."""
    open_pnl = sum(p.get("pnl", 0) for p in portfolio["positions"])
    open_value = sum(
        p.get("cur_price", p.get("entry_price", 0)) * p.get("shares", 0)
        for p in portfolio["positions"]
    )
    total_value = portfolio["balance"] + open_value
    
    resolved_pnl = sum(p.get("pnl", 0) for p in portfolio["resolved"])
    
    return {
        "balance": portfolio["balance"],
        "initial_deposit": portfolio["initial_deposit"],
        "open_positions": len(portfolio["positions"]),
        "resolved_bets": len(portfolio["resolved"]),
        "total_bets": portfolio["total_bets"],
        "wins": portfolio["win_count"],
        "losses": portfolio["loss_count"],
        "win_rate": (portfolio["win_count"] / max(1, portfolio["win_count"] + portfolio["loss_count"])) * 100,
        "total_won": portfolio["total_won"],
        "total_lost": portfolio["total_lost"],
        "open_pnl": open_pnl,
        "resolved_pnl": resolved_pnl,
        "total_pnl": open_pnl + resolved_pnl,
        "total_value": total_value,
        "roi_pct": ((total_value - portfolio["initial_deposit"]) / portfolio["initial_deposit"]) * 100 if portfolio["initial_deposit"] > 0 else 0,
        "last_updated": portfolio.get("last_updated", ""),
    }

def auto_bet_from_whale(portfolio, whale_name, whale_positions, max_bet=None):
    """Auto-bet on whale positions that are significant."""
    if not portfolio.get("auto_betting", True):
        return []
    
    if max_bet is None:
        max_bet = portfolio["balance"] * portfolio.get("max_bet_pct", 5) / 100
    
    new_bets = []
    existing_markets = {p["market"][:30].lower() for p in portfolio["positions"]}
    
    for pos in whale_positions:
        title = pos.get("title", "")
        cur_val = float(pos.get("currentValue", 0) or 0)
        
        # Skip if too small or already betting on this market
        if cur_val < 1000 or title[:30].lower() in existing_markets:
            continue
        
        # Skip if balance is too low
        if portfolio["balance"] < max_bet:
            break
        
        outcome = pos.get("outcome", "Yes")
        price = float(pos.get("avgPrice", pos.get("curPrice", 0.5)) or 0.5)
        if price <= 0 or price > 1:
            price = 0.5
        
        bet_result = place_bet(portfolio, whale_name, title, outcome, price, max_bet, price)
        if "error" not in bet_result:
            new_bets.append(bet_result)
    
    return new_bets

if __name__ == "__main__":
    p = load_portfolio()
    stats = get_stats(p)
    print(f"💰 Balance: ${stats['balance']:.2f}")
    print(f"📊 Open: {stats['open_positions']} | Resolved: {stats['resolved_bets']}")
    print(f"💵 P&L: ${stats['total_pnl']:+.2f} | ROI: {stats['roi_pct']:+.1f}%")
    print(f"✅ Wins: {stats['wins']} | ❌ Losses: {stats['losses']} | Win rate: {stats['win_rate']:.0f}%")