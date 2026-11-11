#!/usr/bin/env bash
# check-availability.sh — 产品命名平台可用性核验（只报状态，不替用户下结论）
# 用法: bash check-availability.sh <name> [domain npm github pypi crates rubygems wp telegram ...]
# 依赖: curl（必需）；whois（可选）。Windows 请在 WSL / Git Bash 下运行。
# 说明: 结果仅供参考；域名注册状态以注册商为准，商标/法律判断请交专业人士。
set -uo pipefail

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "用法: bash check-availability.sh <name> [domain npm github pypi crates rubygems wp telegram]"
  exit 2
fi
shift || true
PLATFORMS="${*:-domain npm github pypi}"

have() { command -v "$1" >/dev/null 2>&1; }
http_code() { curl -s -o /dev/null -w "%{http_code}" --max-time 12 "$1" 2>/dev/null || echo "ERR"; }

hr() { printf '%s\n' "------------------------------------------------------------"; }
echo "命名可用性核验: $NAME"
echo "平台: $PLATFORMS"
hr

for p in $PLATFORMS; do
  case "$p" in
    domain)
      for tld in com dev io app co; do
        d="$NAME.$tld"
        if have whois; then
          out="$(whois "$d" 2>/dev/null || true)"
          if echo "$out" | grep -qiE "no match|not found|no data found|available|no entries found"; then
            echo "  domain   $d : 可能可用 (whois)"
          elif [ -n "$out" ]; then
            echo "  domain   $d : 疑似已注册 (whois)"
          else
            echo "  domain   $d : whois 无响应，跳过"
          fi
        else
          code="$(http_code "https://$d")"
          if [ "$code" = "000" ] || [ "$code" = "ERR" ]; then
            echo "  domain   $d : 无站点响应（不代表未注册，仅提示）"
          else
            echo "  domain   $d : HTTP $code（可能已有站点）"
          fi
        fi
      done
      ;;
    npm)
      if have npm; then
        if npm view "$NAME" version >/dev/null 2>&1; then echo "  npm      $NAME : 已占用"; else echo "  npm      $NAME : 可能可用"; fi
      else echo "  npm      $NAME : 跳过（无 npm）"; fi
      ;;
    pypi)
      code="$(http_code "https://pypi.org/project/$NAME/")"
      if [ "$code" = "404" ]; then echo "  pypi     $NAME : 可能可用 (404)"; else echo "  pypi     $NAME : 已占用/异常 (HTTP $code)"; fi
      ;;
    crates)
      code="$(http_code "https://crates.io/api/v1/crates/$NAME")"
      if [ "$code" = "404" ]; then echo "  crates   $NAME : 可能可用 (404)"; else echo "  crates   $NAME : 已占用/异常 (HTTP $code)"; fi
      ;;
    rubygems)
      code="$(http_code "https://rubygems.org/api/v1/gems/$NAME.json")"
      if [ "$code" = "404" ]; then echo "  rubygems $NAME : 可能可用 (404)"; else echo "  rubygems $NAME : 已占用/异常 (HTTP $code)"; fi
      ;;
    github)
      code="$(http_code "https://github.com/$NAME")"
      if [ "$code" = "404" ]; then echo "  github   $NAME : 可能可用 (404)"; else echo "  github   $NAME : 已占用/异常 (HTTP $code)"; fi
      ;;
    wp)
      resp="$(curl -s --max-time 12 "https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&slug=$NAME" 2>/dev/null || true)"
      if echo "$resp" | grep -qi "plugin not found"; then echo "  wp-slug  $NAME : 可能可用"; else echo "  wp-slug  $NAME : 已占用/异常"; fi
      ;;
    telegram)
      code="$(http_code "https://t.me/$NAME")"
      if [ "$code" = "404" ]; then echo "  telegram $NAME : 可能可用 (404)"; else echo "  telegram $NAME : 已占用/异常 (HTTP $code)"; fi
      ;;
    *)
      echo "  ??       $p : 未知平台，跳过"
      ;;
  esac
done

hr
echo "注意: 字典常见词精确 .com 基本被占；可用时优先看 get${NAME}/use${NAME} 变体与 .sh/.site。"
echo "竞品冲突一定先于域名/平台检查（web 搜 \"$NAME\" <品类>）。商标/法律请交专业人士。"
