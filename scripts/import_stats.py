"""官方进口数据（验证层，不靠谷歌的硬数据）：某个税号在各国的月度进口，从中国、从美国进口多少，和去年同期比。

用法：python3 import_stats.py 税号 [国家 ...]
      税号用 6 位（如 732391）；欧盟、英国也可以用 8 位（如 95030070）
      国家：欧盟成员国代码（DE FR NL IT ES AT BE SE DK FI IE PL ...）、GB、CA、US；默认 US CA GB DE FR NL IT ES
例：python3 import_stats.py 732391 US CA GB DE
输出每国：今年 1 月到最新月的累计 vs 去年同期（总进口、从中国、从美国）、中国份额变化、最新月 vs 去年同月；美国、加拿大另列中国以外的前 3 个来源国。
只用来复核机会榜前几名：税号粗（捏捏玩具藏在"玩具"大类里），数据滞后 1–3 个月，不适合用来发现。
单月常有一次性大单或抢关税的突增，判断方向时看看月度明细（加 -v）。

来源（都免费，2026-10 实测）：
- 欧盟统计局 Comext（免注册，欧元，最新约晚两个半月）
- 英国海关 HMRC uktradeinfo（免注册，英镑，最新约晚两个半月）
- 加拿大统计局 CIMT 年度文件（免注册，加元，最新约晚一个半月；每年一个 60–80MB 的压缩包，缓存在 ~/.cache/trade-intel/cimt/，当年的文件超过 7 天自动重下）
- 美国人口普查局 intltrade 接口（美元，最新约晚一个半月）：要免费 API key，注册见 references/首次设置.md；
  key 放在环境变量 CENSUS_API_KEY 或 ~/.config/trade-intel-weekly/census_key，没有 key 就跳过美国
"""
import csv, datetime as dt, io, json, os, sys, time, urllib.parse, urllib.request, zipfile
from collections import defaultdict

CACHE = os.path.expanduser("~/.cache/trade-intel/cimt")
CENSUS_KEY = os.path.expanduser("~/.config/trade-intel-weekly/census_key")
EU = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV",
      "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"}
CUR = {"GB": "英镑", "CA": "加元", "US": "美元"}
THIS = dt.date.today().year
LAST = THIS - 1


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 trade-intel-weekly"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def comext(geo, hs):
    """返回 {(partner, 'YYYY-MM'): 欧元}，partner 取 CN、US、WORLD。"""
    out = {}
    for partner in ("CN", "US", "WORLD"):
        q = urllib.parse.urlencode({"format": "JSON", "lang": "en", "freq": "M", "reporter": geo, "partner": partner,
                                    "product": hs, "flow": "1", "indicators": "VALUE_IN_EUROS", "sinceTimePeriod": f"{LAST}-01"})
        d = json.loads(get("https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409?" + q))
        if "error" in d:
            raise RuntimeError(str(d["error"])[:150])
        times = {v: k for k, v in d["dimension"]["time"]["category"]["index"].items()}
        for i, v in d.get("value", {}).items():
            out[(partner, times[int(i)])] = v
        time.sleep(1)
    src = ("https://ec.europa.eu/eurostat/databrowser/view/DS-045409/default/table"
           f"（Comext，报告国 {geo}，产品 {hs}）")
    return out, src


def hmrc(hs):
    lo, hi = (hs + "00", hs + "99") if len(hs) == 6 else (hs, hs)
    flt = f"CommodityId ge {lo} and CommodityId le {hi} and MonthId ge {LAST}01 and (FlowTypeId eq 1 or FlowTypeId eq 3)"
    url = ("https://api.uktradeinfo.com/OTS?$apply=" + urllib.parse.quote(f"filter({flt})/groupby((MonthId,CountryId),aggregate(Value with sum as V))"))
    out = defaultdict(float)
    while url:
        d = json.loads(get(url))
        for x in d["value"]:
            m = str(x["MonthId"])
            ym = f"{m[:4]}-{m[4:]}"
            out[("WORLD", ym)] += x["V"]
            if x["CountryId"] == 720:  # 中国
                out[("CN", ym)] += x["V"]
            if x["CountryId"] in (400, 902):  # 美国（HMRC 里有两个代码）
                out[("US", ym)] += x["V"]
        url = d.get("@odata.nextLink")
    return dict(out), f"https://www.uktradeinfo.com/trade-data/ots-custom-table/（HMRC，商品 {hs}）"


def cimt_file(year):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"CIMT-CICM_Imp_{year}.zip")
    stale = year == THIS and os.path.exists(path) and time.time() - os.path.getmtime(path) > 7 * 86400
    if not os.path.exists(path) or stale:
        data = get(f"https://www150.statcan.gc.ca/n1/pub/71-607-x/2021004/zip/CIMT-CICM_Imp_{year}.zip", timeout=600)
        with open(path, "wb") as f:
            f.write(data)
    return path


def cimt(hs):
    if len(hs) != 6:
        raise RuntimeError("加拿大文件是 6 位税号，8 位的查不了")
    out = defaultdict(float)
    for year in (LAST, THIS):
        with zipfile.ZipFile(cimt_file(year)) as z:
            name = next(n for n in z.namelist() if "ODPFN015_" in n)  # 6 位税号 × 国家 × 省 × 州
            with z.open(name) as f:
                r = csv.reader(io.TextIOWrapper(f, encoding="latin-1"))
                next(r)
                for row in r:
                    if row[1] != hs:
                        continue
                    ym = f"{row[0][:4]}-{row[0][4:]}"
                    v = float(row[5] or 0)
                    out[("WORLD", ym)] += v
                    if row[2] in ("CN", "US"):
                        out[(row[2], ym)] += v
                    out[("C:" + row[2], ym)] += v
    return dict(out), f"https://www150.statcan.gc.ca/n1/pub/71-607-x/71-607-x2021004-eng.htm（CIMT 年度文件，HS {hs}）"


