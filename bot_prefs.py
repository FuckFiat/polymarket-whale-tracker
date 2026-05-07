#!/usr/bin/env python3
"""
🐋 NANO Bot Preferences Manager
User preferences for alerts, tracked coins, thresholds.
"""
import json, os

PREFS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "bot_prefs.json")

DEFAULT_PREFS = {
    "alerts_enabled": True,
    "whale_alert_min_usd": 10000,
    "funding_alert_threshold": 0.05,
    "liq_alert_distance_pct": 15,
    "volume_spike_multiplier": 3,
    "tracked_coins": ["BTC", "ETH", "SOL", "HYPE", "XRP", "DOGE", "LINK", "AVAX", "ARB", "SUI"],
    "auto_betting": True,
    "bet_strategy": "follow_whales",
    "max_bet_usd": 50,
    "followed_wallets": [],
    "signal_coins": ["BTC", "ETH", "SOL"],
}

def load_prefs():
    """Load user preferences from file."""
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE) as f:
                data = json.load(f)
            # Merge with defaults for missing keys
            merged = {**DEFAULT_PREFS, **data}
            return merged
        except Exception:
            return DEFAULT_PREFS.copy()
    return DEFAULT_PREFS.copy()

def save_prefs(prefs):
    """Save user preferences to file."""
    os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)

def update_pref(key, value):
    """Update a single preference."""
    prefs = load_prefs()
    prefs[key] = value
    save_prefs(prefs)
    return prefs