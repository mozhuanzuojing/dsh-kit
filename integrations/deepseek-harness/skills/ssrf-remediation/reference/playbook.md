# SSRF Remediation — Implementation Playbook

Language-agnostic rules + a Java reference implementation (Spring MVC / Apache HttpClient), distilled from a real kkFileView `getCorsFile` hotfix.

## 1. The one algorithm (read top-to-bottom)

```
validate(rawUrl):
  ① empty  -> reject
  ② parse  -> scheme / userinfo / host(after @) / port / path   (galimatias URL.parse or java.net.URI)
  ③ scheme must be in {http, https (+ftp if needed)}
  ④ host = host after the last '@'; port = explicit or scheme default
  ⑤ if allowlist configured: host:port must EXACTLY match (no prefix, no any-port)
  ⑥ resolve host -> InetAddress[]:
       6.1 reject if any isLoopback / isLinkLocal / isAnyLocal / isMulticast   (ALWAYS, even if allowlisted)
       6.2 if no allowlist: also reject private/reserved ranges
  ⑦ return java.net.URL(validated)  // caller fetches THIS object
```

Keep this as **one method at the top of the class**; put helpers at the bottom. A reviewer should understand the whole rule from this method alone.

## 2. Java skeleton — `UrlSecurityValidator`

```java
public static URL validate(String rawUrl) {
    if (rawUrl == null || rawUrl.trim().isEmpty()) return reject(rawUrl, "empty url");

    io.mola.galimatias.URL g;
    try { g = io.mola.galimatias.URL.parse(rawUrl); }
    catch (GalimatiasParseException e) { return reject(rawUrl, "parse error"); }

    String scheme = g.scheme() == null ? "" : g.scheme().toLowerCase(Locale.ROOT);
    if (!ALLOWED_SCHEMES.contains(scheme)) return reject(rawUrl, "scheme");

    // host AFTER @ — userinfo does NOT change host; do not blanket-reject userinfo (breaks ftp/basic-auth)
    String host = g.host() == null ? "" : g.host().toString().toLowerCase(Locale.ROOT);
    if (host.startsWith("[") && host.endsWith("]")) host = host.substring(1, host.length() - 1);
    if (host.isEmpty()) return reject(rawUrl, "empty host");
    int port = g.port() < 0 ? g.defaultPort() : g.port();

    Set<String> allowed = effectiveAllowedHosts();               // derived from existing config
    if (!allowed.isEmpty() && !allowed.contains(host + ":" + port)) return reject(rawUrl, "host not in allowlist");

    InetAddress[] addrs;
    try { addrs = InetAddress.getAllByName(host); } catch (Exception e) { return reject(rawUrl, "dns"); }
    for (InetAddress a : addrs) if (isAlwaysBlocked(a)) return reject(rawUrl, "blocked: " + a);
    if (allowed.isEmpty()) for (InetAddress a : addrs)
        if (isPrivateOrReserved(a)) return reject(rawUrl, "private: " + a);

    try { return g.toJavaURL(); } catch (MalformedURLException e) { return reject(rawUrl, "to url"); }
}
```
Helpers (bottom): `reject`, `isAlwaysBlocked`, `isPrivateOrReserved`, `effectiveAllowedHosts`, `hostPortFromUrl`, `matchesAllowList` — see the reference case file for the full bodies.

`isAlwaysBlocked` = `isAnyLocalAddress || isLoopbackAddress || isLinkLocalAddress || isMulticastAddress`.
`isPrivateOrReserved` adds: `isSiteLocalAddress` (10/8,172.16/12,192.168/16), `0/8`, `100.64/10`, `169.254/16`, `192.0.2/24`, `198.18/15`, `198.51.100/24`, `203.0.113/24`, `240/4`, IPv6 `fc00::/7` (and `::ffff:a.b.c.d` unwrap).

## 3. Redirect handling (Java / Apache HttpClient 4.5)

```java
public class SsrfSafeRedirectStrategy extends DefaultRedirectStrategy {
    @Override public HttpUriRequest getRedirect(HttpRequest req, HttpResponse resp, HttpContext ctx)
            throws ProtocolException {
        URI loc = getLocationURI(req, resp, ctx);           // null => not a redirect
        if (loc == null) return super.getRedirect(req, resp, ctx);
        if (!UrlSecurityValidator.isAllowed(loc.toString()))
            throw new ProtocolException("blocked redirect target: " + loc);
        return super.getRedirect(req, resp, ctx);
    }
}
// wire: HttpClientBuilder.create().setRedirectStrategy(new SsrfSafeRedirectStrategy()).build()
```
If the product does not need redirects, simply disable redirect-following instead.

## 4. Zero-new-config allowlist derivation

When the product already has a URL-prefix config (e.g. `url.allowed.prefix = http://host:port,...`),
derive the host allowlist from it instead of adding a new key:

```java
for (String p : ConfigConstants.getUrlAllowedPrefixes()) {
    io.mola.galimatias.URL u = io.mola.galimatias.URL.parse(p);
    String h = u.host().toString().toLowerCase();
    int prt = u.port() > 0 ? u.port() : u.defaultPort();   // bare domain -> 80/443, not "any port"
    add(h + ":" + prt);
}
```
Field config then only needs the unsafe entry removed (e.g. delete `http://127.0.0.1:8188`); no migration.

## 5. Code layout preference (user request)

Main algorithm first, helpers last, with a visible separator and ①~⑦ step comments, so "看一个方法就明白". Example banner:

```
// ===== 主流程（算法 / 校验规则）—— 看这一个方法即可 =====
// ===== 工具方法（仅供主流程调用）=====
```

## 6. Non-obvious decisions
- **userinfo**: don't reject; take host after `@`. Blanket rejection is redundant and breaks `ftp://user:pass@`/basic-auth.
- **bare host = any port** is an SSRF widening; always compute `host:port` with scheme default port.
- **loopback hard-block even when allowlisted** — the allowlist authorizes *targets*, not *loopback*; metadata `169.254.169.254` and `127.0.0.1` must never be reachable.
- **resolve only after allowlist match** — avoids attacker-controlled DNS lookups for non-allowlisted hosts.
