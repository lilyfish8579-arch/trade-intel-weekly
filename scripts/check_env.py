"""检查这台电脑能跑周刊的哪些部分，缺什么、怎么装。

用法：python3 check_env.py
"""
import importlib.util, os, platform, shutil, subprocess, sys

rows = []
rows.append(("Python 3.9 以上", sys.version_info >= (3, 9), f"当前 {platform.python_version()}"))
rows.append(("curl（亚马逊畅销榜、搜索页抽样）", bool(shutil.which("curl")), "Mac 和 Windows 10 以上都自带"))

pt = importlib.util.find_spec("pytrends") is not None
rows.append(("pytrends（Google 购物飙升词、同比）", pt,
             "已装" if pt else "没装。装：python3 -m pip install --user pytrends"
             "（报 externally-managed-environment 就在命令末尾加 --break-system-packages）"))

rdt = shutil.which("rdt")
if rdt:
    st = subprocess.run([rdt, "status"], capture_output=True, text=True).stdout
    ok = "authenticated: true" in st
    rows.append(("Reddit（可选）", ok, "已登录" if ok else "装了没登录：先在浏览器登录 reddit.com，再跑 rdt login"))
else:
    rows.append(("Reddit（可选）", False, "没装，不装也能出刊。要装：pipx install rdt-cli，浏览器登录 reddit.com 后跑 rdt login"))

key = os.environ.get("CENSUS_API_KEY") or os.path.exists(os.path.expanduser("~/.config/trade-intel-weekly/census_key"))
rows.append(("美国官方进口数据（可选）", bool(key),
             "已配 key" if key else "没配 key，不配也能出刊（欧盟、英国、加拿大不用 key）。要配见 references/首次设置.md"))

mac = platform.system() == "Darwin"
cl = shutil.which("claude")
rows.append(("自动出刊（可选，只支持 Mac）", mac and bool(cl),
             "可以装" if mac and cl else ("不是 Mac，只能手动出刊" if not mac else "找不到 claude 命令，只能手动出刊")))

for name, ok, note in rows:
    print(f"{'✅' if ok else '⚪'} {name}：{note}")
print("\n不用装就能用：折扣社区热榜（8 国）、亚马逊畅销榜和新品榜、欧盟/英国/加拿大官方进口数据、Polymarket 预测市场、网页搜索（财报、展会、政策）")
