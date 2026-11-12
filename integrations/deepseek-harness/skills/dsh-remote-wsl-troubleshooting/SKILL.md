---
name: dsh-remote-wsl-troubleshooting
description: Diagnose and fix the dsh-remote-wsl plugin and its WSL-side dsh runtime - wsl_agent hangs then fails, daemon start stuck, runtime exits at startup, credential/provider errors. Triggers when the user reports the dsh-remote-wsl plugin hanging, being slow, or failing; wsl_agent stuck or timing out with "connection closed before reply"; wsl_daemon failing to start or blocking on the startup lock for 45s; or the WSL-side dsh runtime failing to start. dsh-remote-wsl 插件与 WSL dsh 运行时排障。
metadata:
  origin: dsh-kit
---

# dsh-remote-wsl troubleshooting (plugin hangs / runtime fails to start)

The host (DSH Desktop on Windows) runs a long-lived daemon inside WSL that serves `dsh --profile sdk`; `wsl_agent` is the entry point.

Most "the plugin hangs forever" reports are **not network problems**. They are **a runtime process that died without reporting + an upper layer that waits for a timeout**.

## Flow at a glance

```
 ┌───────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────┐   ┌────────────┐
 │ 1 reproduce│──▶│ 2 collect    │──▶│ 3 locate     │──▶│ 4 minimal  │──▶│ 5 verify   │
 │ call once │   │ daemon.log   │   │ process exit?│   │ source /   │   │ unit test  │
 │ wsl_agent │   │ startup-*.log│   │ start lock?  │   │ credentials│   │ + real run │
 │           │   │ ps/ss/systemd│   │ credential?  │   │ config     │   │ seconds,   │
 │           │   │              │   │ upstream auth│   │            │   │ not 120s   │
 └───────────┘   └──────────────┘   └──────────────┘   └────────────┘   └────────────┘
```

## Where this skill sits

```
 input                        analysis engine (this skill)          output
 ─────                        ────────────────────────────          ──────
 user symptom / logs ─┐        ┌───────────────────┐               ┌─ source fix: sdk-runtime / daemon / daemon-protocol
 wsl_status          ─┼──▶ triage table ──▶│ symptom -> cause -> action │──▶ fix ──┼─ credential fix: ~/.dsh/.credentials.yaml (after backup)
 daemon.log          ─┘        └───────────────────┘               └─ evidence: unit test + real wsl_agent run
        ▲                              │ uses the diagnose skill's reproduce -> hypothesise -> verify -> regress method
        └──────────── evidence backflow ◀────────┘
```

## Decision matrix (stage x dimension)

```
            │ process exit         │ start lock            │ credential schema      │ upstream auth
 ───────────┼──────────────────────┼───────────────────────┼────────────────────────┼──────────────────────
 symptom    │ hangs ~120s then     │ waits 45s reporting   │ startup failed:        │ AUTH 401 /
            │ socket reset /       │ "lock held by another"│ required plugin not    │ MISSING_CREDENTIAL
            │ connection closed    │                       │ activated              │
 evidence   │ no recv op=prompt,   │ ensure.<slot>.lock    │ startup-*.log contains │ turn/end err.message
            │ then "runtime exited │ parent directory      │ "unknown kind ..."     │ or daemon error
            │ (exit=1)"            │ missing               │                        │
 fix        │ race `exited` into   │ mkdir -p parent       │ delete/move the        │ point provider at the
            │ the prompt race      │ before acquiring lock │ unsupported record     │ right gateway / key
 verify     │ retryable=false in   │ unit test: missing    │ --dump-config exits 0  │ wsl_agent returns text
            │ seconds              │ parent still LOCKED   │                        │
```

## Fast triage (symptom -> cause -> action)

