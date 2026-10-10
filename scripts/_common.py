"""各脚本共用：找周刊文件夹、读 config.json。

周刊文件夹的找法：命令行给了就用 → 读 POINTER 里记的路径（init_project.py 写的）→ 默认 ~/外贸情报局周刊。
"""
import json, os, sys

DEFAULT = "~/外贸情报局周刊"
POINTER = os.path.expanduser("~/.config/trade-intel-weekly/周刊文件夹.txt")


def remembered():
    try:
        with open(POINTER, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def project_dir(arg=None):
    p = os.path.abspath(os.path.expanduser(arg or remembered() or DEFAULT))
    if not os.path.exists(os.path.join(p, "config.json")):
        sys.exit(f"{p} 里没有 config.json。先跑 init_project.py 建周刊文件夹，或把周刊文件夹路径作为第一个参数传进来。")
    return p


def load_config(p):
    with open(os.path.join(p, "config.json"), encoding="utf-8") as f:
        return json.load(f)
