#!/bin/zsh
# 自动出刊（只支持 Mac）：由 install_schedule.py 装的定时任务触发，也可以手动跑。
# 先跑不用 AI 的采集（折扣热榜、亚马逊畅销榜和新品榜），再用 claude -p 按 skill 出一期。
# 用法：zsh run_weekly.sh [周刊文件夹]      不给就用 init_project.py 记住的那个，再没有就用 ~/外贸情报局周刊
setopt null_glob
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
SKILL="${0:A:h:h}"
P="${1:-$(cat "$HOME/.config/trade-intel-weekly/周刊文件夹.txt" 2>/dev/null)}"
P="${P:-$HOME/外贸情报局周刊}"
cd "$P" || exit 1
mkdir -p logs 各期
LOG="$P/logs/$(date +%Y%m%d).log"
files=(各期/*.md)
ISSUE=$(printf "%03d" $(( ${#files} + 1 )))
OUT="各期/第${ISSUE}期_$(date +%Y-%m-%d).md"

{
  echo "=== 采集 $(date) ==="
  python3 "$SKILL/scripts/deals_collect.py" "$P"
  caffeinate -i python3 "$SKILL/scripts/amazon_bestsellers.py" "$P"
} >> "$LOG" 2>&1

PROMPT="今天是 $(date +%Y-%m-%d)。请用 trade-intel-weekly skill 出《外贸情报局周刊》第 $((10#$ISSUE)) 期，统计最近 7 天。
周刊文件夹是 $P（就是当前目录），skill 目录是 $SKILL。
- 折扣热榜和亚马逊畅销榜、新品榜刚采好，直接读，不要再抓榜单页。
- 机会榜前 3 名用 import_stats.py 查官方进口数据（美国没配 key 就跳过）。
- 新一期存为 $OUT，写完更新 信号台账.md。
- 这是无人值守运行：不要提问；需要周刊主人决定或要花钱查的事，写进「下期跟踪」。
- 绝对不要调用信风或任何收费接口。
- 不改 config.json 和 选品档案.md，不动周刊文件夹以外的文件。"

{
  echo "=== 出刊 $(date) ==="
  caffeinate -i claude -p "$PROMPT" \
    --permission-mode dontAsk \
    --add-dir "$SKILL" \
    --allowedTools "Skill Read Write Edit Glob Grep WebSearch WebFetch Bash(python3:*) Bash(curl:*) Bash(ls:*) Bash(date:*) Bash(rdt:*)" \
    --no-session-persistence
  echo "=== 结束 $(date) exit=$? ==="
} >> "$LOG" 2>&1

if [ -f "$OUT" ]; then
  osascript -e "display notification \"第 $((10#$ISSUE)) 期已出刊，在 $P/各期/\" with title \"外贸情报局周刊\" sound name \"Glass\""
else
  osascript -e "display notification \"这期没生成出来，看 $P/logs/ 里的日志\" with title \"外贸情报局周刊\" sound name \"Basso\""
fi
