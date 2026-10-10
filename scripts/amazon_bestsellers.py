"""亚马逊畅销榜（Best Sellers）每周快照：抓 config.json 里配置的 类目 × 国家 榜单，存前 50 名，和上一次比。

用法：python3 amazon_bestsellers.py <周刊文件夹>
      python3 amazon_bestsellers.py --list 国家 [类目地址]  列出这个榜下面的子类目和地址（不给类目地址就列一级类目）
      python3 amazon_bestsellers.py --test 国家 类目地址    试抓一个榜，确认类目地址能用，不写数据
      例：--list FR kitchen → 找到「Petit électroménager」的地址 → --test FR 那个地址
      类目地址 = 榜单网址 /gp/bestsellers/ 后面那一段，子类目带编号，如 kitchen/289913
输出：数据/amazon_bestsellers.csv（每次追加，同一天重跑覆盖当天）
      数据/amazon_bestsellers_本周变化.md（新上榜、名次大涨、跌出前 20，周刊直接读这个）
不开浏览器：页面直接请求能拿到前 30 名的标题、价格、评分；31–50 名只有名次和商品链接（要滚动才加载）。
页与页之间停 5 秒；被拦（验证码或空列表）就记下来跳过，不重试。
飙升榜（Movers & Shakers）2026-10 实测连真实浏览器都是空的，所以用"畅销榜周对比"代替。
"""
import csv, datetime as dt, html, json, os, re, subprocess, sys, time
from _common import project_dir, load_config

SITES = {  # 国家: (域名, Accept-Language, 币种)。US GB DE FR CA JP AU 2026-10 实测能抓
    "US": ("www.amazon.com", "en-US,en;q=0.9", "USD"),
    "CA": ("www.amazon.ca", "en-CA,en;q=0.9", "CAD"),
    "GB": ("www.amazon.co.uk", "en-GB,en;q=0.9", "GBP"),
    "DE": ("www.amazon.de", "de-DE,de;q=0.9,en;q=0.8", "EUR"),
    "FR": ("www.amazon.fr", "fr-FR,fr;q=0.9,en;q=0.8", "EUR"),
    "IT": ("www.amazon.it", "it-IT,it;q=0.9,en;q=0.8", "EUR"),
    "ES": ("www.amazon.es", "es-ES,es;q=0.9,en;q=0.8", "EUR"),
    "NL": ("www.amazon.nl", "nl-NL,nl;q=0.9,en;q=0.8", "EUR"),
    "JP": ("www.amazon.co.jp", "ja-JP,ja;q=0.9", "JPY"),
    "AU": ("www.amazon.com.au", "en-AU,en;q=0.9", "AUD"),
}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
FIELDS = ["collected", "country", "category", "rank", "asin", "title", "price", "rating", "reviews", "link"]
RISE = 10  # 名次上升多少算"大涨"
GAP = 5


def fetch(country, slug):
    host, lang, cur = SITES[country]
    out = subprocess.run(  # 锁本国币种，不然亚马逊会按访问 IP 换算成美元
        ["curl", "-s", "-L", "--compressed", "-A", UA, "-H", f"Accept-Language: {lang}",
         "-b", f"i18n-prefs={cur}", "-w", "\n%{http_code}", f"https://{host}/gp/bestsellers/" + (f"{slug}/" if slug else "")],
        capture_output=True, text=True, errors="ignore", timeout=60).stdout
    page, _, code = out.rpartition("\n")
    return code, page


def first(pat, s, flags=0):
    m = re.search(pat, s, flags)
    return html.unescape(m.group(1)).strip() if m else ""


def parse(page):
    items = []
    for b in page.split('id="gridItemRoot"')[1:]:
        b = b[:20000]
        items.append({
            "rank": re.sub(r"\D", "", first(r'zg-bdg-text">([^<]+)', b)),
            "asin": first(r'data-asin="([A-Z0-9]{10})"', b),
            "title": first(r'line-clamp[^"]*">([^<]+)', b) or first(r'<img alt="([^"]*)"', b),
            "price": first(r'sc-price[^"]*">([^<]+)', b),
            "rating": first(r'a-icon-alt">([\d.,]+)', b).replace(",", "."),
            "reviews": re.sub(r"\D", "", first(r'a-icon-row.*?a-size-small">([\d.,\s\xa0]+)<', b, re.S)),
        })
    # 没加载出来的 31–50 名：页面里自带完整的 ASIN 和名次，只缺标题价格
    have = {i["asin"] for i in items}
    raw = re.search(r'data-client-recs-list="([^"]+)"', page)
    try:
        for r in json.loads(html.unescape(raw.group(1))) if raw else []:
            rank = (r.get("metadataMap") or {}).get("render.zg.rank", "")
            if r.get("id") and r["id"] not in have:
                items.append({"rank": rank, "asin": r["id"], "title": "", "price": "", "rating": "", "reviews": ""})
    except ValueError:
        pass
    seen = set()
    return [i for i in items if i["asin"] and i["rank"] and not (i["asin"] in seen or seen.add(i["asin"]))]


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def line(r):
    return f"[{r['title'][:70] or '标题没加载出来，点链接看'}]({r['link']}) · {r['price']} · {r['reviews']} 评价"


