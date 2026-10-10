"""Google Trends 同比：近 4 周均值 vs 去年同期 4 周均值。

用法：python3 google_trends_yoy.py GEO 词1 词2 ... (最多 5 个词)
例：python3 google_trends_yoy.py NL thuisbatterij powerstation zonnepanelen
输出每个词的 近 4 周热度 / 去年同期 / 同比百分比，以及最近 12 周的周度曲线（用来识别单周尖峰）。
每组最多 5 个词；同组里有高流量大词会把小词压成 0–1，要分组查。
和 shopping_rising.py 共用 Google 的额度：飙升词跑完至少隔 15 分钟再查，每组之间隔 1 分钟。
"""
import sys, warnings, urllib.parse, datetime as dt
warnings.filterwarnings("ignore")
from pytrends.request import TrendReq

geo, kws = sys.argv[1], sys.argv[2:7]
end = dt.date.today() - dt.timedelta(days=1)
start = end - dt.timedelta(days=760)
p = TrendReq(hl="en-US", tz=0, timeout=(10, 30), retries=0)  # retries>0 和 urllib3 v2 冲突
try:
    p.build_payload(kws, geo=geo, timeframe=f"{start} {end}")
    d = p.interest_over_time().drop(columns=["isPartial"], errors="ignore")
except Exception as e:
    sys.exit(f"{geo} | {' '.join(kws)} | 失败 {type(e).__name__}"
             + ("：被 Google 限流，本期同比停掉，没查的词写进「下期跟踪」，不要连着重试" if "TooManyRequests" in type(e).__name__ else ""))
cur_from = end - dt.timedelta(days=28)
prev_to, prev_from = end - dt.timedelta(days=365), cur_from - dt.timedelta(days=365)
cur = d.loc[str(cur_from):str(end)].mean()
prev = d.loc[str(prev_from):str(prev_to)].mean()
for k in kws:
    ratio = cur[k] / prev[k] if prev[k] else float("nan")
    url = "https://trends.google.com/trends/explore?" + urllib.parse.urlencode(
        {"date": f"{start} {end}", "geo": geo, "q": k})
    chg = "去年无数据" if ratio != ratio else (f"{(ratio-1)*100:+.0f}%")
    print(f"{geo} | {k} | 近4周热度 {cur[k]:.0f} vs 去年同期 {prev[k]:.0f} | 比去年同期 {chg} | 近12周 {list(d[k].tail(12).astype(int))} | {url}")
