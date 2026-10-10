"""折扣社区热榜收集：把各国"热门折扣"追加到 <周刊文件夹>/数据/deals.csv（按链接去重）。

热度（°）= 社区用户投票，代表消费者真实兴趣。RSS 每次只给最新约 30 条，所以最好每天收一次，周刊再汇总一周；
没装每天定时的话，出刊时收一次，只代表那一刻的热榜。
用法：python3 deals_collect.py <周刊文件夹>      站点读 config.json 的 deals_sites
"""
import csv, os, re, sys, html, datetime as dt, urllib.request
import xml.etree.ElementTree as ET
from _common import project_dir, load_config

FEEDS = {  # 国家: (站点, RSS)
    "GB": ("hotukdeals", "https://www.hotukdeals.com/rss/hot"),
    "DE": ("mydealz", "https://www.mydealz.de/rss/hot"),
    "AT": ("preisjaeger", "https://www.preisjaeger.at/rss/hot"),
    "FR": ("dealabs", "https://www.dealabs.com/rss/hot"),
    "ES": ("chollometro", "https://www.chollometro.com/rss/hot"),
    "NL": ("pepper.nl", "https://nl.pepper.com/rss/hot"),
    "US": ("slickdeals", "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1"),
    "CA": ("redflagdeals", "https://forums.redflagdeals.com/feed/forum/9"),
}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
ATOM = "{http://www.w3.org/2005/Atom}"
# RedFlagDeals 的热帖源里混着抽奖帖（标题以 [Once] [Daily] 开头，或带 Contest、Giveaway、Win a）
CONTEST = re.compile(r"^\[(once|daily|weekly)\]|\b(contest|giveaway|competition|sweepstakes?)\b|\bwin an?\b", re.I)
FIELDS = ["collected", "country", "site", "temperature", "title", "category", "merchant", "published", "link"]


def items(url):
    root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
    for it in root.findall(".//item") + root.findall(f".//{ATOM}entry"):
        title = (it.findtext("title") or it.findtext(f"{ATOM}title") or "").strip()
        link = it.findtext("link") or ""
        if not link:
            el = it.find(f"{ATOM}link")
            link = el.attrib.get("href", "") if el is not None else ""
        merchant = it.find("merchant")
        temp = re.match(r"(-?\d+)°\s*-\s*", title)  # Pepper 系标题以 "123° - " 开头
        yield {
            "temperature": temp.group(1) if temp else "",
            "title": html.unescape(title[temp.end():] if temp else title),
            "category": it.findtext("category") or "",
            "merchant": merchant.attrib.get("name", merchant.text or "") if merchant is not None else "",
            "published": it.findtext("pubDate") or it.findtext(f"{ATOM}updated") or "",
            "link": link.strip(),
        }


def main():
    p = project_dir(sys.argv[1] if len(sys.argv) > 1 else None)
    sites = load_config(p).get("deals_sites", list(FEEDS))
    out = os.path.join(p, "数据", "deals.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    seen = set()
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            seen = {r["link"] for r in csv.DictReader(f)}
    today = dt.date.today().isoformat()
    new = 0
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if not seen:
            w.writeheader()
        for country in sites:
            site, url = FEEDS[country]
            try:
                for row in items(url):
                    if CONTEST.search(row["title"]):
                        continue
                    if row["link"] and row["link"] not in seen:
                        seen.add(row["link"])
                        w.writerow({"collected": today, "country": country, "site": site, **row})
                        new += 1
            except Exception as e:  # 单个站失败不影响其他站
                print(f"{country} {site} 失败: {e}")
    print(f"{today} 新增 {new} 条")


if __name__ == "__main__":
    main()
