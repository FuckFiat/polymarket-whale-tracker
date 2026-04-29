#!/usr/bin/env python3
"""
🎰 NANO Virtual Trading System
Simulates following whale signals with a virtual deposit.
Tracks balance, positions, P&L, and resolved bets.
"""

import json, os, time
from datetime import datetime, timezone, timedelta

TRADES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "virtual_trades.json")

DEFAULT_BALANCE = 1000.0  # Starting $1000
DEFAULT_BET_SIZE = 50.0   # $50 per bet

def load_portfolio():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE) as f:
            return json.load(f)
    return {
        "balance": DEFAULT_BALANCE,
        "initial_deposit": DEFAULT_BALANCE,
        "positions": [],      # Open positions
        "resolved": [],       # Resolved bets
        "total_won": 0,
        "total_lost": 0,
        "total_bets": 0,
        "win_count": 0,
        "loss_count": 0,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

def save_portfolio(portfolio):
    portfolio["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    with open(TRADES_FILE, "w") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

def place_bet(portfolio, whale_name, market, outcome, price, bet_size=None, cur_price=None):
    """Place a virtual bet following a whale signal."""
    if bet_size is None:
        bet_size = DEFAULT_BET_SIZE
    
    if portfolio["balance"] < bet_size:
        return {"error": f"Insufficient balance: ${portfolio['balance']:.2f} < ${bet_size:.2f}"}
    
    shares = bet_size / price if price > 0 else 0
    
    position = {
        "id": f"bet_{len(portfolio['positions']) + len(portfolio['resolved']) + 1}",
        "whale": whale_name,
        "market": market,
        "outcome": outcome,
        "entry_price": price,
        "cur_price": cur_price or price,
        "bet_size": bet_size,
        "shares": shares,
        "entry_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "status": "open",
        "pnl": 0,
        "pnl_pct": 0,
    }
    
    portfolio["balance"] -= bet_size
    portfolio["positions"].append(position)
    portfolio["total_bets"] += 1
    save_portfolio(portfolio)
    return position

def update_positions(portfolio, whale_data):
    """Update open positions with current prices from whale data."""
    for pos in portfolio["positions"]:
        # Find matching position in whale data
        for wp in whale_data:
            title = wp.get("title", "").lower()
            outcome = wp.get("outcome", "").lower()
            if pos["market"].lower() in title and pos["outcome"].lower() == outcome:
                cur = float(wp.get("curPrice", 0) or 0)
                if cur > 0:
                    pos["cur_price"] = cur
                    # P&L = (cur - entry) * shares for YES, or (entry - cur) * shares for NO
                    if pos["outcome"].lower() in ("yes", "y"):
                        pos["pnl"] = (cur - pos["entry_price"]) * pos["shares"]
                        pos["pnl_pct"] = ((cur / pos["entry_price"]) - 1) * 100 if pos["entry_price"] > 0 else 0
                    else:
                        entry_no = 1 - pos["entry_price"]
                        cur_no = 1 - cur
                        pos["pnl"] = (cur_no - entry_no) * pos["shares"]
                        pos["pnl_pct"] = ((cur_no / entry_no) - 1) * 100 if entry_no > 0 else 0
                break
    
    save_portfolio(portfolio)

def close_position(portfolio, position_id, result="loss"):
    """Close a position manually."""
    for i, pos in enumerate(portfolio["positions"]):
        if pos["id"] == position_id:
            pos["status"] = "resolved"
            pos["result"] = result
            pos["close_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            
            # Calculate final P&L
            if result == "win":
                # YES wins: get back bet_size * (1/entry_price) * 1.0
                payout = pos["shares"] * (1.0 if pos["outcome"].lower() in ("yes", "y") else 0.0)
                pos["pnl"] = payout - pos["bet_size"]
            else:
                payout = pos["shares"] * (0.0 if pos["outcome"].lower() in ("yes", "y") else 1.0)
                pos["pnl"] = payout - pos["bet_size"]
            
            portfolio["balance"] += max(0, pos["bet_size"] + pos["pnl"])
            
            if pos["pnl"] >= 0:
                portfolio["win_count"] += 1
                portfolio["total_won"] += pos["pnl"]
            else:
                portfolio["loss_count"] += 1
                portfolio["total_lost"] += abs(pos["pnl"])
            
            portfolio["resolved"].append(pos)
            portfolio["positions"].pop(i)
            save_portfolio(portfolio)
            return pos
    
    return {"error": "Position not found"}

def get_stats(portfolio):
    """Get portfolio statistics."""
    open_pnl = sum(p.get("pnl", 0) for p in portfolio["positions"])
    total_value = portfolio["balance"] + sum(
        p.get("cur_price", 0) * p.get("shares", 0) for p in portfolio["positions"]
    )
    
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
        "total_pnl": portfolio["total_won"] - portfolio["total_lost"] + open_pnl,
        "total_value": total_value,
        "roi_pct": ((total_value - portfolio["initial_deposit"]) / portfolio["initial_deposit"]) * 100,
        "last_updated": portfolio["last_updated"],
    }

if __name__ == "__main__":
    # Demo: initialize portfolio
    p = load_portfolio()
    stats = get_stats(p)
    print(f"Balance: ${stats['balance']:.2f}")
    print(f"Open positions: {stats['open_positions']}")
    print(f"Total P&L: ${stats['total_pnl']:+.2f}")
    print(f"ROI: {stats['roi_pct']:+.1f}%")
