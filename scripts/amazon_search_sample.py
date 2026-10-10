"""亚马逊搜索页抽样（验证层）：一个词在某国亚马逊搜索第一页长什么样。

用法：python3 amazon_search_sample.py 国家 "关键词"
例：python3 amazon_search_sample.py US "cat litter box"
    python3 amazon_search_sample.py DE "katzenklo"
国家：US CA DE 先用手机版（有"顾客怎么说"标签），没商品自动换电脑版；IT ES NL BE 用电脑版（没有标签）。
UK、FR、AU 的搜索页会被拦，直接跳过（2026-09 实测）。畅销榜用 amazon_bestsellers.py，不用这个脚本。
输出：条数、价格区间和中位数、"过去一月购买"标注、评分数，以及"顾客怎么说"里负面/褒贬不一的方面汇总。
同一个词一天内别反复跑，被限流（503）就停，下周再查。
"""
import sys, re, html, statistics, subprocess, tempfile, os, time, urllib.parse

SITES = {  # 国家: (域名, 模式, Accept-Language, 币种)
    "US": ("www.amazon.com", "m", "en-US,en;q=0.9", "USD"),
    "CA": ("www.amazon.ca", "m", "en-CA,en;q=0.9", "CAD"),
    "DE": ("www.amazon.de", "m", "de-DE,de;q=0.9,en;q=0.8", "EUR"),
    "IT": ("www.amazon.it", "d", "en-GB,en;q=0.9", "EUR"),
    "ES": ("www.amazon.es", "d", "en-GB,en;q=0.9", "EUR"),
    "NL": ("www.amazon.nl", "d", "en-GB,en;q=0.9", "EUR"),
    "BE": ("www.amazon.com.be", "d", "en-GB,en;q=0.9", "EUR"),
}
BLOCKED = {"UK", "GB", "FR", "AU"}  # AU 2026-09-28 实测手机版、电脑版都只回空壳页
M_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
D_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
D_HEADERS = [
    'sec-ch-ua: "Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile: ?0", 'sec-ch-ua-platform: "macOS"',
    "Sec-Fetch-Dest: document", "Sec-Fetch-Mode: navigate", "Sec-Fetch-Site: none", "Sec-Fetch-User: ?1",
    "Upgrade-Insecure-Requests: 1",
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
]


def curl(url, ua, lang, jar, extra=()):
    cmd = ["curl", "-s", "-L", "--compressed", "-A", ua, "-H", f"Accept-Language: {lang}",
           "-b", jar, "-c", jar, "-w", "\n%{http_code}", url]
    for h in extra:
        cmd[1:1] = ["-H", h]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", timeout=60).stdout
    body, _, code = out.rpartition("\n")
    return code, body


def num(s):
    """$1,234.56 / 1.234,56 € / 16,99 € → float：最后一个带 1-2 位小数的分隔符是小数点"""
    m = re.fullmatch(r"([\d.,]*?)(?:[.,](\d{1,2}))?", s)
    if not m or not m.group(1) and not m.group(2):
        return None
    whole = re.sub(r"[.,]", "", m.group(1)) or "0"
    return float(f"{whole}.{m.group(2) or 0}")


