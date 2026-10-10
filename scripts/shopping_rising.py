"""Google 购物搜索（Google Shopping）按品类的"飙升词"：不用预设关键词，直接看各国消费者这周突然在搜什么。

用法：python3 shopping_rising.py <周刊文件夹> [GEO ...]
      国家和品类读 config.json 的 shopping_rising；命令行给了 GEO 就只跑这几个国家（补跑用）。
口径：过去 7 天 vs 前一段时间的增幅（百分比，Breakout = 增长超 5000%）。是短期异动，不是同比。
品类筛选是松的：别的品类的热词也会混进来，按词本身判断属于什么品类。
每次请求间隔 12 秒，11 国 × 5 品类约 11 分钟。被限流（429）先停 60 秒再试一次；
连续 3 组失败就整个停掉，没跑的过至少 1 小时再补跑。这个脚本和 google_trends_yoy.py 共用 Google 的额度。
"""
import sys, time, warnings, urllib.parse
warnings.filterwarnings("ignore")
from pytrends.request import TrendReq
from _common import project_dir, load_config

cfg = load_config(project_dir(sys.argv[1] if len(sys.argv) > 1 else None))["shopping_rising"]
CATS = {int(k): v for k, v in cfg["categories"].items()}
GEOS = sys.argv[2:] or cfg["geos"]
p = TrendReq(hl="en-US", tz=0, timeout=(10, 30), retries=0)  # retries>0 和 urllib3 v2 冲突


def one(geo, cat, name):
    for attempt in (1, 2):
        try:
            p.build_payload([""], cat=cat, geo=geo, timeframe="now 7-d", gprop="froogle")
            rising = list(p.related_queries().values())[0]["rising"]
            words = [] if rising is None else [
                f"{r['query']}(+{r['value']}%)" if r["value"] < 5000 else f"{r['query']}(Breakout)"
                for r in rising.head(12).to_dict("records")]
            url = "https://trends.google.com/trends/explore?" + urllib.parse.urlencode(
                {"date": "now 7-d", "geo": geo, "cat": cat, "gprop": "froogle"})
            print(f"{geo} | {name} | " + "; ".join(words or ["无数据"]) + f" | {url}")
            return True
        except Exception as e:
            if attempt == 1 and "TooManyRequests" in type(e).__name__:
                time.sleep(60)
                continue
            print(f"{geo} | {name} | 失败 {type(e).__name__}")
            return False


ok, failed, streak = 0, [], 0
for geo in GEOS:
    for cat, name in CATS.items():
        if one(geo, cat, name):
            ok, streak = ok + 1, 0
        else:
            failed.append(f"{geo} {name}")
            streak += 1
        sys.stdout.flush()
        if streak >= 3:
            break
        time.sleep(12)
    if streak >= 3:
        print("连续 3 组失败，判断为被 Google 限流，停掉。")
        break

total = len(GEOS) * len(CATS)
print(f"\n成功 {ok}/{total} 组。失败：{'、'.join(failed) or '无'}。"
      + ("没跑到的国家过至少 1 小时再补跑：shopping_rising.py <周刊文件夹> 国家代码…" if ok + len(failed) < total or failed else ""))
