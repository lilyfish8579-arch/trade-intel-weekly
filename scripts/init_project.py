"""建周刊文件夹：config.json、选品档案.md、信号台账.md，以及 各期/、数据/、logs/。已有的文件不覆盖。
建完把路径记到 ~/.config/trade-intel-weekly/周刊文件夹.txt，以后开新对话不用再问放哪。

用法：python3 init_project.py [周刊文件夹]      默认 ~/外贸情报局周刊
      python3 init_project.py --where            看记住的是哪个文件夹
"""
import os, shutil, sys
from _common import DEFAULT, POINTER, remembered

if sys.argv[1:] == ["--where"]:
    sys.exit(f"记住的周刊文件夹：{remembered() or '还没有（默认 ' + DEFAULT + '）'}")

TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
p = os.path.abspath(os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
if p.startswith(("/tmp/", "/private/tmp/", "/var/folders/")):
    print("⚠️ 这是临时文件夹，电脑重启后可能被清空，正式用请换个地方")

for d in ("各期", "数据", "logs"):
    os.makedirs(os.path.join(p, d), exist_ok=True)
for f in ("config.json", "选品档案.md", "信号台账.md"):
    dst = os.path.join(p, f)
    if os.path.exists(dst):
        print("已有，不覆盖：", dst)
    else:
        shutil.copy(os.path.join(TPL, f), dst)
        print("新建：", dst)
os.makedirs(os.path.dirname(POINTER), exist_ok=True)
with open(POINTER, "w", encoding="utf-8") as fh:
    fh.write(p)
print("周刊文件夹：", p, "（已记住）")