def parse(page):
    items = []
    for b in page.split('data-component-type="s-search-result"')[1:]:
        b = b[:40000]
        title = re.search(r'<h2 aria-label="([^"]+)"', b) or re.search(r"<h2[^>]*>\s*<span[^>]*>([^<]+)", b)
        price = re.search(r'class="a-offscreen">([^<]+)<', b)
        rating = re.search(r'aria-label="([\d.,]+) (?:out of|von|su|de|van|sur) 5', b)
        count = re.search(r'aria-label="([\d.,]+) (?:ratings|rating|Bewertungen|Sternebewertungen|valutazioni|valoraciones|beoordelingen)"', b)
        bought = re.search(r">([^<]{1,20}\+[^<]{0,40}(?:past month|im letzten Monat|mese|mes|maand)[^<]*)<", b)
        aspects = {}
        pay = re.search(r'data-payload="([^"]+)"', b)
        if pay:
            p = html.unescape(html.unescape(pay.group(1)))
            for tone, words in re.findall(r'\["(positive|mixed|negative)","[^"]*",\[([^\]]*)\]\]', p):
                aspects[tone] = re.findall(r'"([^"]+)"', words)
        pv = None
        if price:
            digits = re.sub(r"[^\d.,]", "", price.group(1))
            pv = num(digits) if digits else None
        items.append({
            "title": html.unescape(title.group(1)).strip() if title else "?",
            "price": pv, "price_raw": price.group(1).strip() if price else "",
            "rating": rating.group(1) if rating else "",
            "count": count.group(1) if count else "",
            "bought": html.unescape(bought.group(1)).strip() if bought else "",
            "sponsored": "Sponsored" in b or "Gesponsert" in b or "Sponsorizzato" in b or "Patrocinado" in b,
            "aspects": aspects,
        })
    return items


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cc, kw = sys.argv[1].upper(), " ".join(sys.argv[2:])
    if cc in BLOCKED:
        sys.exit(f"{cc} | {kw} | 跳过：该站搜索页也会被拦。英国可以看 Argos，法国可以看 E.Leclerc、Auchan 的站内搜索")
    if cc not in SITES:
        sys.exit(f"{cc} 未实测，支持：{' '.join(SITES)}")
    host, mode, lang, cur = SITES[cc]
    url = f"https://{host}/s?k={urllib.parse.quote_plus(kw)}"
    fd, jar = tempfile.mkstemp(); os.close(fd)
    with open(jar, "w") as f:  # 不锁币种的话，亚马逊会按访问 IP 换算成美元
        f.write(f"#HttpOnly_.{host.removeprefix('www.')}\tTRUE\t/\tFALSE\t0\ti18n-prefs\t{cur}\n")
    try:
        if mode == "m":
            code, page = curl(url, M_UA, lang, jar)
            if code == "503" or 's-search-result' not in page:  # 手机版被限流就换电脑版
                mode = "d"
        if mode == "d":
            curl(f"https://{host}/", D_UA, lang, jar, D_HEADERS)  # 先拿 cookie
            time.sleep(2)
            code, page = curl(url, D_UA, lang, jar, D_HEADERS + ["Sec-Fetch-Site: same-origin"])
    finally:
        os.remove(jar)
    items = parse(page)
    if not items:
        sys.exit(f"{cc} | {kw} | 没抓到（HTTP {code}，{'验证页' if 'captcha' in page.lower() else '页面无商品'}）。别重试，写进附录的缺口")

    prices = [i["price"] for i in items if i["price"]]
    organic = [i for i in items if not i["sponsored"]]
    head = f"{cc} | {kw} | {'手机版' if mode == 'm' else '电脑版'} | 第一页 {len(items)} 条（广告 {len(items) - len(organic)}）"
    if prices:
        head += f" | 价格 {min(prices):g}–{max(prices):g} {cur}，中位数 {statistics.median(prices):g}"
    print(head + f" | {url}")
    for i in items:
        tag = "[广告] " if i["sponsored"] else ""
        extra = " ｜".join(x for x in [i["price_raw"], i["rating"] and f"{i['rating']}★ ({i['count']})", i["bought"]] if x)
        print(f"  - {tag}{i['title'][:90]} ｜{extra}")
    agg = {}
    for i in items:
        for tone in ("negative", "mixed"):
            for w in i["aspects"].get(tone, []):
                agg.setdefault(w, {"negative": 0, "mixed": 0})[tone] += 1
    if agg:
        print("  顾客怎么说（负面/褒贬不一，按出现商品数排）：")
        for w, c in sorted(agg.items(), key=lambda x: -(x[1]["negative"] * 2 + x[1]["mixed"])):
            print(f"    {w}：负面 {c['negative']} 款，褒贬不一 {c['mixed']} 款")
    elif mode == "m":
        print("  顾客怎么说：本页没有负面/褒贬不一标签")


if __name__ == "__main__":
    main()
