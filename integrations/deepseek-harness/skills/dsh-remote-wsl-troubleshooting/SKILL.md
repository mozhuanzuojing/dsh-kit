---
name: dsh-remote-wsl-troubleshooting
description: Diagnose and fix the dsh-remote-wsl plugin and its WSL-side dsh runtime — wsl_agent hangs then fails, daemon start stuck, runtime exits at startup, credential/provider errors. Triggers when the user reports dsh-remote-wsl 插件卡/慢/失败, wsl_agent 一直卡 / 超时 / "connection closed before reply", wsl_daemon 启动失败 / 启动锁 / 空等 45s, or WSL 侧 dsh runtime 启动失败. dsh-remote-wsl 插件与 WSL dsh 运行时排障。
---

# dsh-remote-wsl 排障（插件卡死 / 运行时启动失败）

宿主（DSH Desktop，Windows）通过 WSL 里的常驻 daemon 跑 `dsh --profile sdk`，`wsl_agent` 是入口。
绝大多数“插件一直卡”**不是网络问题**，而是 **运行时进程死了没人报 + 上层干等超时**。

## 一图流程
```
 ┌───────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────┐   ┌────────────┐
 │ 1 复现     │──▶│ 2 取证        │──▶│ 3 定位四层     │──▶│ 4 最小修复   │──▶│ 5 验证      │
 │ 调一次     │   │ daemon.log    │   │ 进程退出?      │   │ 源码/凭据    │   │ 单测+实跑   │
 │ wsl_agent  │   │ startup-*.log │   │ 启动锁?        │   │ 配置         │   │ 秒级返回真实 │
 │            │   │ ps/ss/systemd │   │ 凭据 schema?   │   │              │   │ 原因(retry=F)│
 └───────────┘   └──────────────┘   │ 上游鉴权?      │   └────────────┘   └────────────┘
                                     └──────────────┘
```

## 定位图（本 skill 在系统中的位置）
```
 输入                         分析引擎(本 skill)                    输出
 ─────                        ─────────────────                    ─────
 用户症状/日志 ─┐              ┌───────────────────┐               ┌─ 源码修复: sdk-runtime / daemon / daemon-protocol
 wsl_status   ─┼──▶ 分诊表 ──▶│ 症状→根因→动作 映射 │──▶ 修复 ──────┼─ 凭据修复: ~/.dsh/.credentials.yaml (备份后)
 daemon.log   ─┘              └───────────────────┘               └─ 验证证据: 单测 + wsl_agent 实跑
        ▲                              │ 依赖 diagnose 的“复现→假设→验证→回归”方法
        └──────────── 证据回流 ◀────────┘
```

## 判断矩阵（阶段 × 维度）
```
            │ 进程退出            │ 启动锁               │ 凭据 schema           │ 上游鉴权
 ───────────┼─────────────────────┼──────────────────────┼───────────────────────┼──────────────────────
 现象        │ 卡~120s 后 socket重置│ 空等45s“锁被占用”     │ startup failed:       │ AUTH 401 /
            │ / connection closed  │                      │ required plugin 未激活 │ MISSING_CREDENTIAL
 证据        │ 无 recv op=prompt 后 │ ensure.<slot>.lock    │ startup-*.log 里       │ turn/end 里 err.message
            │ “运行时已退出(exit=1)”│ 父目录缺失             │ “unknown kind ...”     │ 或 daemon 返回 error
 修复        │ exited 纳入 prompt竞速│ 抢锁前 mkdir -p 父目录│ 删/移不受支持的 record │ provider 指对网关/key
 验证        │ 秒级 retryable=false │ 单测：父目录缺失仍LOCKED│ --dump-config exit 0  │ wsl_agent 出正文
```

