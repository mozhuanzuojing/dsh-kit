#!/usr/bin/env python3
"""check-cross-layer.py — 跨层命名一致性检查（API / DB / 事件 / 指标 / 配置）。

解决 `api-naming.md` §5 留下的缺口：跨层概念表此前只是模板，没有检查器。

三个子命令：
  init    生成一份 `docs/naming-map.md` 骨架（含表格头与示例行）
  check   校验概念表本身：三宗跨层陷阱 + 表格结构
  audit   把代码里的标识符与概念表对照，报"表里没有的名字"

三条被机器化的陷阱（来自 `api-naming.md` §0，全部有官方出处）：
  T1 is_prefix_conflict   API 字段用 `disabled`（AIP-140 禁 `is`）而 DB 列用 `is_disabled`（GitLab 要求 `is_`）
                          —— 同一行里两者并存是**允许**的（要求显式映射）；同一层内混用才是问题。
  T2 tense_conflict       API 侧用过去式（`published_time`）——AIP-142 明确禁止
  T3 total_conflict       同一指标既要求 `_total` 又不加（Prometheus vs OTel），同一行必须写清两套名
  T4 unit_missing         数量/时长类字段没有单位后缀（`timeout` vs `timeout_ms`）
  T5 name_as_person       `name` 被用作人名（AIP-122 禁止）

用法:
  python check-cross-layer.py init  --out docs/naming-map.md
  python check-cross-layer.py check --map docs/naming-map.md [--json] [--strict]
  python check-cross-layer.py audit --map docs/naming-map.md --code path/to/src

退出码：0 正常；--strict 且有 Critical/Major 时 1；参数错误 2。
依赖：`_common.py`（同目录）。
"""
import argparse
import json
import os
import re
import sys
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import atomic_write  # noqa: E402

SEV = {"Critical": 0, "Major": 1, "Minor": 2}

TEMPLATE = """# 跨层概念名注册表（naming-map）

> 唯一真源：同一业务概念在五层里的名字只在这里定义；代码/DDL/指标定义从这里生成或校验。
> 由 `check-cross-layer.py init` 生成，`check-cross-layer.py check` 校验。
> 规则与三宗陷阱见技能 `references/api-naming.md` §0 与 §5.5。

| 概念 | API 字段 | DB 列 | 事件属性 | 指标/属性 | 配置 key | 备注 |
|---|---|---|---|---|---|---|
| 创建时间 | create_time | created_at | time | — | — | 时态差异是刻意的：AIP 禁过去式 |
| 资源标识 | name | id | subject | — | — | name 是资源路径，id 是主键 |
| 布尔状态 | disabled | is_disabled | enabled | — | FEATURE_X_ENABLED | AIP 禁 is_，GitLab 要求 is_ |
| 超时 | timeout | timeout_ms | duration | — | TIMEOUT_MS | API 用 Duration 类型不带单位；DB/配置必须带 |
"""


