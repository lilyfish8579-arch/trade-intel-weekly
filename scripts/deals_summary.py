"""汇总折扣社区热榜：最近 N 天收到的帖子，每个国家按热度取前几条，带原帖链接。

用法：python3 deals_summary.py <周刊文件夹> [天数=7] [每国条数=15]
热度（°）只有 Pepper 系站点有（英、德、奥、法、西、荷）；Slickdeals、RedFlagDeals 没有热度，按收集顺序列。
"""
import csv, os, sys, datetime as dt
from _common import project_dir

p = project_dir(sys.argv[1] if len(sys.argv) > 1 else None)
days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
top = int(sys.argv[3]) if len(sys.argv) > 3 else 15
f = os.path.join(p, "数据", "deals.csv")
if not os.path.exists(f):
    sys.exit("还没有折扣数据：先跑 deals_collect.py")

since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
with open(f, encoding="utf-8") as fh:
    rows = [r for r in csv.DictReader(fh) if r["collected"] >= since]
dates = sorted({r["collected"] for r in rows})
print(f"最近 {days} 天共 {len(rows)} 条，收集了 {len(dates)} 天：{', '.join(dates) or '无'}")
if len(dates) <= 1:
    print("只收到 1 天：代表那一刻的热榜，不是一周汇总，周刊里要写明。")

by = {}
for r in rows:
    by.setdefault(r["country"], []).append(r)
for country, rs in by.items():
    if any(r["temperature"] for r in rs):
        rs.sort(key=lambda r: -int(r["temperature"] or -99999))
    print(f"\n## {country} · {rs[0]['site']}（{len(rs)} 条）")
    for r in rs[:top]:
        heat = f"{r['temperature']}° | " if r["temperature"] else ""
        extra = " | ".join(x for x in [r["category"], r["merchant"]] if x)
        print(f"- {heat}{r['title'][:100]}" + (f" | {extra}" if extra else "") + f" | {r['link']}")
