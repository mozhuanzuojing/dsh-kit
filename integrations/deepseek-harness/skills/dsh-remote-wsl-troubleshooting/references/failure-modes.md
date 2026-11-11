# 失败模式详解（根因 · 证据 · 修复 · 验证）

来源：2026-11-07 一次真实排障（插件 `dsh-remote-wsl` 0.3.20，WSL 发行版 debian-u8-1，dsh 0.2.2-rc.1）。
标记：**事实**=有日志/源码/命令证据；**判断**=基于证据的推断；**假设**=未完全证实。

---

## F1 — 运行时中途退出，wsl_agent 卡 ~120s 后报 socket 重置  【事实】

- **现象**：每次 `wsl_agent` 先“卡”约 120s，然后返回
  `守护调用失败(closed): connection closed before reply … Windows→WSL socket 被重置`。
- **证据**（`~/.dsh/remote-wsl/daemon.log`）：
  ```
  recv op=prompt id=1 key=default peer=win-pid-...
  spawning runtime key=default dsh@0.2.2-rc.1 cwd=/home/g
  runtime ready key=default pid=... session=remote-wsl-default-...
  （约 120s 后，下一次 prompt 才出现）
  key=default cwd=/home/g 运行时已退出(exit=1) ⇒ 丢弃（上下文已重置）
  ```
  即：运行时启动成功 → 一轮 prompt 中进程退出 exit=1 → 但守护当时**不知道**。
- **根因**（`src/sdk-runtime.ts` 的 `#prompt`）：只 `Promise.race([turnDone, sleep(promptTimeoutMs)])`。
  子进程中途 `exit` 时 `turnDone` 永不 resolve；守护侧这一轮一直挂着，客户端只能等 daemon 连接
  空闲超时（`SOCKET_IDLE_MS=120000`）被 `socket.destroy()` → 收到“connection closed before reply”，
  真正的退出原因被吞掉。
- **修复**：
  1. `#prompt` 把 `this.exited` 纳入竞速，进程一死立即抛 `RUNTIME_EXITED`（带 exit 码 + stderr 尾巴）；
  2. `start()` 的 `exit` 监听里 `#failPendingAfterExit(code)`，reject 所有在飞 `request()`；
  3. `daemon.ts` 的 `pump` catch：`RUNTIME_EXITED` ⇒ `retryable:false`，真实原因上抛；
  4. 超时用可清除的 timer（不要裸 `sleep`，避免 5 分钟定时器泄漏）。
- **验证**：`test/sdk-runtime-exit.test.ts`（fake runtime：initialize 回包 → session/prompt 回 messageId →
  50ms 后 exit(1) 不发 turn/end），断言 prompt 数秒内以 `RUNTIME_EXITED` 失败。
  实跑：`wsl_agent` 变成**秒级**返回 `retryable=false … runtime exited (exit=1): …`。
- **文件**：`src/sdk-runtime.ts`（exit 监听 / `#prompt` 竞速 / `#failPendingAfterExit`）、`src/daemon.ts`（`pump` catch）。

---

## F2 — 首次启动状态目录缺失 ⇒ 启动锁死锁，空等 45s  【事实】

- **现象**：`wsl_daemon start` 卡约 45s 后报
  `槽位 8731 的启动锁被另一个宿主持有超过 45000ms，且期间没有出现可复用的守护`。
- **证据**：`/home/g/.dsh/remote-wsl` 不存在；该目录是 `<wslHome>/.dsh/remote-wsl`。
- **根因**（鸡生蛋）：`ensureDaemon()` 先抢启动锁（`daemon-lifecycle.ts`），锁是
  `mkdir "<stateDir>/ensure.<slot>.lock"`；而 `<stateDir>` 原本只在 `launchDaemon()`（拿锁**之后**）
  的 `ensureStateDir()` 里创建。父目录缺失 ⇒ `mkdir` 恒失败 ⇒ 脚本回 `BUSY` ⇒ 空等满 `daemonLockWaitMs`。
- **修复**（`src/daemon-protocol.ts` 的 `acquireEnsureLockScript`）：抢锁前
  `umask 077; mkdir -p -- "$(dirname -- "$d")" 2>/dev/null || true`（WSL 侧执行，目录 0700）。
- **验证**：`test/daemon-protocol.test.ts` 新用例“父目录缺失仍返回 LOCKED”；实跑建目录后守护立即起来。
- **生效**：属**宿主侧**代码 → 需重启 DSH Desktop。

---

## F3 — `.credentials.yaml` 不支持的 kind ⇒ runtime 启动失败 exit=1  【事实】

