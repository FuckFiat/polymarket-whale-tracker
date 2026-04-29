"""
NANO Polymarket Whale Tracker — Configuration
"""

# Polymarket API Endpoints
CLOB_URL = "https://clob.polymarket.com"
DATA_URL = "https://data-api.polymarket.com"
GAMMA_URL = "https://gamma-api.polymarket.com"

# Whale Detection Parameters
WHALE_TOP_PERCENT = 1          # Top 1% by PnL = whale
MIN_TRADES_FOR_RANKING = 3     # Minimum trades to be ranked
MIN_VOLUME_USD = 50            # Minimum volume to be considered
WHALE_MONITOR_INTERVAL = 60    # Seconds between whale checks

# Market Filters
MARKETS_LIMIT = 200           # Max markets to fetch
TRADES_PER_MARKET = 500       # Max trades per market
WALLET_TRADES_LIMIT = 500     # Max trades per wallet

# Scoring Weights (must sum to 1.0)
SCORE_WEIGHTS = {
    "pnl": 0.35,
    "win_rate": 0.25,
    "roi": 0.25,
    "recency": 0.15,
}

# Output
DB_PATH = "whale_cache.db"
RESULTS_DIR = "/Users/zero_mini/.openclaw/workspace/scripts/polymarket_whale_tracker/results"

# Rate limiting
REQUEST_DELAY = 0.3  # Seconds between API requests
MAX_CONCURRENT = 5   # Max concurrent requests