| Symptom | Most likely cause | Action |
|---|---|---|
| `wsl_agent` hangs ~120s then reports `connection closed before reply` / socket reset | `SdkRuntime` never notices the runtime **exiting mid-turn**, so `turnDone` never resolves and the daemon waits for socket idle timeout (120s) | Check daemon.log for `runtime exited (exit=1) => discard`; fix sdk-runtime to race `this.exited` into the prompt race (F1) |
| `wsl_daemon start` waits 45s and reports the start lock held by another host | State directory `<wslHome>/.dsh/remote-wsl` does not exist, so the lock's `mkdir "$d"` always fails on a missing parent (chicken-and-egg: the directory is created by launchDaemon *after* the lock is taken) | In `acquireEnsureLockScript`, run `mkdir -p "$(dirname "$d")"` (umask 077) before taking the lock; or pre-create the directory (F2) |
| runtime `startup failed: 1 required plugin did not activate` ... `credentials ... unknown kind "password"` | `~/.dsh/.credentials.yaml` contains a `kind` that dsh 0.2.2 does not recognise (only `api-key` / `grant`) | After backing up, delete/move that record; verify with `--dump-config` exiting 0 (F3) |
| `MISSING_CREDENTIAL` / `AUTH 401 ... api key invalid` | Provider and key do not match (default `deepseek-official` has no valid key; this machine actually goes through the Magpie gateway) | Point at the actual gateway (`MAGPIE_GATEWAY_KEY` + `llm-pi-ai`), or put a valid `DEEPSEEK_API_KEY` in place (F4) |
| `wsl_exec` occasionally reports `bash: /tmp/dsh-rwsl-<winpid>-*.sh: No such file or directory` | The one-shot launcher script was concurrently cleaned up / the cancellation took effect | Retry; investigate only if it keeps happening (F5) |

## Key paths and commands

- Plugin source (the copy actually running): `D:\project\dsh1\dsh-remote-wsl` (inside WSL: `/mnt/d/project/dsh1/dsh-remote-wsl`)
- Daemon state directory: `<wslHome>/.dsh/remote-wsl/` -> `daemon.log`, `launch-stderr.log`, `daemon.<slot>.json`, `daemon.<slot>.token`
- dsh startup diagnostics: `~/.dsh/logs/startup-*.log`
- Processes / services: `ps -eo pid,etime,cmd | grep daemon.ts`; `systemctl --user status dsh-rwsl-<port>.service`; `ss -tn | grep <port>`
- Credentials: `$DSH_HOME/.credentials.yaml` (default `~/.dsh/.credentials.yaml`); the only valid kinds are `api-key` / `grant`
- Runtime: `mise exec -- pnpm dlx @deepseek-ai/dsh@<ver> --profile sdk`; dlx cache at `~/.cache/pnpm/dlx`; **does not rely on a global dsh**
- One-shot evidence collection: `scripts/collect-diagnostics.sh` (copy it into WSL and run with `bash`)

## Verify and apply

- Unit tests (WSL): `cd /mnt/d/project/dsh1/dsh-remote-wsl && node --experimental-strip-types --test test/xxx.test.ts`
- Syntax: `node --experimental-strip-types scripts/check-syntax.ts`
- Daemon-side restart: `wsl_daemon action=restart` (`daemon.ts` / `sdk-runtime.ts` changes take effect immediately)
- Host-side changes (`daemon-protocol.ts` / `daemon-lifecycle.ts` / `register-tools.ts`) require **restarting DSH Desktop**
- Acceptance: after the fix, `wsl_agent` must return the real cause **within seconds** (`retryable=false` + exit code + stderr), not a socket error after 120s

## Discipline

- Do not blindly run `wsl_daemon stop all` (it kills healthy daemons that hold live sessions); confirm identity with `status` / a process scan first.
- Always back up `.credentials.yaml` (it contains secrets) before editing; delete only the records dsh rejected, never valid refs/records.
- With DSH Desktop, WSL only needs the **sdk capability** (`--profile sdk` = dsh-base + dsh-sdk-app); global dsh / web / tui are optional.

Full root causes, log evidence and commands: `references/failure-modes.md`.
