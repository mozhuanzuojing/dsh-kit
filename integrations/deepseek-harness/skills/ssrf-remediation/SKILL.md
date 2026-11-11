---
name: ssrf-remediation
description: "Fix and audit server-side request forgery (SSRF) in any endpoint that fetches a user-supplied URL (urlPath/url/redirect/import-from-URL/webhook). Explains why string-prefix (startsWith) checks and blacklists fail (@-userinfo, domain-suffix, param desync, redirect, private IP) and gives the safe design: parse → exact host:port allowlist → loopback/link-local hard-block → per-hop redirect validation; reuse existing config (no new param). Includes a reproducible bypass test harness. Triggers when the user mentions SSRF, 服务器端请求伪造, 内网探测, getCorsFile, urlPath 校验, URL 白名单/前缀校验, server-side URL fetch, or an SSRF vulnerability report."
---

# SSRF Remediation

Validate at the **sink** (where the outbound request is actually made), not only in an upstream filter.

## When to activate
- An endpoint takes a URL and the **server fetches it** (file preview, image proxy, "import from URL", webhook tester, URL→PDF, `getCorsFile`, `onlinePreview`).
- A vuln report names: 未授权访问 + SSRF, `urlPath` 未校验, 内网探测, 服务器端请求伪造.
- You see a "URL whitelist" implemented as `startsWith` / `contains` / regex on the raw string.

## Golden rules
1. **Sink-level, same param.** Validate on the exact parameter you will fetch. A filter that reads `url` while the controller fetches `urlPath` is bypassable (param desync).
2. **Exact host, not string prefix.** Parse the URL; take the host **after the last `@`** (userinfo); match `host` (and port) **exactly** against an allowlist. `http://allowed@internal` and `http://allowed.evil.com` defeat `startsWith`.
3. **Always block loopback/link-local.** Regardless of allowlist, reject `127/8, ::1, 169.254/16 (cloud metadata), fe80::/10, 0.0.0.0, multicast`. Then re-validate **every redirect hop** (or disable redirects). `@`-in-URL and 302 are the two most common escapes.

## Bypass patterns a "looks safe" check misses
| Sloppy check | Bypass |
|---|---|
| `decodedUrl.startsWith(prefix)` on whole URL | `http://allowed@169.254.169.254/`, `http://allowed.evil.com/` |
| filter reads one param, handler fetches another | `?url=<benign>&urlPath=<internal>` |
| default HTTP client follows 3xx | allowed host returns `302 → http://internal` |
| only domain allowlist, no IP check | allowlisted host that resolves to a private IP (DNS rebinding) |
| allowlist entry `host` (no port) treated as any port | `http://host:22/` (port scan / non-HTTP services) |

## Correct design (in order)
1. Parse URL (galimatias / `URI`); get scheme + host (after `userinfo@`) + effective port.
2. Scheme allowlist (http/https; keep ftp only if the product needs it).
3. **Exact `host:port` allowlist** — derive from existing config when possible (e.g. parse existing `url.allowed.prefix`); prefer **zero new config param**.
4. Resolve host → reject if any IP is loopback/link-local/any-local/multicast.
5. No allowlist configured → also reject private/reserved (`10/8,172.16/12,192.168/16,100.64/10,fc00::/7,240/4`).
6. Redirects: subclass `DefaultRedirectStrategy` to re-validate each `Location`, or disable redirect-following.
7. Return the validated URL; the caller fetches that exact object.

> Do **not** blanket-reject `userinfo` — host is taken after `@`, so it's not a bypass, and rejecting it breaks legit `ftp://user:pass@` / HTTP basic-auth. It is redundant with rule 2.

## Verification (reproducible)
- Compile with the project's **required JDK** (watch maven-enforcer, e.g. kkFileView needs JDK8).
- Run a small harness with the real URL lib in use; assert **REJECT** for: PoC host, `@internal`, `allowed.evil.com`, cloud metadata, private IP, `bare-host:other-port`, `302→internal`; assert **ALLOW** for: the real allowlisted internal file server and domain.
- Keep the PASS/FAIL matrix in the delivery doc as evidence.

## Review checklist (遗漏 / 冗余 / 因果颠倒)
- 遗漏: same-class unauthenticated entry (`onlinePreview`) + auth bypass flags (`modCode=CIM`); DNS rebinding; ftp creds.
- 冗余: userinfo reject (covered by host check); dead `try/catch`; unused imports.
- 因果: "config file still has old key" ≠ "old jar"; external props are independent of jar version — verify the actual artifact.

## References
- `reference/playbook.md` — Java implementation skeleton (`UrlSecurityValidator`, `SsrfSafeRedirectStrategy`), config derivation, code layout (algorithm first, helpers last).
- `reference/case-kkfileview-getcorsfile.md` — full worked case: bypass matrix results, files changed, residual risks.
