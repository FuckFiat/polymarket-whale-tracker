#!/usr/bin/env python3
"""NANO Polymarket API Server — bridges dashboard buttons with the Telegram bot's virtual trading.

Shares virtual_trades.json with the Telegram bot. Runs on port 8422.
"""

import json
import os
import time
from datetime import datetime, timezone
from aiohttp import web
import aiohttp

# Shared modules - only import what's needed for API
from virtual_trading import load_portfolio, save_portfolio, place_bet, close_position, get_stats, update_prices

# Don't import dashboard_gen - it has heavy f-strings that cause issues at import time
# We'll regenerate dashboard via subprocess after bets
def regenerate_dashboard():
    import subprocess
    try:
        subprocess.run(["python3", "-c", "import asyncio; from dashboard_gen import collect_data_and_generate; asyncio.run(collect_data_and_generate())"],
                       capture_output=True, timeout=60)
    except:
        pass

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DATA_API = "https://data-api.polymarket.com"
WHALES = {
    "0x2a2c53bd278c04da9962fcf96490e17f3dfb9bc1": {"name": "kcnyekchno"},
    "0xdc876e6873772d38716fda7f2452a78d426d7ab6": {"name": "432614799197"},
    "0x02227b8f5a9636e895607edd3185ed6ee5598ff7": {"name": "HorizonSplendidView"},
    "0x019782cab5d844f02bafb71f512758be78579f3c": {"name": "majorexploiter"},
    "0x492442eab586f242b53bda933fd5de859c8a3782": {"name": "April #1"},
    "0xefbc5fec8d7b0acdc8911bdd9a98d6964308f9a2": {"name": "reachingthesky"},
    "0xc2e7800b5af46e6093872b177b7a5e7f0563be51": {"name": "beachboy4"},
    "0xde17f7144fbd0eddb2679132c10ff5e74b120988": {"name": "Crypto Leader"},
    "0x2005d16a84ceefa912d4e380cd32e7ff827875ea": {"name": "RN1"},
    "0xbddf61af533ff524d27154e589d2d7a81510c684": {"name": "Countryside"},
}

# CORS headers for dashboard
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


async def cors_middleware(app, handler):
    async def middleware_handler(request):
        if request.method == "OPTIONS":
            return web.Response(headers=CORS_HEADERS)
        resp = await handler(request)
        for k, v in CORS_HEADERS.items():
            resp.headers[k] = v
        return resp
    return middleware_handler


# ── API ENDPOINTS ────────────────────────────────────────────────

async def api_portfolio(request):
    """GET /api/portfolio — current balance, positions, resolved, stats."""
    portfolio = load_portfolio()
    update_prices(portfolio)
    stats = get_stats(portfolio)
    return web.json_response({
        "balance": portfolio["balance"],
        "initial_deposit": portfolio.get("initial_deposit", 1000),
        "positions": portfolio["positions"],
        "resolved": portfolio.get("resolved", []),
        "win_count": portfolio.get("win_count", 0),
        "loss_count": portfolio.get("loss_count", 0),
        "total_won": portfolio.get("total_won", 0),
        "total_lost": portfolio.get("total_lost", 0),
        "total_bets": portfolio.get("total_bets", 0),
        "stats": stats,
    })


async def api_signals(request):
    """GET /api/signals — available whale signals to bet on."""
    signals = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        for addr, info in WHALES.items():
            try:
                url = f"{DATA_API}/positions?user={addr.lower()}"
                async with s.get(url) as r:
                    positions = await r.json()
                for p in positions[:10]:
                    cv = float(p.get("currentValue", 0) or 0)
                    cur = float(p.get("curPrice", 0) or 0)
                    avg = float(p.get("avgPrice", 0) or 0)
                    if cv > 500 and 0.05 < cur < 0.98:
                        signals.append({
                            "whale": info["name"],
                            "market": p.get("title", "?"),
                            "outcome": p.get("outcome", "?"),
                            "cur_price": cur,
                            "avg_price": avg,
                            "value": cv,
                            "pnl": float(p.get("cashPnl", 0) or 0),
                        })
            except:
                continue
    signals.sort(key=lambda x: x["pnl"], reverse=True)
    return web.json_response({"signals": signals[:12]})


async def api_place_bet(request):
    """POST /api/bet — place a virtual bet from dashboard.
    Body: {"whale": "...", "market": "...", "outcome": "Yes/No", "price": 0.60}
    """
    try:
        data = await request.json()
        whale = data.get("whale", "?")
        market = data.get("market", "?")
        outcome = data.get("outcome", "Yes")
        price = float(data.get("price", 0.5))
        bet_size = float(data.get("bet_size", 50))

        portfolio = load_portfolio()
        result = place_bet(portfolio, whale, market, outcome, price, bet_size, price)

        if "error" in result:
            return web.json_response({"error": result["error"]}, status=400)

        # Regenerate dashboard after bet
        try:
            from dashboard_gen import collect_data_and_generate
            import asyncio as aio
            aio.get_event_loop().create_task(collect_data_and_generate())
        except:
            pass

        return web.json_response({
            "success": True,
            "position": result,
            "balance": portfolio["balance"],
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def api_close_position(request):
    """POST /api/close — close a position from dashboard.
    Body: {"position_id": "bet_xxx", "result": "win"|"loss"}
    """
    try:
        data = await request.json()
        pos_id = data.get("position_id", "")
        result = data.get("result", "loss")

        portfolio = load_portfolio()
        closed = close_position(portfolio, pos_id, result)

        if not closed:
            return web.json_response({"error": "Position not found"}, status=404)

        # Regenerate dashboard
        try:
            from dashboard_gen import collect_data_and_generate
            import asyncio as aio
            aio.get_event_loop().create_task(collect_data_and_generate())
        except:
            pass

        return web.json_response({
            "success": True,
            "closed": closed,
            "balance": portfolio["balance"],
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def api_topup(request):
    """POST /api/topup — add $500 to balance."""
    portfolio = load_portfolio()
    portfolio["balance"] += 500
    save_portfolio(portfolio)
    return web.json_response({"balance": portfolio["balance"]})


async def api_whales(request):
    """GET /api/whales — list whale addresses and names."""
    return web.json_response({
        addr: info["name"] for addr, info in WHALES.items()
    })


# ── SERVER ───────────────────────────────────────────────────────

app = web.Application(middlewares=[cors_middleware])
app.router.add_get("/api/portfolio", api_portfolio)
app.router.add_get("/api/signals", api_signals)
app.router.add_post("/api/bet", api_place_bet)
app.router.add_post("/api/close", api_close_position)
app.router.add_post("/api/topup", api_topup)
app.router.add_get("/api/whales", api_whales)

if __name__ == "__main__":
    print("🎰 NANO Polymarket API Server starting on :8422")
    web.run_app(app, host="0.0.0.0", port=8422)