- **现象**：`wsl_agent` 报 `runtime exited (exit=1)`；`~/.dsh/logs/startup-*.log` 里：
  ```
  dsh: startup failed: 1 required plugin did not activate
  Failed plugins (1):
    credentials (@deepseek-ai/dsh-credentials-local)
    Error: credentials-local: record "u8-local/zhangsan" in /home/g/.dsh/.credentials.yaml has unknown kind "password"
  Plugins waiting for services: connection (required) credentials …
  ```
  因为 `credentials` 挂了，必需的 `connection` 激活不了，dsh 直接退出 1。
- **根因**：`dsh-credentials-local@0.2.2-rc.1` 只认 `kind: api-key` / `kind: grant`；文件里有一条
  `kind: password` 的记录（`u8-local/zhangsan`）。
- **修复**：先备份整份 `.credentials.yaml`（0600），再删除/移走该 record；
  用 `dsh --profile sdk --dump-config` 验证 exit 0（能装载即 OK）。旧数据保留在备份里。
- **隔离验证技巧**：用 `DSH_HOME=<临时目录>`（内部 `profiles/ storages/ logs/` 软链到真实目录 +
  一份净化后的 `.credentials.yaml`）跑 `--dump-config`，可在**不改真实文件**的前提下证实“只差这一条”。

---

## F4 — provider / key 不匹配 ⇒ MISSING_CREDENTIAL 或 AUTH 401  【事实/判断】

- **现象**：
  - `MISSING_CREDENTIAL: llm-deepseek: no API key for provider route "deepseek-official"`，或
  - `远端运行时在上游侧失败（AUTH 401）：Authentication Fails, Your api key: ****xxxx is invalid`
- **根因**：插件默认 `provider=deepseek-official`、`model=deepseek-flash`；但本机 WSL 实际可用的网关是
  **Magpie**（`/home/g/.local/bin/dsh` 包装器从 `C:\Users\l\.dsh\.env` 取 `MAGPIE_GATEWAY_KEY`，provider 用 `llm-pi-ai`）。
  默认路由的 `DEEPSEEK_API_KEY` 若失效就从 401 变成 MISSING_CREDENTIAL。
- **修复**（二选一）：
  1. 把插件的 `provider`/`model` 指到 `llm-pi-ai` 对应值，并让 `MAGPIE_GATEWAY_KEY` 进入 WSL 登录环境
     （插件 `useShellEnvironment=true` 会捕获登录 shell 环境给常驻运行时）；
  2. 或把一枚**有效**的 `DEEPSEEK_API_KEY` 写回 `.credentials.yaml` 的 `refs`。

---

## F5 — `wsl_exec` 偶发 /tmp 启动脚本 ENOENT  【假设，未完全证实】

- **现象**：工具调用偶发 `bash: /tmp/dsh-rwsl-<winpid>-<rand>.sh: No such file or directory`（exit 127），重试即好。
- **观察**：`wsl_exec` 每次把命令写进 `/tmp/dsh-rwsl-<winpid>-*.sh` 再 `bash <script>`；该类文件也参与
  “本主机陈旧文件收敛”。**推断**是收敛/清理与当次执行存在竞争，脚本在 `bash` 打开前被删。
- **处置**：重试；若持续发生，检查 `wsl_open_ui` / `.pid` 的收敛逻辑与并发调用量。

---

## 环境事实速查

- 插件源码（运行中的副本）：`D:\project\dsh1\dsh-remote-wsl`（WSL 内 `/mnt/d/project/dsh1/dsh-remote-wsl`），
  守护进程 cmdline 直接指向它的 `src/daemon.ts`。
- profile：`~/.dsh/profiles/sdk` = `@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-sdk-app`。
- 运行时：`mise exec -- pnpm dlx @deepseek-ai/dsh@<ver> --profile sdk`；dlx 缓存 `~/.cache/pnpm/dlx`；
  **不依赖全局 dsh**（全局 `@deepseek-ai/dsh` 可卸载，WSL 只留 sdk 能力即可）。
- 凭据：`$DSH_HOME/.credentials.yaml`（`DSH_HOME` 默认 `~/.dsh`）；合法 `kind` 仅 `api-key` / `grant`。
- dsh 启动诊断：`~/.dsh/logs/startup-*.log`。
- 守护状态：`~/.dsh/remote-wsl/{daemon.log, launch-stderr.log, daemon.<slot>.json, daemon.<slot>.token}`。
- 服务：`systemctl --user status dsh-rwsl-<port>.service`（systemd-run --user）。

## 测试/校验命令（在 WSL 里）

```bash
cd /mnt/d/project/dsh1/dsh-remote-wsl
node --experimental-strip-types scripts/check-syntax.ts
node --experimental-strip-types --test test/daemon-protocol.test.ts test/sdk-runtime-exit.test.ts
```