def census(hs):
    if len(hs) not in (6, 10):
        raise RuntimeError("美国接口用 6 位或 10 位税号")
    key = os.environ.get("CENSUS_API_KEY") or (open(CENSUS_KEY).read().strip() if os.path.exists(CENSUS_KEY) else "")
    if not key:
        raise RuntimeError(f"没有 API key（应在 {CENSUS_KEY}）")
    q = urllib.parse.urlencode({"get": "CTY_CODE,CTY_NAME,GEN_VAL_MO", "I_COMMODITY": hs, "COMM_LVL": f"HS{len(hs)}",
                                "time": f"from {LAST}-01", "key": key})
    rows = json.loads(get("https://api.census.gov/data/timeseries/intltrade/imports/hs?" + q))
    h = rows[0]
    out = defaultdict(float)
    for r in rows[1:]:
        x = dict(zip(h, r))
        code, ym, v = x["CTY_CODE"], x["time"], float(x["GEN_VAL_MO"] or 0)
        if code == "-":  # 全部国家合计
            out[("WORLD", ym)] += v
        elif code == "5700":  # 中国
            out[("CN", ym)] += v
            out[("C:中国", ym)] += v
        elif code[:1] in "1234567" and "X" not in code:  # 单个国家（去掉欧盟、亚洲这类合计行）
            out[("C:" + x["CTY_NAME"].title(), ym)] += v
    return dict(out), f"https://usatrade.census.gov/（美国人口普查局 intltrade 接口，HS {hs}，一般进口额）"


def summarize(geo, hs, data, src, verbose):
    # 总进口（WORLD）有时比分国数据晚一个月发布，比较窗口取它也有数据的最新月，各项口径才一致
    world = sorted(ym for (p, ym) in data if p == "WORLD" and ym.startswith(str(THIS)))
    months = world or sorted({ym for (_, ym) in data if ym.startswith(str(THIS))})
    if not months:
        return f"{geo} {hs}：今年还没有数据"
    last = months[-1]
    n = int(last[5:])
    unit = CUR.get(geo, "欧元")

    def total(p, y):
        return sum(data.get((p, f"{y}-{m:02d}"), 0) for m in range(1, n + 1))

    def pct(a, b):
        return f"{(b / a - 1) * 100:+.0f}%" if a else "去年无数据"

    lines = [f"{geo} · {hs}（{unit}，{THIS} 年 1–{n} 月 vs {LAST} 年同期；最新到 {last}）"]
    for p, name in (("WORLD", "总进口"), ("CN", "从中国"), ("US", "从美国")):
        a, b = total(p, LAST), total(p, THIS)
        if a or b:
            lines.append(f"  {name}：{b / 1e6:.2f} 百万 vs {a / 1e6:.2f} 百万，{pct(a, b)}")
    for p, name in (("CN", "中国"), ("US", "美国")):
        a0, b0 = total("WORLD", LAST), total("WORLD", THIS)
        if a0 and b0 and (total(p, LAST) or total(p, THIS)):
            lines.append(f"  {name}份额：{total(p, LAST) / a0 * 100:.0f}% → {total(p, THIS) / b0 * 100:.0f}%")
    others = {p[2:] for (p, _) in data if p.startswith("C:")} - {"CN", "中国", "US"}
    if others:
        top = sorted(others, key=lambda c: -total("C:" + c, THIS))[:3]
        lines.append("  中国以外的前 3 个来源：" + "；".join(f"{c} {total('C:' + c, THIS) / 1e6:.2f} 百万（{pct(total('C:' + c, LAST), total('C:' + c, THIS))}）" for c in top))
    prev = f"{LAST}-{last[5:]}"
    lines.append(f"  最新月 {last}：从中国 {data.get(('CN', last), 0) / 1e6:.2f} 百万 vs 去年同月 {data.get(('CN', prev), 0) / 1e6:.2f} 百万")
    if verbose:
        for p in ("CN", "US", "WORLD"):
            ms = sorted(ym for (q, ym) in data if q == p)
            if not ms:
                continue
            lines.append(f"  月度 {p}（千）：" + "；".join(f"{ym} {data[(p, ym)] / 1e3:.0f}" for ym in ms))
    lines.append(f"  来源：{src}")
    return "\n".join(lines)


def main():
    args = [a for a in sys.argv[1:] if a != "-v"]
    verbose = "-v" in sys.argv
    if not args:
        sys.exit(__doc__)
    hs, geos = args[0], [g.upper() for g in args[1:]] or ["US", "CA", "GB", "DE", "FR", "NL", "IT", "ES"]
    print(f"# python3 import_stats.py {' '.join(sys.argv[1:])}（{dt.date.today()} 运行）")
    for geo in geos:
        try:
            if geo in EU:
                data, src = comext(geo, hs)
            elif geo == "GB":
                data, src = hmrc(hs)
            elif geo == "CA":
                data, src = cimt(hs)
            elif geo == "US":
                data, src = census(hs)
            else:
                print(f"{geo}：不支持")
                continue
            print(summarize(geo, hs, data, src, verbose))
        except Exception as e:  # 第一次失败就停在这一国，不重试
            print(f"{geo} {hs}：失败 {str(e)[:150]}（不重试，写进附录）")


if __name__ == "__main__":
    main()
