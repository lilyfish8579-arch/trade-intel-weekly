"""Polymarket 贸易相关盘口：列出活跃事件和各选项概率。

用法：python3 polymarket_trade.py ["关键词" ...]   默认查 tariff / trade deal / China tariff
"""
import sys, json, urllib.request, urllib.parse

queries = sys.argv[1:] or ["tariff", "trade deal", "tariff rate on China"]
seen = set()
for q in queries:
    url = "https://gamma-api.polymarket.com/public-search?" + urllib.parse.urlencode(
        {"q": q, "limit_per_type": 6, "events_status": "active"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=20))
    for e in data.get("events", []):
        if e["slug"] in seen:
            continue
        seen.add(e["slug"])
        print(f"* {e['title']} | 截止 {str(e.get('endDate'))[:10]} | 成交额 ${int(float(e.get('volume') or 0)):,} | https://polymarket.com/event/{e['slug']}")
        for m in e.get("markets") or []:
            if m.get("closed"):
                continue
            try:
                prob = float(json.loads(m.get("outcomePrices") or "[]")[0])
            except (ValueError, IndexError):
                continue
            print(f"    - {(m.get('groupItemTitle') or m.get('question'))[:70]}: {prob:.1%}")