## 快速分诊（症状 → 根因 → 动作）
| 症状 | 最可能根因 | 动作 |
|---|---|---|
| wsl_agent 每次卡 ~120s 后 `connection closed before reply` / “socket 被重置” | `SdkRuntime` 没感知运行时**中途退出**，`turnDone` 永不 resolve，守护干等到 socket 空闲 120s | 看 daemon.log 是否 `运行时已退出(exit=1) ⇒ 丢弃`；修 sdk-runtime 把 `this.exited` 纳入 prompt 竞速（F1） |
| `wsl_daemon start` 空等 45s 报“启动锁被另一个宿主持有” | 状态目录 `<wslHome>/.dsh/remote-wsl` 不存在 ⇒ 抢锁 `mkdir "$d"` 因父目录缺失恒失败（鸡生蛋：目录本由拿锁后的 launchDaemon 创建） | `acquireEnsureLockScript` 抢锁前 `mkdir -p "$(dirname "$d")"`（umask 077）；或先手建目录（F2） |
| runtime `startup failed: 1 required plugin did not activate` … `credentials … unknown kind "password"` | `~/.dsh/.credentials.yaml` 有 dsh 0.2.2 不认的 kind（只认 `api-key` / `grant`） | 备份后删/移该 record；`--dump-config` 验证 exit 0（F3） |
| `MISSING_CREDENTIAL` / `AUTH 401 … api key invalid` | provider 与 key 不匹配（默认 `deepseek-official` 无有效 key；本机实际走 Magpie 网关） | 指向实际网关（`MAGPIE_GATEWAY_KEY` + `llm-pi-ai`）或放有效 `DEEPSEEK_API_KEY`（F4） |
| `wsl_exec` 偶发 `bash: /tmp/dsh-rwsl-<winpid>-*.sh: No such file or directory` | 一次性启动脚本在 /tmp 被并发清理/取消失效 | 重试即可；连续出现再查（F5） |

## 关键路径与命令
- 插件源码（本机运行中的副本）：`D:\project\dsh1\dsh-remote-wsl`（WSL 内 `/mnt/d/project/dsh1/dsh-remote-wsl`）
- 守护状态目录：`<wslHome>/.dsh/remote-wsl/` → `daemon.log`、`launch-stderr.log`、`daemon.<slot>.json`、`daemon.<slot>.token`
- dsh 启动诊断：`~/.dsh/logs/startup-*.log`
- 进程/服务：`ps -eo pid,etime,cmd | grep daemon.ts`；`systemctl --user status dsh-rwsl-<port>.service`；`ss -tn | grep <port>`
- 凭据：`$DSH_HOME/.credentials.yaml`（默认 `~/.dsh/.credentials.yaml`），合法 kind 只有 `api-key` / `grant`
- 运行时：`mise exec -- pnpm dlx @deepseek-ai/dsh@<ver> --profile sdk`；dlx 缓存 `~/.cache/pnpm/dlx`；**不依赖全局 dsh**
- 一键取证：`scripts/collect-diagnostics.sh`（拷到 WSL 里 `bash` 即可）

## 验证与生效
- 单测（WSL）：`cd /mnt/d/project/dsh1/dsh-remote-wsl && node --experimental-strip-types --test test/xxx.test.ts`
- 语法：`node --experimental-strip-types scripts/check-syntax.ts`
- 守护侧重启：`wsl_daemon action=restart`（`daemon.ts` / `sdk-runtime.ts` 改动即刻生效）
- 宿主侧改动（`daemon-protocol.ts` / `daemon-lifecycle.ts` / `register-tools.ts`）需**重启 DSH Desktop** 才加载
- 判据：修复后 `wsl_agent` 应在**秒级**返回真实原因（`retryable=false` + exit 码 + stderr），而不是 120s 后报 socket

## 纪律
- 不盲目 `wsl_daemon stop all`（会杀带会话的健康守护）；先 `status` / 扫描确认身份。
- 改 `.credentials.yaml` 必先备份（含凭据）；只删被 dsh 拒绝的条目，不误删有效 ref/record。
- 用 DSH Desktop 时，WSL 只需 **sdk 能力**（`--profile sdk` = dsh-base + dsh-sdk-app）；全局 dsh / web / tui 可不要。

详细根因、日志证据与命令见 `references/failure-modes.md`。
