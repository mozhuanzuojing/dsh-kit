# Case Study — kkFileView `/getCorsFile` 未授权 SSRF (漏洞编号 614623)

Real hotfix worked end-to-end; use as a template.

## Context
- Asset: `https://cwxt.cqcivc.edu.cn:8188/kkFileView/getCorsFile` (kkFileView file-preview service).
- Report type: 未授权访问 + SSRF; `urlPath` 未做来源与目标校验（Base64 可构造任意地址，服务器主动请求）。
- PoC: `GET /kkFileView/getCorsFile?urlPath=aHR0cDovLzEyNy4wLjAuMTo4MTg4` → `http://127.0.0.1:8188`.
- Codebase: legacy Spring MVC, packaged as WAR, **must compile on JDK8** (maven-enforcer rejects 11+).

## Root cause (why "patch + config" still vulnerable)
`UrlPrefixSecurityFilter` (also gating `getCorsFile`) validated `decodedUrl.startsWith(prefix)` — a **whole-string** prefix check — while the controller fetched the galimatias-parsed URL. Multiple escapes:
- `@`-userinfo: `http://<allowed>:8188@127.0.0.1:8188/` → string starts with allowed, real host = `127.0.0.1`.
- domain suffix: `https://cwxt...edu.cn.attacker.com/`.
- **param desync**: filter's `WebUtils.getSourceUrl` reads `url`/`currentUrl` first, controller consumes `urlPath` → send benign `url` + malicious `urlPath`.
- follows 3xx (`DefaultRedirectStrategy`) → allowlisted host 302s to internal.
- no private-IP check; and the field allowlist literally contained `http://127.0.0.1:8188` and `http://172.24.100.39:8188`.
Also `getCorsFile` was **not** in `TokenValidationFilter`'s path list → unauthenticated.

## Bypass matrix (old filter vs new validator, galimatias-verified)
| Input (decoded urlPath) | old `startsWith` | new validator | actual host |
|---|---|---|---|
| `http://127.0.0.1:8188` (PoC) | pass | **REJECT** (loopback) | 127.0.0.1 |
| `http://172.24.100.39:8188@127.0.0.1:8188/` | pass | **REJECT** (loopback) | 127.0.0.1 |
| `http://127.0.0.1:8188@172.24.100.39:8188/` | pass | **ALLOW** (reaches authorized host only) | 172.24.100.39 |
| `https://cwxt.cqcivc.edu.cn.attacker.com/` | pass | **REJECT** | attacker.com |
| `http://169.254.169.254/latest/meta-data/` | pass | **REJECT** | link-local |
| `http://cwxt.cqcivc.edu.cn:22/` | pass | **REJECT** (port) | cwxt:22 |
| `ftp://user:pass@172.24.100.39:8188/x` | pass | **ALLOW** (creds kept) | 172.24.100.39 |

## Files changed (minimal, zero new config param)
- **new** `utils/UrlSecurityValidator.java` — ordered algorithm + helpers (see playbook).
- **new** `utils/SsrfSafeRedirectStrategy.java` — per-hop redirect validation.
- **edit** `web/controller/OnlinePreviewController.java` — in `getCorsFile`: `url = UrlSecurityValidator.validate(urlPath)` → 403 on fail; use `SsrfSafeRedirectStrategy`; removed dead try/catch + unused imports. (~+14/−? lines.)
- `ConfigConstants.java` / `application.properties` **unchanged** (validator reuses `url.allowed.prefix`).

## Verification
- `JAVA_HOME=<jdk8> ./mvnw -o -DskipTests clean compile` → BUILD SUCCESS.
- Behavioral harness with real `galimatias-0.2.1` + `icu4j`: assert REJECT for PoC/@/suffix/metadata/private/`bare:other-port`; ALLOW for real internal file server. Keep the matrix as evidence.

## Field-config action
- Remove `http://127.0.0.1:8188` from `url.allowed.prefix` (it's the **local U8 gateway** `u8_url=http://127.0.0.1:8188`; Redis also on `127.0.0.1:6379` → juiciest pivot). Keep real file host `172.24.100.39:8188`.
- `url.check.path` is **not read by current code** — a leftover in the external props; **presence of a key ≠ jar version** (packaging ships a dated sample, external props persist).
- If a legit preview genuinely needs loopback files, do NOT whitelist all loopback; use a path-scoped allow (e.g. only GET `http://127.0.0.1:8188/U8CloudFile/**`, still block `/pubgy/**`, `/kkFileView/**`).

## Residual / same-class (log as separate tickets)
1. **`/onlinePreview` is a same-class unauthenticated SSRF**: also fetches `url` server-side; `TokenValidationFilter` skips auth when `modCode=CIM`; `UrlPrefixSecurityFilter` still startsWith. Fix: reuse `UrlSecurityValidator` on decoded `url` (special-case `file://` via local-dir allowlist) + fix `modCode=CIM` bypass.
2. **DNS rebinding**: validation resolves DNS but the subsequent connect may re-resolve; pin the validated IP or accept the residual (non-allowlisted hosts are already blocked, loopback hard-blocked).
3. **Unauthenticated fetch remains** for allowlisted hosts (frontend `kkPreviewUrl.js` calls `getCorsFile?urlPath=` without token); bounded by the host allowlist.
