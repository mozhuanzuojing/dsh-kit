#!/usr/bin/env bash
# dsh-remote-wsl 诊断信息收集（在 WSL 内运行）
# 用法: bash collect-diagnostics.sh [daemonPort]
# 只读：仅打印信息，不改任何文件。
set -uo pipefail
PORT="${1:-8731}"
STATE="${HOME}/.dsh/remote-wsl"

echo "=== date ==="; date
echo "=== daemon 进程 ==="
ps -eo pid,ppid,etime,stat,cmd | grep -E 'daemon\.ts' | grep -v grep || echo "none"
echo "=== systemd unit (dsh-rwsl-${PORT}.service) ==="
systemctl --user status "dsh-rwsl-${PORT}.service" --no-pager 2>&1 | head -15 || echo "none"
echo "=== 监听 ${PORT} ==="
ss -tn 2>/dev/null | grep ":${PORT}" || echo "none"
echo "=== state dir ==="; ls -la "$STATE" 2>/dev/null || echo "missing: $STATE"
echo "=== meta（含 session/key 摘要）==="
cat "$STATE/daemon.${PORT}.json" 2>/dev/null || echo "none"
echo "=== daemon.log（非 fs 噪声，末尾 60 行）==="
grep -v -E 'recv op=fs|客户端断开|连接空闲' "$STATE/daemon.log" 2>/dev/null | tail -n 60 || echo "none"
echo "=== launch-stderr.log 末尾 20 行 ==="
tail -n 20 "$STATE/launch-stderr.log" 2>/dev/null || echo "none"
echo "=== 最近的 dsh 启动日志（首个 40 行，通常是崩溃原因）==="
for f in $(ls -t "$HOME/.dsh/logs"/startup-*.log 2>/dev/null | head -1); do
  echo "--- $f"; sed -n '1,40p' "$f"
done
echo "=== credentials（keys/kinds，值不打印）==="
grep -nE '^[[:space:]]*(kind|version|[A-Z_]+):' "$HOME/.dsh/.credentials.yaml" 2>/dev/null || echo "none"
echo "=== profiles ==="; ls -la "$HOME/.dsh/profiles" 2>/dev/null || echo "none"
echo "=== dlx dsh 版本缓存 ==="
for f in "$HOME"/.cache/pnpm/dlx/*/*/node_modules/@deepseek-ai/dsh/package.json; do
  [ -f "$f" ] && sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/dsh=\1/p' "$f" | head -1
done 2>/dev/null | sort -u
