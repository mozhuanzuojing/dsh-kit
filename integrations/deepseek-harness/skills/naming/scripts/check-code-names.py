#!/usr/bin/env python3
"""check-code-names.py — 代码命名轻量校验器（纯标准库，跨语言）。

用途：扫描源码里的【声明名】（变量/函数/类/接口/常量）与文件名，按命名规则给出
Critical/Major/Minor 分级建议 + 文件:行号。它是「辅助草稿」，语义正确性仍需人工/LLM 复核。

已知局限：只从“声明行”抽取，**不解析函数参数名、也不做 AST**；复杂签名/一行多声明可能漏检；
Java/C# 的正则属启发式，可能把部分调用行误当声明。结果为提示，不作为硬性裁决。

用法:
  python check-code-names.py <file_or_dir> [--lang auto|py|ts|js|tsx|jsx|go|java|cs|rb|rs|kt]
                             [--json|--out FILE] [--strict] [--max-files N] [--quiet]

退出码: 0 正常；--strict 且存在 Critical 时返回 1。
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

EXT_LANG = {
    ".py": "py", ".pyi": "py",
    ".ts": "ts", ".tsx": "tsx", ".js": "js", ".jsx": "jsx", ".mjs": "js", ".cjs": "js",
    ".go": "go", ".java": "java", ".cs": "cs", ".rb": "rb", ".rs": "rs", ".kt": "kt",
}
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


def tokenize(name):
    """拆分 camelCase / PascalCase / snake_case / kebab / 数字 为小写词元。"""
    name = re.sub(r"[^0-9A-Za-z]+", " ", name)
    parts = []
    for chunk in name.split():
        # insert boundary between lower/digit and Upper, and between acronym and word
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", chunk)
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
        parts.extend(s.split())
    return [p.lower() for p in parts if p]


def normalize(name):
    """大小写冲突比较键：仅小写（保留分隔符），用于发现同类型声明只差大小写。"""
    return name.lower()


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
        ("variable", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\b")),
    ],
    "go": [
        ("function", re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(")),
        ("class", re.compile(r"\btype\s+([A-Za-z_]\w*)\b")),
        ("variable", re.compile(r"\b(?:var|const)\s+([A-Za-z_]\w*)\b")),
    ],
    "java": [
        ("class", re.compile(r"\b(?:class|interface|enum)\s+([A-Za-z_]\w*)\b")),
        ("function", re.compile(r"^\s*(?:public|private|protected|static|final|abstract|synchronized|native|\s)+[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*\(")),
        ("variable", re.compile(r"^\s*(?:public|private|protected|static|final|\s)+[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*=(?!=)")),
    ],
    "rs": [
        ("function", re.compile(r"\bfn\s+([A-Za-z_]\w*)\s*\(")),
        ("class", re.compile(r"\b(?:struct|enum|trait|union)\s+([A-Za-z_]\w*)\b")),
        ("variable", re.compile(r"\blet\s+(?:mut\s+)?([A-Za-z_]\w*)\b")),
    ],
    "rb": [
        ("function", re.compile(r"^\s*def\s+([A-Za-z_]\w*[?!]?)")),
        ("class", re.compile(r"^\s*(?:class|module)\s+([A-Za-z_]\w*)")),
        ("variable", re.compile(r"^\s*([A-Za-z_]\w*)\s*=(?!=)")),
    ],
}
# 复用 js 模式
DECL_PATTERNS["ts"] = DECL_PATTERNS["js"]
DECL_PATTERNS["tsx"] = DECL_PATTERNS["js"]
DECL_PATTERNS["jsx"] = DECL_PATTERNS["js"]
DECL_PATTERNS["cs"] = DECL_PATTERNS["java"]
DECL_PATTERNS["kt"] = DECL_PATTERNS["java"]


def extract_decls(text, lang):
    out = []
    pats = DECL_PATTERNS.get(lang, [])
    for i, line in enumerate(text.splitlines(), 1):
        for kind, rx in pats:
            m = rx.search(line)
            if m:
                nm = m.group(1)
                # 过滤明显非声明（如 JS 关键词）
                if nm in {"if", "for", "while", "switch", "return", "function", "new"}:
                    continue
                out.append((i, nm, kind))
                break
    return out


def check_file(path, lang):
    findings = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    stem = os.path.splitext(os.path.basename(path))[0]
    if stem.lower() in UTILS_NAMES:
        findings.append(dict(line=1, name=os.path.basename(path), kind="module", rule="utils_module",
                             severity="Major", message="垃圾模块名（utils/helpers/common/…）——按领域拆成具体模块"))

    decls = extract_decls(text, lang)

    # 同文件「同类型」大小写冲突检测
    lower_map = defaultdict(list)   # lower(name) -> [(name,line,kind)]
    for line, nm, kind in decls:
        lower_map[normalize(nm)].append((nm, line, kind))

    for line, nm, kind in decls:
        toks = tokenize(nm)
        if not toks:
            continue
        first, last = toks[0], toks[-1]

        # 只对函数/类名的单字母报警；局部变量单字母（i/x 等循环/数学惯用）不扫，避免噪声
        if len(nm) == 1 and kind in ("function", "class"):
            findings.append(dict(line=line, name=nm, kind=kind, rule="single_letter",
                                 severity="Minor", message="函数/类名只有单字母；改用描述性名字"))

        if kind == "function" and (first in VAGUE_VERBS or (first == "handle" and len(toks) == 1)):
            findings.append(dict(line=line, name=nm, kind=kind, rule="vague_verb",
                                 severity="Major", message="模糊动词（process/manage/do/run/data/temp…）；换成具体动词"))

        if kind in ("class", "variable") and last in WEASEL_SUFFIX:
            findings.append(dict(line=line, name=nm, kind=kind, rule="weasel_suffix",
                                 severity="Minor", message=f"可疑无信息后缀 “{last}”；若含真实角色语义可保留，否则换有信息的名"))

        for t in toks:
            if t in BAD_ABBR:
                findings.append(dict(line=line, name=nm, kind=kind, rule="abbreviation",
                                     severity="Major", message=f"未认可缩写 “{t}”；公开名请写全称"))
                break

        if first in BOOL_PREFIX and any(t in NEG_WORDS for t in toks[1:]):
            findings.append(dict(line=line, name=nm, kind=kind, rule="negation_boolean",
                                 severity="Minor", message="布尔含否定；尽量用正向（isReady 而非 isNotReady）"))

    # 大小写冲突：仅当“同类型”声明只差大小写（如两个变量 foo/Foo、两个类 Foo/foo）才报 Critical；
    # `class User` 搭配 `const user` 属正常跨类型，不报；纯分隔符/近义词分歧不做自动判断（交 glossary 人工核）。
    for lname, items in lower_map.items():
        uniq = {nm for nm, _, _ in items}
        if len(uniq) > 1:
            kinds = {k for _, _, k in items}
            if len(kinds) == 1:
                findings.append(dict(line=items[0][1], name="/".join(sorted(uniq)), kind="case", rule="case_collision",
                                     severity="Critical", message="同类型声明仅大小写不同（跨语言/重构不安全）；改名区分"))
    return findings


def iter_files(target, lang_opt, max_files):
    if os.path.isfile(target):
        yield target, detect_lang(target, lang_opt)
        return
    count = 0
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXT_LANG:
                count += 1
                if count > max_files:
                    return
                yield os.path.join(root, fn), detect_lang(fn, lang_opt)


def detect_lang(path, lang_opt):
    if lang_opt and lang_opt != "auto":
        return lang_opt
    return EXT_LANG.get(os.path.splitext(path)[1].lower(), "js")


def main():
    ap = argparse.ArgumentParser(description="代码命名轻量校验器")
    ap.add_argument("path")
    ap.add_argument("--lang", default="auto", choices=["auto", "py", "ts", "js", "tsx", "jsx", "go", "java", "cs", "rb", "rs", "kt"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--max-files", type=int, default=2000)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--out", default=None, help="把结果写入该文件（UTF-8）；避免 shell 管道捕获问题，便于 CI")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    all_findings = []
    files_scanned = 0
    for path, lang in iter_files(args.path, args.lang, args.max_files):
        files_scanned += 1
        try:
            for f in check_file(path, lang):
                f["file"] = path
                all_findings.append(f)
        except Exception as e:  # 单文件失败不中断
            if not args.quiet:
                print(f"[warn] skip {path}: {e}", file=sys.stderr)

    all_findings.sort(key=lambda x: (SEV_ORDER.get(x["severity"], 9), x["file"], x["line"]))
    counts = defaultdict(int)
    for f in all_findings:
        counts[f["severity"]] += 1

    lines = []
    if args.json:
        lines.append(json.dumps(dict(files_scanned=files_scanned,
                                     counts=dict(counts), findings=all_findings),
                                ensure_ascii=False, indent=2))
    elif not args.quiet:
        lines.append(f"扫描文件 {files_scanned} 个；问题 Critical={counts['Critical']} "
                     f"Major={counts['Major']} Minor={counts['Minor']}")
        lines.append("-" * 72)
        cur = None
        for f in all_findings:
            if f["file"] != cur:
                cur = f["file"]
                lines.append(f"\n{f['file']}")
            lines.append(f"  [{f['severity']}] {f['line']}: {f['name']}  <{f['rule']}> — {f['message']}")
        if not all_findings:
            lines.append("未发现明显命名问题（仍建议人工核对语义与一致性）。")

    text = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as wf:
            wf.write(text + "\n")
    elif text:
        print(text)

    if args.strict and counts["Critical"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