def report(path, cats, rows, today, errors):
    lines = [f"# 亚马逊畅销榜本周变化（{today} 采集）", "",
             f"> 由 amazon_bestsellers.py 自动生成，原始数据在 数据/amazon_bestsellers.csv。对比的是同一榜单上一次采集；"
             f"名次上升 ≥{RISE} 算大涨。只看前 50 名，31–50 名可能只有链接。", ""]
    for cat, slugs in cats.items():
        for c in slugs:
            cur = [r for r in rows if r["collected"] == today and r["country"] == c and r["category"] == cat]
            lines.append(f"## {c} · {cat}")
            if not cur:
                lines += [f"本次没采到：{errors.get((c, cat), '未知原因')}", ""]
                continue
            prev_dates = sorted({r["collected"] for r in rows
                                 if r["country"] == c and r["category"] == cat and r["collected"] < today})
            if not prev_dates:
                lines += [f"第一次采集，共 {len(cur)} 条，下次开始有对比。前 10 名：", ""]
                lines += [f"- #{r['rank']} " + line(r) for r in cur[:10]] + [""]
                continue
            prev = {r["asin"]: int(r["rank"]) for r in rows
                    if r["collected"] == prev_dates[-1] and r["country"] == c and r["category"] == cat}
            curset = {r["asin"] for r in cur}
            new = [r for r in cur if r["asin"] not in prev]
            up = [r for r in cur if r["asin"] in prev and prev[r["asin"]] - int(r["rank"]) >= RISE]
            gone = [a for a, k in sorted(prev.items(), key=lambda x: x[1]) if k <= 20 and a not in curset]
            lines += [f"对比 {prev_dates[-1]}：新上榜 {len(new)} 个，大涨 {len(up)} 个，跌出前 20 的 {len(gone)} 个。", ""]
            if new:
                lines += ["**新上榜**"] + [f"- #{r['rank']} " + line(r) for r in new]
            if up:
                lines += ["**名次大涨**"] + [f"- #{prev[r['asin']]} → #{r['rank']} " + line(r) for r in up]
            if gone:
                lines += ["**跌出前 20**"] + [f"- 上次 #{prev[a]} https://{SITES[c][0]}/dp/{a}" for a in gone]
            lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def test(country, slug):
    if country not in SITES:
        sys.exit(f"脚本里没有 {country} 站，支持：{' '.join(SITES)}")
    code, page = fetch(country, slug)
    items = parse(page)
    name = first(r"<title>([^<]+)", page)
    if not items:
        sys.exit(f"❌ {country} {slug} 抓不到（HTTP {code}，页面标题：{name}）。标题里是 undefined 就是类目地址不对")
    print(f"✅ {country} {slug} 抓得到：{len(items)} 条\n   页面标题：{name}\n   第 1 名：{items[0]['title'][:60]}\n"
          "   核对标题和第 1 名是不是你要的品类：子类目编号不对时，亚马逊会退回到上一级大类，照样抓得到")


def list_children(country, slug=""):
    if country not in SITES:
        sys.exit(f"脚本里没有 {country} 站，支持：{' '.join(SITES)}")
    _, page = fetch(country, slug)
    print(f"{country} {slug or '一级类目'} 下面的类目：")
    seen = set()
    for path, name in re.findall(r'href="[^"]*?/(?:gp/bestsellers|zgbs)/([^"/]+(?:/\d+)?)/ref=zg_bs_nav_[^"]*"[^>]*>([^<]+)<', page):
        if path != slug and path not in seen:
            seen.add(path)
            print(f"  {html.unescape(name).strip()}  →  {path}")
    if not seen:
        print("  没找到（这一级没有子类目，或页面被拦）")


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--test":
        return test(sys.argv[2].upper(), sys.argv[3])
    if len(sys.argv) in (3, 4) and sys.argv[1] == "--list":
        return list_children(sys.argv[2].upper(), sys.argv[3] if len(sys.argv) == 4 else "")
    p = project_dir(sys.argv[1] if len(sys.argv) > 1 else None)
    cats = load_config(p)["amazon_bestsellers"]
    data = os.path.join(p, "数据")
    os.makedirs(data, exist_ok=True)
    out, rep = os.path.join(data, "amazon_bestsellers.csv"), os.path.join(data, "amazon_bestsellers_本周变化.md")
    today = dt.date.today().isoformat()
    rows = [r for r in load(out) if r["collected"] != today]  # 同一天重跑覆盖
    errors, got = {}, 0
    for cat, slugs in cats.items():
        for c, slug in slugs.items():
            if c not in SITES:
                errors[(c, cat)] = f"脚本里没有 {c} 站"
                continue
            try:
                code, page = fetch(c, slug)
                items = parse(page)
                if not items:
                    raise RuntimeError(f"HTTP {code}，" + ("出了验证码" if "captcha" in page.lower() else "页面没有商品（类目地址不对或被拦）"))
            except Exception as e:
                errors[(c, cat)] = str(e)[:200]
                print(c, cat, "失败:", errors[(c, cat)])
                time.sleep(GAP)
                continue
            for i in items:
                rows.append({"collected": today, "country": c, "category": cat, **i,
                             "link": f"https://{SITES[c][0]}/dp/{i['asin']}"})
            got += len(items)
            print(c, cat, len(items), "条，其中有标题的", sum(1 for i in items if i["title"]))
            time.sleep(GAP)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    report(rep, cats, rows, today, errors)
    print(today, "共", got, "条 →", rep)


if __name__ == "__main__":
    main()
