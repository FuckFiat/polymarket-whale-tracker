#!/usr/bin/env python3
"""Quick whale discovery from Polymarket real-time data."""
import aiohttp
import asyncio
import json
from collections import defaultdict

async def find_whales():
    async with aiohttp.ClientSession() as session:
        # Get top markets by 24h volume
        url = 'https://gamma-api.polymarket.com/markets?limit=30&order=volume24hr&ascending=false&closed=false'
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            markets = await resp.json()
        
        print(f"Found {len(markets)} top markets")
        
        top_markets = []
        for m in markets[:15]:
            vol = float(m.get('volume24hr', 0) or 0)
            q = m.get('question', '')[:60]
            slug = m.get('slug', '')
            top_markets.append({'slug': slug, 'volume_24h': vol, 'question': q})
            print(f"  ${vol:,.0f} | {q}")
        
        # Fetch trades for each market
        wallets = defaultdict(lambda: {
            'volume': 0.0, 'trades': 0, 
            'markets': set(), 'pseudonyms': set(), 
            'sides': defaultdict(int),
            'total_buy': 0.0, 'total_sell': 0.0
        })
        
        for m in top_markets[:15]:
            slug = m['slug']
            try:
                url = f'https://data-api.polymarket.com/trades?limit=200&order=desc&slug={slug}'
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        trades = await resp.json()
                        for t in trades:
                            addr = t.get('proxyWallet', '')
                            size = float(t.get('size', 0) or 0)
                            price = float(t.get('price', 0) or 0)
                            side = t.get('side', '')
                            pseudo = t.get('pseudonym', '')
                            vol_usd = size * price
                            
                            wallets[addr]['volume'] += vol_usd
                            wallets[addr]['trades'] += 1
                            wallets[addr]['markets'].add(slug[:30])
                            if pseudo:
                                wallets[addr]['pseudonyms'].add(pseudo)
                            wallets[addr]['sides'][side] += 1
                            if side == 'BUY':
                                wallets[addr]['total_buy'] += vol_usd
                            else:
                                wallets[addr]['total_sell'] += vol_usd
            except:
                pass
        
        # Rank by volume
        ranked = sorted(wallets.items(), key=lambda x: x[1]['volume'], reverse=True)
        
        print(f"\n{'='*100}")
        print(f"  WHALE RANKING — TOP 20 (by 24h volume from top markets)")
        print(f"{'='*100}")
        
        for i, (addr, data) in enumerate(ranked[:20], 1):
            pseudo = ', '.join(data['pseudonyms']) if data['pseudonyms'] else 'anon'
            mkts = len(data['markets'])
            total_t = max(data['trades'], 1)
            buy_pct = (data['sides'].get('BUY', 0) / total_t) * 100
            
            if data['volume'] > 100000:
                emoji = '🐋'
            elif data['volume'] > 20000:
                emoji = '🐟'
            else:
                emoji = '🦐'
            
            vol_str = f"${data['volume']:>12,.0f}"
            print(f"  {emoji} #{i:2d} {addr[:10]}...{addr[-6:]} | {vol_str} | {data['trades']:3d} trades | {mkts} mkts | {pseudo[:20]} | Buy {buy_pct:.0f}%")
        
        # Save
        results = []
        for addr, data in ranked[:50]:
            total_t = max(data['trades'], 1)
            results.append({
                'address': addr,
                'volume_usd': round(data['volume'], 2),
                'trades': data['trades'],
                'markets_count': len(data['markets']),
                'pseudonym': ', '.join(data['pseudonyms']) if data['pseudonyms'] else 'anon',
                'buy_pct': round((data['sides'].get('BUY', 0) / total_t) * 100, 1),
                'total_buy': round(data['total_buy'], 2),
                'total_sell': round(data['total_sell'], 2),
            })
        
        with open('results/whale_ranking_realtime.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved {len(results)} wallets to results/whale_ranking_realtime.json")

asyncio.run(find_whales())