"""Mac 定时任务（launchd，系统自带）：每天收折扣热榜、每周自动出刊。只支持 Mac。

用法：
  python3 install_schedule.py <周刊文件夹> --deals 21:00         每天 21:00 收折扣热榜（不用 AI，不花钱）
  python3 install_schedule.py <周刊文件夹> --weekly 1 07:00      每周一 07:00 自动出刊（会用 Claude 额度）
  python3 install_schedule.py <周刊文件夹> --status              看装了哪些
  python3 install_schedule.py <周刊文件夹> --remove              全部停掉并删除
星期：1=周一 … 7=周日。到点时电脑在睡眠，唤醒后会补跑一次。
"""
import argparse, hashlib, os, platform, plistlib, subprocess, sys
from _common import project_dir

if platform.system() != "Darwin":
    sys.exit("定时任务只支持 Mac。其他系统请手动出刊：跟 AI 说「出周刊」。")

SKILL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ap = argparse.ArgumentParser()
ap.add_argument("project", nargs="?")
ap.add_argument("--deals", metavar="HH:MM")
ap.add_argument("--weekly", nargs=2, metavar=("星期", "HH:MM"))
ap.add_argument("--status", action="store_true")
ap.add_argument("--remove", action="store_true")
a = ap.parse_args()

P = project_dir(a.project)
tag = hashlib.md5(P.encode()).hexdigest()[:6]
AGENTS = os.path.expanduser("~/Library/LaunchAgents")
DOMAIN = f"gui/{os.getuid()}"
JOBS = {
    "deals": f'python3 "{SKILL}/scripts/deals_collect.py" "{P}" >> "{P}/logs/deals.log" 2>&1',
    "weekly": f'zsh "{SKILL}/scripts/run_weekly.sh" "{P}"',
}


def label(kind):
    return f"com.trade-intel-weekly.{tag}.{kind}"


def plist_path(kind):
    return os.path.join(AGENTS, label(kind) + ".plist")


def hm(s):
    h, m = s.split(":")
    return {"Hour": int(h), "Minute": int(m)}


def install(kind, when):
    os.makedirs(AGENTS, exist_ok=True)
    os.makedirs(os.path.join(P, "logs"), exist_ok=True)
    path = plist_path(kind)
    subprocess.run(["launchctl", "bootout", DOMAIN, path], capture_output=True)
    with open(path, "wb") as f:  # 经 zsh 登录环境启动，才能找到 python3、claude
        plistlib.dump({"Label": label(kind), "ProgramArguments": ["/bin/zsh", "-lc", JOBS[kind]],
                       "StartCalendarInterval": when, "RunAtLoad": False,
                       "StandardErrorPath": os.path.join(P, "logs", f"launchd_{kind}.err")}, f)
    r = subprocess.run(["launchctl", "bootstrap", DOMAIN, path], capture_output=True, text=True)
    print(f"{'已装' if r.returncode == 0 else '装失败'}：{label(kind)} {when}" + (f"  {r.stderr.strip()}" if r.returncode else ""))


if a.remove:
    for kind in JOBS:
        if os.path.exists(plist_path(kind)):
            subprocess.run(["launchctl", "bootout", DOMAIN, plist_path(kind)], capture_output=True)
            os.remove(plist_path(kind))
            print("已删除：", label(kind))
elif a.status:
    for kind in JOBS:
        on = subprocess.run(["launchctl", "print", f"{DOMAIN}/{label(kind)}"], capture_output=True).returncode == 0
        print(f"{'✅ 在跑' if on else '⚪ 没装'}：{label(kind)}")
else:
    if a.deals:
        install("deals", hm(a.deals))
    if a.weekly:
        day = int(a.weekly[0]) % 7  # launchd 里 0 = 周日
        install("weekly", {"Weekday": day, **hm(a.weekly[1])})
    if not (a.deals or a.weekly):
        ap.print_help()
