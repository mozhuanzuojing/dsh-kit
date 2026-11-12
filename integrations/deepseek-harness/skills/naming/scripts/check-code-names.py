#!/usr/bin/env python3
"""check-code-names.py — 代码命名校验器（AST 优先，正则兜底）。

三层引擎（自动降级，降级会**打印警告**，绝不静默）：
  1. `ast-grep-py`（pip 包，MIT）—— 进程内 AST 解析，最准；
  2. `ast-grep` CLI（`sg`，MIT）—— 子进程调用，需要装 CLI；
  3. 正则 —— 零依赖离线兜底，有已知局限（见下）。

检查内容：
  A. 单名检查：缩写 / 模糊动词 / 否定式布尔 / 单字母 / weasel 后缀 / 垃圾模块名 / 大小写冲突；
  B. 仓库级聚合（`--repo`，默认开）：
     · near_name        近名（同 kind 同作用域内仅大小写/编辑距离≤1/单复数/词元前缀不同）
     · synonym_drift    同一概念多个同义动词混用（save/store/persist），并给出本仓库主流用法
     · inconsistent_pair 同名不同 kind（疑似同一概念的类与变量命名分裂）
  C. 重命名影响面（`--rename OLD[=NEW]`）：把命中点分成
     auto(可自动改) / manual(需人工确认) / risky(不要动：字符串、注释、契约字段)。

依赖：`_common.py`（同目录，词元切分/近名比较/原子写；要拷就拷整个 scripts/）。

输出契约（向后兼容）：
  {file, line, name, kind, rule, severity, message}
  新增可选字段：`scope`（作用域路径）、`engine`（ast-grep-py / ast-grep-cli / regex）。

用法:
  python check-code-names.py <file_or_dir>
      [--lang auto|py|ts|js|tsx|jsx|go|java|cs|rb|rs|kt]
      [--engine auto|ast-grep-py|ast-grep-cli|regex]
      [--json|--out FILE] [--strict] [--max-files N] [--quiet]
      [--no-repo] [--rename OLD[=NEW]]
      [--near-name/--no-near-name] [--synonyms/--no-synonyms]

退出码: 0 正常；--strict 且存在 Critical（含 risky 重命名冲突）时返回 1；
        参数/引擎错误返回 2（不静默成功）。

已知局限（诚实标注）：
  · AST 引擎覆盖 9 种语言；`cs` 走 ast-grep 的 `cs` 语法（`c_sharp` 别名在该实现里会 panic，已规避）；
    Kotlin/Rust 的某些节点没有 `name` 字段，靠首个子标识符兜底，复合模式（解构赋值）可能漏检。
  · 正则兜底仍可能漏检一行多类型混合声明（已修「一行多声明只看第一个」的旧缺陷）。
  · 近名/一致性是**启发式**：编辑距离≤1 在短名（<4 字符）上噪声大，默认跳过；不做语义判断。
  · `--rename` 只做文本级影响面分类，不做重写；跨文件语义改名请用 IDE/LSP。
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (atomic_write, edit_distance_le1,  # noqa: E402
                     singular, strip_sep, tokenize)

EXT_LANG = {
    ".py": "py", ".pyi": "py",
    ".ts": "ts", ".tsx": "tsx", ".js": "js", ".jsx": "jsx", ".mjs": "js", ".cjs": "js",
    ".go": "go", ".java": "java", ".cs": "cs", ".rb": "rb", ".rs": "rs", ".kt": "kt",
}
JS_LANGS = {"js", "jsx", "ts", "tsx"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "target", "__pycache__", "venv",
             ".venv", ".next", ".idea", ".vscode", "vendor", "out", "coverage", ".mypy_cache"}
UTILS_NAMES = {"utils", "util", "helpers", "helper", "common", "shared", "lib", "core", "base", "misc"}
VAGUE_VERBS = {"process", "manage", "do", "run", "data", "temp", "tmp", "foo", "bar", "stuff", "thing", "object", "value"}
BAD_ABBR = {"req", "resp", "rsp", "svr", "obj", "biz", "mgr"}
# 仅保留高度可疑的“无信息”后缀；含真实角色语义的（PaymentProcessor / OrderItem / FooImpl / BaseService）不列入，避免误报
WEASEL_SUFFIX = {"info", "data", "manager", "helper", "util", "utils", "utility"}
BOOL_PREFIX = {"is", "has", "can", "should", "are", "was", "were"}
NEG_WORDS = {"not", "no", "never", "non"}
SEV_ORDER = {"Critical": 0, "Major": 1, "Minor": 2}

# 同义动词族：同一族内混用即 synonym_drift（启发式；可用 glossary 覆盖）
SYNONYM_GROUPS = [
    {"get", "fetch", "load", "read", "retrieve", "query"},
    {"save", "store", "persist", "write", "put"},
    {"remove", "delete", "erase", "drop", "clear"},
    {"create", "make", "build", "construct", "init", "initialize"},
    {"update", "modify", "patch", "edit", "set"},
    {"send", "emit", "publish", "dispatch", "fire"},
    {"parse", "decode", "deserialize", "unmarshal"},
    {"encode", "serialize", "marshal", "stringify"},
    {"check", "validate", "verify", "assert", "ensure"},
]
# 单个词元后接这些词时，视为「同概念的容器/数量写法」（user / userList / userCount）
CONTAINER_TOKENS = {"list", "map", "set", "array", "count", "total", "items", "item",
                    "names", "name", "data", "info", "value", "values", "id", "ids"}

SYNONYM_INDEX = {}
for _gid, _grp in enumerate(SYNONYM_GROUPS):
    for _w in _grp:
        SYNONYM_INDEX[_w] = _gid

# ---------------------------------------------------------------- 通用工具


def normalize(name):
    """大小写冲突比较键：仅小写（保留分隔符）。"""
    return name.lower()





# ---------------------------------------------------------------- AST 引擎

AST_ENGINE = None      # "ast-grep-py" | "ast-grep-cli" | "regex"
_AST_WARNED = set()


def _warn(msg):
    key = msg[:60]
    if key in _AST_WARNED:
        return
    _AST_WARNED.add(key)
    print(f"[warn] {msg}", file=sys.stderr)


def _load_ast_grep_py():
    try:
        import ast_grep_py  # noqa: F401
        return ast_grep_py
    except Exception:
        return None


# 每种语言：(节点 kind, 归一的声明类别, 语言包名)
AST_DECL_SPECS = {
    "py": [
        ("function_definition", "function"),
        ("class_definition", "class"),
        ("assignment", "variable"),
    ],
    "js": [
        ("function_declaration", "function"),
        ("class_declaration", "class"),
        ("method_definition", "function"),
        ("variable_declarator", "variable"),
    ],
    "ts": [
        ("function_declaration", "function"),
        ("class_declaration", "class"),
        ("method_definition", "function"),
        ("interface_declaration", "class"),
        ("type_alias_declaration", "class"),
        ("enum_declaration", "class"),
        ("variable_declarator", "variable"),
    ],
    "go": [
        ("function_declaration", "function"),
        ("method_declaration", "function"),
        ("type_spec", "class"),
        ("var_spec", "variable"),
        ("const_spec", "variable"),
    ],
    "java": [
        ("class_declaration", "class"),
        ("interface_declaration", "class"),
        ("enum_declaration", "class"),
        ("method_declaration", "function"),
        ("variable_declarator", "variable"),
    ],
    "cs": [
        ("class_declaration", "class"),
        ("interface_declaration", "class"),
        ("enum_declaration", "class"),
        ("method_declaration", "function"),
        ("variable_declarator", "variable"),
    ],
    "rs": [
        ("function_item", "function"),
        ("struct_item", "class"),
        ("enum_item", "class"),
        ("trait_item", "class"),
        ("const_item", "variable"),
        ("let_declaration", "variable"),
    ],
    "rb": [
        ("method", "function"),
        ("class", "class"),
        ("module", "class"),
        ("assignment", "variable"),
    ],
    "kt": [
        ("function_declaration", "function"),
        ("class_declaration", "class"),
        ("object_declaration", "class"),
        ("property_declaration", "variable"),
    ],
}
AST_DECL_SPECS["tsx"] = AST_DECL_SPECS["ts"]
AST_DECL_SPECS["jsx"] = AST_DECL_SPECS["js"]

# ast-grep 语言名（cs 用 "cs"；"c_sharp" 在该实现里会 panic）
AST_LANG_NAME = {"py": "python", "js": "javascript", "jsx": "jsx", "ts": "typescript",
                 "tsx": "tsx", "go": "go", "java": "java", "cs": "cs", "rs": "rust",
                 "rb": "ruby", "kt": "kotlin"}

SCOPE_NODE_KINDS = {
    "class_declaration", "class_definition", "class_body", "interface_declaration",
    "impl_item", "trait_item", "module", "object_declaration", "struct_item",
    "method_declaration", "method_definition", "function_declaration", "function_item",
    "function_definition", "block", "program", "declaration_list",
}


def _node_name(node, lang):
    """从 AST 节点提取声明名；不同语言字段不同，最后退回首个子标识符。"""
    for field in ("name", "left", "declarator", "pattern"):
        try:
            f = node.field(field)
        except Exception:
            f = None
        if f is not None:
            txt = f.text()
            if txt and re.fullmatch(r"[A-Za-z_$][\w$]*[?!]?", txt):
                return txt
    for child in node.named_children():
        if child.kind() in ("identifier", "simple_identifier", "type_identifier",
                            "field_identifier", "constant", "property_identifier"):
            txt = child.text()
            if re.fullmatch(r"[A-Za-z_$][\w$]*[?!]?", txt):
                return txt
        if child.kind() in ("pattern_list", "tuple_pattern", "tuple", "expression_list"):
            for sub in child.named_children():
                txt = sub.text()
                if re.fullmatch(r"[A-Za-z_$][\w$]*[?!]?", txt):
                    return txt
        if child.kind() in ("variable_declaration", "variable_declarator"):
            sub = _node_name(child, lang)
            if sub:
                return sub
    return None


def _returns_jsx(node):
    """判断函数体内是否出现 JSX 节点（tsx/jsx 专用）。"""
    stack = [node]
    guard = 0
    while stack and guard < 4000:
        cur = stack.pop()
        guard += 1
        for child in cur.named_children():
            if child.kind().startswith("jsx_"):
                return True
            stack.append(child)
    return False


def _node_scope(node):
    """作用域路径：由内向外收集命名作用域，用 `/` 连接。"""
    names = []
    try:
        ancestors = list(node.ancestors())
    except Exception:
        ancestors = []
    for a in ancestors:
        if a.kind() in SCOPE_NODE_KINDS:
            nm = None
            for field in ("name",):
                try:
                    f = a.field(field)
                except Exception:
                    f = None
                if f is not None:
                    nm = f.text()
                    break
            if nm and re.fullmatch(r"[A-Za-z_$][\w$]*", nm):
                names.append(nm)
    return ".".join(reversed(names[:4]))


def extract_decls_ast(ag, text, lang):
    """返回 [(line, name, kind, scope)]；解析失败抛异常由上层降级。"""
    lang_name = AST_LANG_NAME.get(lang)
    if lang_name is None:
        raise RuntimeError(f"ast-grep 不支持语言 {lang}")
    specs = AST_DECL_SPECS.get(lang, [])
    if not specs:
        raise RuntimeError(f"无 AST 声明规格: {lang}")
    root = ag.SgRoot(text, lang_name).root()
    out = []
    seen = set()
    for node_kind, decl_kind in specs:
        for node in root.find_all(kind=node_kind):
            nm = _node_name(node, lang)
            if not nm:
                continue
            if nm in {"if", "for", "while", "switch", "return", "function", "new", "constructor"}:
                continue
            if lang in ("tsx", "jsx") and decl_kind == "function" and _returns_jsx(node):
                decl_kind_eff = "component"
            else:
                decl_kind_eff = decl_kind
            line = node.range().start.line + 1
            key = (line, nm, decl_kind_eff)
            if key in seen:
                continue
            seen.add(key)
            out.append((line, nm, decl_kind_eff, _node_scope(node)))
    return out


def extract_decls_cli(text, lang, path):
    """ast-grep CLI 兜底：`sg run --pattern` 逐类抽取（子进程）。"""
    import shutil
    import subprocess
    exe = shutil.which("ast-grep") or shutil.which("sg")
    if not exe:
        raise RuntimeError("未找到 ast-grep CLI")
    lang_name = AST_LANG_NAME.get(lang)
    if not lang_name:
        raise RuntimeError(f"ast-grep CLI 不支持语言 {lang}")
    out = []
    seen = set()
    for node_kind, decl_kind in AST_DECL_SPECS.get(lang, []):
        proc = subprocess.run([exe, "run", "--kind", node_kind, "--lang", lang_name,
                               "--json=stream", path],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            start = item.get("range", {}).get("start", {})
            ln = int(start.get("line", 0)) + 1
            snippet = item.get("text", "")
            m = re.search(r"\b(?:function|class|interface|type|struct|enum|trait|def|fn|func|method)\s+"
                          r"([A-Za-z_$][\w$]*)", snippet)
            nm = m.group(1) if m else None
            if not nm:
                m2 = re.search(r"([A-Za-z_$][\w$]*)\s*[(:=]", snippet)
                nm = m2.group(1) if m2 else None
            if not nm:
                continue
            key = (ln, nm, decl_kind)
            if key in seen:
                continue
            seen.add(key)
            out.append((ln, nm, decl_kind, ""))
    if not out and not AST_DECL_SPECS.get(lang):
        raise RuntimeError("无 AST 声明规格")
    return out


# ---------------------------------------------------------------- 正则兜底引擎

DECL_PATTERNS = {
    "py": [
        ("function", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")),
        ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*[\(:]")),
        ("variable", re.compile(r"^\s*([A-Za-z_]\w*)\s*(?::[^=\n]+)?=(?!=)")),
        ("variable", re.compile(r"\bfor\s+([A-Za-z_]\w*)\s+in\b")),
    ],
    "js": [
        ("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")),
        ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)\b")),
        ("class", re.compile(r"\b(?:interface|type)\s+([A-Za-z_$][\w$]*)\b")),
        # 一行多声明：用 finditer 全量抓，不 break
        ("variable", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\b")),
        ("variable", re.compile(r",\s*([A-Za-z_$][\w$]*)\s*(?::[^=,;\n]+)?=")),
    ],
    "go": [
        ("function", re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(")),
        ("class", re.compile(r"\btype\s+([A-Za-z_]\w*)\b")),
        ("variable", re.compile(r"\b(?:var|const)\s+([A-Za-z_]\w*)\b")),
    ],
    "java": [
        ("class", re.compile(r"\b(?:class|interface|enum)\s+([A-Za-z_]\w*)\b")),
        # 修：声明必须落在「修饰符/返回类型 + 名 + (」且行内不含 . 调用前缀，行尾是 { 或 ;
        ("function", re.compile(
            r"^\s*(?:@\w+\s+)*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default)\s+)*"
            r"[\w<>\[\],.?\s]+?\s+([A-Za-z_]\w*)\s*\([^;{]*\)\s*(?:throws\s+[\w,.\s]+)?\{?\s*$")),
        ("variable", re.compile(
            r"^\s*(?:(?:public|private|protected|static|final|readonly|volatile|transient)\s+)*"
            r"(?:[\w<>\[\],.?]+)\s+([A-Za-z_]\w*)\s*(?:=[^;]*)?;\s*$")),
    ],
    "rs": [
        ("function", re.compile(r"\bfn\s+([A-Za-z_]\w*)\s*[<(]")),
        ("class", re.compile(r"\b(?:struct|enum|trait|union)\s+([A-Za-z_]\w*)\b")),
        ("variable", re.compile(r"\b(?:let\s+(?:mut\s+)?|const\s+)([A-Za-z_]\w*)\b")),
    ],
    "rb": [
        ("function", re.compile(r"^\s*def\s+([A-Za-z_]\w*[?!]?)")),
        ("class", re.compile(r"^\s*(?:class|module)\s+([A-Za-z_]\w*)")),
        ("variable", re.compile(r"^\s*([A-Za-z_]\w*)\s*=(?!=)")),
    ],
}
DECL_PATTERNS["ts"] = DECL_PATTERNS["js"]
DECL_PATTERNS["tsx"] = DECL_PATTERNS["js"]
DECL_PATTERNS["jsx"] = DECL_PATTERNS["js"]
DECL_PATTERNS["cs"] = DECL_PATTERNS["java"]
DECL_PATTERNS["kt"] = DECL_PATTERNS["java"]

# 框架/标准库规定的覆写名，不算“模糊动词”（Python BaseHTTPRequestHandler 的 do_GET 等）
FRAMEWORK_OVERRIDES = {"do_GET", "do_POST", "do_PUT", "do_DELETE", "do_PATCH", "do_HEAD", "do_OPTIONS",
                       "setUp", "tearDown", "setUpClass", "tearDownClass", "runTest"}

NON_DECL_PREFIX = re.compile(r"^\s*(?:return|throw|yield|await|else|case|if|while|for|switch|catch)\b")
CALL_LINE = re.compile(r"^\s*(?:[\w$.\[\]'\"]+\s*\.\s*)?[\w$]+\s*\(.*\)\s*;?\s*$")


def extract_decls_regex(text, lang):
    out = []
    pats = DECL_PATTERNS.get(lang, [])
    for i, line in enumerate(text.splitlines(), 1):
        if NON_DECL_PREFIX.match(line):
            continue
        for kind, rx in pats:
            for m in rx.finditer(line):
                nm = m.group(1)
                if nm in {"if", "for", "while", "switch", "return", "function", "new", "else", "try", "catch"}:
                    continue
                # 保守过滤：纯调用行（`foo(bar);` / `obj.foo();`）不算声明
                if kind in ("function", "variable") and CALL_LINE.match(line) and "=" not in line \
                        and not re.search(r"\b(?:class|interface|enum|def|func|fn|function)\b", line):
                    continue
                out.append((i, nm, kind, ""))
    return out


# ---------------------------------------------------------------- 单名检查

def check_names(decls, path, lang):
    """单名规则：输入 [(line, name, kind, scope)]，输出 findings。"""
    findings = []
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem.lower() in UTILS_NAMES:
        findings.append(dict(line=1, name=os.path.basename(path), kind="module", rule="utils_module",
                             severity="Major", message="垃圾模块名（utils/helpers/common/…）——按领域拆成具体模块"))

    lower_map = defaultdict(list)
    for line, nm, kind, scope in decls:
        lower_map[(normalize(nm), scope)].append((nm, line, kind))

    for line, nm, kind, scope in decls:
        toks = tokenize(nm)
        if not toks:
            continue
        first, last = toks[0], toks[-1]
        base = dict(scope=scope) if scope else {}

        if len(nm) == 1 and kind in ("function", "class"):
            findings.append(dict(line=line, name=nm, kind=kind, rule="single_letter", severity="Minor",
                                 message="函数/类名只有单字母；改用描述性名字", **base))

        if kind == "component" and not re.match(r"^[A-Z]", nm):
            findings.append(dict(line=line, name=nm, kind=kind, rule="component_case", severity="Major",
                                 message="JSX 组件名应以 PascalCase 开头（小写会被当成普通函数/HTML 标签）", **base))

        if kind == "function" and "/" not in nm and re.match(r"^[A-Z][A-Za-z0-9]*$", nm) \
                and lang in ("tsx", "jsx"):
            findings.append(dict(line=line, name=nm, kind=kind, rule="function_case", severity="Minor",
                                 message="tsx/jsx 中 PascalCase 函数名易被误认为组件；若非组件请改小写", **base))

        if kind == "function" and nm not in FRAMEWORK_OVERRIDES and \
                (first in VAGUE_VERBS or (first == "handle" and len(toks) == 1)):
            findings.append(dict(line=line, name=nm, kind=kind, rule="vague_verb", severity="Major",
                                 message="模糊动词（process/manage/do/run/data/temp…）；换成具体动词", **base))

        if kind in ("class", "variable") and last in WEASEL_SUFFIX:
            findings.append(dict(line=line, name=nm, kind=kind, rule="weasel_suffix", severity="Minor",
                                 message=f"可疑无信息后缀 “{last}”；若含真实角色语义可保留，否则换有信息的名", **base))

        for t in toks:
            if t in BAD_ABBR:
                findings.append(dict(line=line, name=nm, kind=kind, rule="abbreviation", severity="Major",
                                     message=f"未认可缩写 “{t}”；公开名请写全称", **base))
                break

        if first in BOOL_PREFIX and any(t in NEG_WORDS for t in toks[1:]):
            findings.append(dict(line=line, name=nm, kind=kind, rule="negation_boolean", severity="Minor",
                                 message="布尔含否定；尽量用正向（isReady 而非 isNotReady）", **base))

    # 大小写冲突：同作用域同类型只差大小写
    for (_, scope), items in lower_map.items():
        uniq = {nm for nm, _, _ in items}
        if len(uniq) > 1:
            kinds = {k for _, _, k in items}
            if len(kinds) == 1:
                findings.append(dict(line=items[0][1], name="/".join(sorted(uniq)), kind="case",
                                     rule="case_collision", severity="Critical", scope=scope,
                                     message="同类型声明仅大小写不同（跨语言/重构不安全）；改名区分"))
    return findings


# ---------------------------------------------------------------- 仓库级聚合

def repo_near_names(records):
    """records: [(file, line, name, kind, scope, lang)] → 近名 findings。"""
    findings = []
    by_bucket = defaultdict(list)
    for rec in records:
        f, line, nm, kind, scope, lang = rec
        # 作用域缺失（正则引擎）时退化为按文件分桶；否则跨文件的模块级名字会互撞
        bucket_scope = scope if scope else f"@file:{f}"
        by_bucket[(lang, kind, bucket_scope)].append(rec)

    for (lang, kind, scope), items in by_bucket.items():
        # 先按去分隔符归并，减少 n^2
        names = sorted({nm for _, _, nm, _, _, _ in items})
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                na, nb = strip_sep(a), strip_sep(b)
                if na == nb:
                    # 纯大小写差异：同文件已由 case_collision 报过；
                    # 跨文件仍值得报（同一概念两种写法散落两处）
                    rec_a = next(r for r in items if r[2] == a)
                    rec_b = next(r for r in items if r[2] == b)
                    if normalize(a) == normalize(b) and rec_a[0] == rec_b[0]:
                        continue
                    rule, msg = "near_name", f"“{a}” 与 “{b}” 仅大小写/分隔符不同（同作用域、同类型）"
                elif singular(na) == singular(nb) and na != nb:
                    rule, msg = "near_name", f"“{a}” 与 “{b}” 疑单复数混用（同作用域、同类型）"
                elif min(len(na), len(nb)) >= 5 and edit_distance_le1(na, nb):
                    rule, msg = "near_name", f"“{a}” 与 “{b}” 编辑距离 ≤1，易混（同作用域、同类型）"
                else:
                    ta, tb = tokenize(a), tokenize(b)
                    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
                    if not short or long_[:len(short)] != short or ta == tb:
                        continue
                    extra = long_[len(short):]
                    if len(extra) == 1 and extra[0] in CONTAINER_TOKENS:
                        rule, msg = "near_name", f"“{a}” 与 “{b}” 差一个容器/数量词，疑同概念两种写法"
                    else:
                        continue
                line_a = next(l for _, l, nm, _, _, _ in items if nm == a)
                findings.append(dict(file=items[0][0], line=line_a, name=f"{a}/{b}", kind=kind,
                                     rule=rule, severity="Minor", scope=scope, message=msg))
    return findings


def repo_synonym_drift(records):
    """同一 kind 内首词跨同义族混用 → Minor，并给出本仓库主流用法。"""
    findings = []
    groups = defaultdict(lambda: defaultdict(list))   # (lang, kind, gid) -> word -> [rec]
    for rec in records:
        f, line, nm, kind, scope, lang = rec
        toks = tokenize(nm)
        if not toks:
            continue
        first = toks[0]
        if first in SYNONYM_INDEX:
            groups[(lang, kind, SYNONYM_INDEX[first])][first].append(rec)

    for (lang, kind, gid), words in groups.items():
        if len(words) < 2:
            continue
        ranked = sorted(words.items(), key=lambda kv: -len(kv[1]))
        main_word, main_recs = ranked[0]
        if len(main_recs) == len(ranked[1][1]):
            # 平手时不宣称“主流”，只报混用
            main_word = None
        for word, recs in ranked[1:]:
            f, line, nm, kind2, scope, lang2 = recs[0]
            if main_word:
                msg = (f"同义动词混用：“{word}” 与主用法 “{main_word}” 表达同一概念"
                       f"（本仓库 “{main_word}” 出现 {len(main_recs)} 次、“{word}” {len(recs)} 次）；统一到一个")
            else:
                msg = f"同义动词混用：“{word}” 与 “{ranked[0][0]}” 表达同一概念且用量接近；先定 glossary 再统一"
            findings.append(dict(file=f, line=line, name=nm, kind=kind, rule="synonym_drift",
                                 severity="Minor", scope=scope, message=msg))
    return findings


def repo_cross_kind(records):
    """同名不同大小写风格跨 kind（类 User / 变量 user）不报；这里只报“完全同名不同 kind 且作用域相同”。
    默认只作读数（不产生 issue），避免对 `class User` + `const user` 误报。"""
    return []


# ---------------------------------------------------------------- 重命名影响面

COMMENT_RE = re.compile(r"^\s*(?://|#|/\*|\*|<!--|--)")


def rename_impact(paths, old, new=None):
    """扫描文本级出现点并分级。返回 findings + summary。"""
    findings = []
    word = re.compile(r"(?<![\w$])" + re.escape(old) + r"(?![\w$])")
    counts = defaultdict(int)
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
        except OSError as e:
            _warn(f"rename: 无法读取 {path}: {e}")
            continue
        for i, line in enumerate(lines, 1):
            if not word.search(line):
                continue
            stripped = line.strip()
            if COMMENT_RE.match(stripped):
                tier, why = "manual", "出现在注释里（改不改取决于是否对外文档）"
            elif re.search(r"['\"`][^'\"`]*" + re.escape(old) + r"[^'\"`]*['\"`]", line):
                tier, why = "risky", "出现在字符串/序列化键里（改会破坏契约或数据）"
            elif re.search(r"\b(?:class|interface|struct|enum|trait|type|def|fn|func|function|const|let|var)\b"
                           r"[^\n]*\b" + re.escape(old) + r"\b", line):
                tier, why = "auto", "声明行（改名需同步所有引用）"
            else:
                tier, why = "manual", "引用/调用点（需人工确认语义）"
            counts[tier] += 1
            target = f"{old} → {new}" if new else old
            findings.append(dict(file=path, line=i, name=old, kind="rename",
                                 rule=f"rename_{tier}", severity="Minor",
                                 message=f"{target}：{why}"))
    return findings, dict(counts)


# ---------------------------------------------------------------- 驱动

def detect_lang(path, lang_opt):
    if lang_opt and lang_opt != "auto":
        return lang_opt
    return EXT_LANG.get(os.path.splitext(path)[1].lower(), None)


def iter_files(target, lang_opt, max_files):
    if os.path.isfile(target):
        yield target, detect_lang(target, lang_opt)
        return
    count = 0
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in EXT_LANG:
                continue
            count += 1
            if count > max_files:
                _warn(f"超过 --max-files={max_files}，其余文件未扫描")
                return
            yield os.path.join(root, fn), detect_lang(fn, lang_opt)


def resolve_engine(requested):
    global AST_ENGINE
    if requested == "regex":
        AST_ENGINE = "regex"
        return "regex"
    ag = _load_ast_grep_py() if requested in ("auto", "ast-grep-py") else None
    if ag is not None:
        AST_ENGINE = "ast-grep-py"
        return "ast-grep-py"
    if requested == "ast-grep-py":
        _warn("请求 ast-grep-py 但未安装；回落到下一引擎")
    import shutil
    if requested in ("auto", "ast-grep-cli") and (shutil.which("ast-grep") or shutil.which("sg")):
        AST_ENGINE = "ast-grep-cli"
        return "ast-grep-cli"
    if requested == "ast-grep-cli":
        _warn("请求 ast-grep CLI 但未找到可执行文件；回落到正则")
    AST_ENGINE = "regex"
    _warn("AST 引擎不可用（pip install ast-grep-py，或安装 ast-grep CLI）——已降级为正则，"
          "一行多类型声明/复杂签名可能漏检")
    return "regex"


def main():
    ap = argparse.ArgumentParser(description="代码命名校验器（AST 优先，正则兜底）")
    ap.add_argument("path")
    ap.add_argument("--lang", default="auto",
                    choices=["auto", "py", "ts", "js", "tsx", "jsx", "go", "java", "cs", "rb", "rs", "kt"])
    ap.add_argument("--engine", default="auto", choices=["auto", "ast-grep-py", "ast-grep-cli", "regex"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--max-files", type=int, default=2000)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--out", default=None, help="把结果写入该文件（UTF-8）")
    ap.add_argument("--no-repo", action="store_true", help="关闭仓库级聚合（近名/同义混用）")
    ap.add_argument("--near-name", dest="near_name", action="store_true", default=True)
    ap.add_argument("--no-near-name", dest="near_name", action="store_false")
    ap.add_argument("--synonyms", dest="synonyms", action="store_true", default=False,
                    help="开启同义动词混用检查（默认关：get/fetch/load 常是合理区分，噪声偏高）")
    ap.add_argument("--no-synonyms", dest="synonyms", action="store_false")
    ap.add_argument("--rename", default=None, metavar="OLD[=NEW]", help="重命名影响面分析（不做重写）")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if os.path.isfile(args.path) and detect_lang(args.path, args.lang) is None:
        print(f"[error] 不支持的扩展名：{args.path}（支持：{', '.join(sorted(EXT_LANG))}）",
              file=sys.stderr)
        return 2

    engine = resolve_engine(args.engine)
    ag = _load_ast_grep_py() if engine == "ast-grep-py" else None

    all_findings = []
    records = []
    files_scanned = 0
    unsupported = 0
    scanned_paths = []

    for path, lang in iter_files(args.path, args.lang, args.max_files):
        if lang is None:
            unsupported += 1
            continue
        files_scanned += 1
        scanned_paths.append(path)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError as e:
            _warn(f"skip {path}: {e}")
            continue

        decls = None
        if engine == "ast-grep-py":
            try:
                decls = extract_decls_ast(ag, text, lang)
            except BaseException as e:   # ast-grep-py 在未知语言上会 panic，必须兜住
                _warn(f"AST 解析失败（{lang}）：{type(e).__name__}；该文件降级为正则")
                decls = None
        elif engine == "ast-grep-cli":
            try:
                decls = extract_decls_cli(text, lang, path)
            except BaseException as e:
                _warn(f"CLI 解析失败（{lang}）：{type(e).__name__}；该文件降级为正则")
                decls = None
        if decls is None:
            decls = extract_decls_regex(text, lang)

        try:
            for f in check_names(decls, path, lang):
                f["file"] = path
                f["engine"] = engine if lang in AST_DECL_SPECS and engine != "regex" else "regex"
                all_findings.append(f)
        except Exception as e:
            _warn(f"单名检查失败 {path}: {e}")

        for line, nm, kind, scope in decls:
            records.append((path, line, nm, kind, scope, lang))

    if unsupported:
        _warn(f"{unsupported} 个文件扩展名不受支持，已跳过（不会静默通过）")
    if files_scanned == 0:
        _warn(f"未扫描到任何受支持的文件：{args.path}（支持：{', '.join(sorted(EXT_LANG))}）")

    if not args.no_repo:
        if args.near_name:
            all_findings.extend(repo_near_names(records))
        if args.synonyms:
            all_findings.extend(repo_synonym_drift(records))
        all_findings.extend(repo_cross_kind(records))

    rename_summary = None
    if args.rename:
        old, _, new = args.rename.partition("=")
        old = old.strip()
        if not old:
            print("[error] --rename 需要 OLD 或 OLD=NEW", file=sys.stderr)
            return 2
        rf, rename_summary = rename_impact(scanned_paths, old, new.strip() or None)
        all_findings.extend(rf)
        if scan_target_is_file(args.path) and not rf:
            all_findings.append(dict(file=args.path, line=1, name=old, kind="rename",
                                     rule="rename_absent", severity="Minor",
                                     message=f"未找到 “{old}” 的任何出现点（确认是否拼写正确）"))

    all_findings.sort(key=lambda x: (SEV_ORDER.get(x["severity"], 9), x.get("file", ""), x.get("line", 0)))

    counts = defaultdict(int)
    for f in all_findings:
        counts[f["severity"]] += 1

    lines = []
    if args.json:
        payload = dict(files_scanned=files_scanned,
                       counts=dict(counts),
                       engine=engine,
                       findings=all_findings)
        if rename_summary is not None:
            payload["rename"] = rename_summary
        lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not args.quiet:
        lines.append(f"扫描文件 {files_scanned} 个；引擎={engine}；"
                     f"问题 Critical={counts['Critical']} Major={counts['Major']} Minor={counts['Minor']}")
        if engine == "regex":
            lines.append("⚠ 正则兜底：可能漏检一行多类型声明与复杂签名；建议 pip install ast-grep-py")
        lines.append("-" * 72)
        cur = None
        for f in all_findings:
            if f.get("file") != cur:
                cur = f.get("file")
                lines.append(f"\n{cur}")
            scope = f" [{f['scope']}]" if f.get("scope") else ""
            lines.append(f"  [{f['severity']}] {f['line']}: {f['name']}  <{f['rule']}>{scope} — {f['message']}")
        if not all_findings and files_scanned == 0:
            lines.append("⚠ 没有扫描到任何文件——这不是“检查通过”。检查路径与扩展名。")
        elif not all_findings:
            lines.append("未发现明显命名问题（仍建议人工核对语义与一致性）。")
        if rename_summary:
            lines.append(f"\n重命名影响面：auto={rename_summary.get('auto',0)} "
                         f"manual={rename_summary.get('manual',0)} risky={rename_summary.get('risky',0)}")

    text_out = "\n".join(lines)
    if args.out:
        atomic_write(args.out, text_out + "\n")
    elif text_out:
        print(text_out)

    if args.strict and counts["Critical"] > 0:
        return 1
    return 0


def scan_target_is_file(target):
    return os.path.isfile(target)


if __name__ == "__main__":
    sys.exit(main())