def parse_map(path):
    """解析 markdown 表格 → [{row_no, concept, api, db, event, metric, config, note}]。"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()

    header = None
    rows = []
    in_table = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            header = cells
            in_table = True
            continue
        if re.fullmatch(r"[-:\s|]+", stripped):
            continue
        if len(cells) < 6:
            rows.append(dict(row_no=i, malformed=cells))
            continue
        rows.append(dict(row_no=i, concept=cells[0], api=cells[1], db=cells[2],
                         event=cells[3], metric=cells[4], config=cells[5],
                         note=(cells[6] if len(cells) > 6 else "")))
    return header, rows


def _clean(cell):
    if not cell:
        return ""
    c = cell.strip().strip("`")
    return "" if c in ("—", "-", "–", "") else c


def check_map(header, rows):
    findings = []

    def add(rule, sev, row_no, where, msg):
        findings.append(dict(row=row_no, layer=where, rule=rule, severity=sev, message=msg))

    if not header:
        add("no_table", "Critical", 0, "-", "找不到 markdown 表格；请先跑 `init`")
        return findings

    expect = ["概念", "API", "DB", "事件", "指标", "配置"]
    for i, key in enumerate(expect):
        if i >= len(header) or key not in header[i]:
            add("table_header", "Major", 0, "-", f"第 {i + 1} 列表头应含“{key}”，实际是“{header[i] if i < len(header) else '缺失'}”")

    for r in rows:
        n = r["row_no"]
        if "malformed" in r:
            add("row_malformed", "Critical", n, "-", f"列数不足 6：{r['malformed']}")
            continue

        api, db, ev, mt, cf = (_clean(r[k]) for k in ("api", "db", "event", "metric", "config"))
        concept = r["concept"]

        # T1 同一层内 is 前缀混用（API 层禁 is_；DB 层要求 is_）
        if api.startswith("is_"):
            add("is_prefix_conflict", "Major", n, "api",
                f"API 字段 `{api}` 带 is_ 前缀——AIP-140 要求布尔省略 is（`disabled`）")
        if db and not db.startswith(("is_", "has_", "does_")) and _looks_boolean(concept):
            add("is_prefix_conflict", "Minor", n, "db",
                f"DB 列 `{db}` 疑为布尔但缺 is_/has_ 前缀——GitLab SQL 指南要求布尔带前缀")

        # T2 时态：API 侧禁过去式
        if re.search(r"(published|created|updated|deleted|modified)_(time|at)$", api):
            add("tense_conflict", "Major", n, "api",
                f"API 字段 `{api}` 用了过去式——AIP-142 要求现在时（`publish_time`）")

        # T3 指标 _total：写了 Prom 名就必须有 OTel 对照
        if mt and "total" in mt.lower() and "—" not in (mt or "") and "otel" not in (r.get("note") or "").lower():
            add("total_conflict", "Minor", n, "metric",
                f"指标 `{mt}` 含 _total（Prometheus 要求）；OTel 侧应去掉，请在备注里写明两套名")

        # T4 单位：只对「度量量」（AIP-141）要求在名字里带单位；
        #     「时长」（AIP-142）用 Duration 类型表达，名字**不带**单位后缀，只在 DB/配置层才带。
        for where, val in (("api", api), ("db", db), ("config", cf)):
            if not val or _has_unit(val):
                continue
            is_time = bool(GENERIC_TIME_RE.search(val)) or _is_time_concept(concept)
            is_measure = _is_measure_concept(concept)
            if where == "api":
                if is_measure and not is_time:
                    add("unit_missing", "Minor", n, where,
                        f"`{val}` 是度量字段，AIP-141 要求单位写进名字（`distance_km`）")
                # 时长在 API 层用 google.protobuf.Duration，名字不带单位 —— 不报
            else:
                if is_time or is_measure:
                    add("unit_missing", "Minor", n, where,
                        f"`{val}` 疑为时长/度量但没有单位后缀（DB/配置层必须带：`timeout_ms`、`size_bytes`）")

        # T5 name 当人名（启发式：概念里出现"人"且字段是 name）
        if "name" in (api, db) and re.search(r"人|user.*name|person", concept, re.I):
            add("name_as_person", "Minor", n, "api/db",
                f"`name` 被用于人名语义——AIP-122 里 name 专指资源名")

    return findings


BOOLEAN_HINTS = ("布尔", "启用", "开关", "是否", "enabled", "disabled", "flag")
# 时长族（AIP-142 Duration）：API 层名字不带单位，DB/配置层带
TIME_HINTS = ("时长", "超时", "延迟", "间隔", "duration", "timeout", "latency", "interval", "ttl")
# 度量族（AIP-141 Quantities）：任何层都要求单位写进名字
MEASURE_HINTS = ("大小", "容量", "距离", "重量", "带宽", "吞吐", "size", "capacity", "distance",
                 "weight", "throughput", "bandwidth")
UNIT_RE = re.compile(r"_(ms|sec|secs|s|us|ns|min|h|bytes|kb|mb|gb|km|m|cm|kg|g|mbps|rps|qps|pct)$", re.I)
GENERIC_TIME_RE = re.compile(r"(timeout|duration|latency|interval|delay|ttl)$", re.I)


def _looks_boolean(concept):
    return any(h in concept.lower() for h in BOOLEAN_HINTS)


def _is_time_concept(concept):
    return any(h in concept.lower() for h in TIME_HINTS)


def _is_measure_concept(concept):
    return any(h in concept.lower() for h in MEASURE_HINTS)


def _has_unit(value):
    return bool(UNIT_RE.search(value))


IDENT_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+|[a-z]+[A-Z][A-Za-z0-9]*)\b")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "target", "__pycache__", ".venv", "vendor"}
# schema 源（跨层名字真正被定义的地方）——默认就扫
SCHEMA_EXT = {".proto", ".sql", ".graphql", ".avsc"}
# 普通源码——默认不扫（局部变量噪声太大），需要时 --include-code
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".cs", ".rb", ".rs", ".kt"}


def audit_code(map_path, code_root, include_code=False):
    exts = SCHEMA_EXT | (CODE_EXT if include_code else set())
    _, rows = parse_map(map_path)
    known = set()
    for r in rows:
        if "malformed" in r:
            continue
        for k in ("api", "db", "event", "metric", "config"):
            v = _clean(r[k])
            if v:
                known.add(v.lower())
                known.add(re.sub(r"[^a-z0-9]", "", v.lower()))

    findings = []
    seen = {}
    for dirpath, dirs, files in os.walk(code_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in exts:
                continue
            path = os.path.join(dirpath, fn)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    for m in IDENT_RE.finditer(line):
                        name = m.group(1)
                        key = re.sub(r"[^a-z0-9]", "", name.lower())
                        if key in known or name.lower() in known:
                            continue
                        if len(key) < 6:
                            continue
                        seen.setdefault(key, (path, i, name))
    for key, (path, line, name) in seen.items():
        findings.append(dict(file=path, line=line, layer="code", rule="unmapped_identifier",
                             severity="Minor",
                             message=f"`{name}` 不在概念表里；若是跨层概念，先入表再写代码"))
    return findings


def main():
    ap = argparse.ArgumentParser(description="跨层命名一致性检查")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="生成概念表骨架")
    p_init.add_argument("--out", default="docs/naming-map.md")
    p_init.add_argument("--force", action="store_true")

    for name in ("check", "audit"):
        p = sub.add_parser(name)
        p.add_argument("--map", default="docs/naming-map.md")
        p.add_argument("--json", action="store_true")
        p.add_argument("--strict", action="store_true")
        p.add_argument("--quiet", action="store_true")
        p.add_argument("--out", default=None)
        if name == "audit":
            p.add_argument("--code", required=True)
            p.add_argument("--include-code", action="store_true",
                           help="连普通源码一起扫（默认只扫 .proto/.sql 等 schema 源，避免局部变量噪声）")

    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.cmd == "init":
        if os.path.exists(args.out) and not args.force:
            print(f"[error] {args.out} 已存在；要覆盖请加 --force", file=sys.stderr)
            return 2
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        atomic_write(args.out, TEMPLATE)
        print(f"已生成骨架：{args.out}")
        return 0

    if not os.path.isfile(args.map):
        print(f"[error] 找不到概念表 {args.map}；先跑 `init`", file=sys.stderr)
        return 2

    header, rows = parse_map(args.map)
    findings = check_map(header, rows)
    if args.cmd == "audit":
        findings.extend(audit_code(args.map, args.code, args.include_code))

    findings.sort(key=lambda f: (SEV.get(f["severity"], 9), str(f.get("file", "")), f.get("line", f.get("row", 0))))
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    if args.json:
        text = json.dumps(dict(concepts=len(rows), counts=counts, findings=findings),
                          ensure_ascii=False, indent=2)
    elif not args.quiet:
        lines = [f"概念表 {args.map}：{len(rows)} 行；问题 "
                 f"Critical={counts.get('Critical', 0)} Major={counts.get('Major', 0)} "
                 f"Minor={counts.get('Minor', 0)}", "-" * 70]
        for f in findings:
            loc = f"{f.get('file')}:{f.get('line')}" if f.get("file") else f"row {f.get('row')}"
            lines.append(f"  [{f['severity']}] {loc} ({f['layer']}) <{f['rule']}> — {f['message']}")
        if not findings:
            lines.append("未发现跨层命名问题（三宗陷阱均已显式处理）。")
        text = "\n".join(lines)
    else:
        text = ""

    if args.out:
        atomic_write(args.out, text + "\n")
    elif text:
        print(text)

    if args.strict and (counts.get("Critical", 0) or counts.get("Major", 0)):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
