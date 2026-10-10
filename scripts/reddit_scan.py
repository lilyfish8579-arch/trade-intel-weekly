"""Reddit 消费者讨论（可选模块）：消费类板块本周热帖 + 在这些板块里搜"缺货/涨价/买不到"。

用法：python3 reddit_scan.py <周刊文件夹>      板块和搜索词读 config.json 的 reddit
要先装 rdt-cli 并登录（pipx install rdt-cli，浏览器登录 reddit.com 后跑 rdt login）；没装就跳过。
输出：分数 | 评论数 | 标题 | 链接 | 帖子 ID。值得细看的帖子用 `rdt read <帖子ID>` 读评论。
第一次抓取失败就整个停掉，不重试。
"""
import json, shutil, subprocess, sys, time
from _common import project_dir, load_config

rdt = shutil.which("rdt")
if not rdt:
    sys.exit("没装 rdt（Reddit 是可选模块），本期跳过，附录写「Reddit 未接入」")
cfg = load_config(project_dir(sys.argv[1] if len(sys.argv) > 1 else None)).get("reddit", {})


def walk(o):
    if isinstance(o, dict):
        if "title" in o and "score" in o and "name" in o:
            yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def posts(args, n):
    r = subprocess.run([rdt, *args, "--json"], capture_output=True, text=True, timeout=60)
    try:
        return list(walk(json.loads(r.stdout)))[:n]
    except ValueError:
        return None


jobs = [(f"r/{s} 本周热帖", ["sub", s, "--sort", "top", "--time", "week", "--limit", "6"], 6) for s in cfg.get("subs", [])]
subs = "+".join(cfg.get("subs", []))  # 关键词只在这些消费类板块里搜，全站搜索噪音太大
jobs += [(f"消费类板块里搜「{q}」本周", ["search", q, "-r", subs, "--sort", "top", "--time", "week", "--limit", "8"], 8)
         for q in cfg.get("queries", []) if subs]
for title, args, n in jobs:
    print(f"## {title}")
    ps = posts(args, n)
    if ps is None:
        sys.exit("  抓取失败，Reddit 本期停掉，附录写明（不要重试）")
    for p in ps:
        pid = p["name"].removeprefix("t3_")
        t = p["title"].replace("\n", " ")[:110]
        print(f"  [{p['score']}分 {p.get('num_comments', 0)}评] {t} | https://www.reddit.com/comments/{pid}/ | ID {pid}")
    sys.stdout.flush()
    time.sleep(2)
