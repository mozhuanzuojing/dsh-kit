#!/usr/bin/env python3
"""check-ui-names.py — 界面文案 / 无障碍标签 / i18n key 的静态检查（code 模式 UI 层）。

定位：**只检查可判定的部分**，不评判文案好坏（那需要人读）。
它把 `ui-naming.md` 里"能被规则抓住"的条目机器化：
  U1 generic_button   按钮文案是「确定/提交/OK/Submit」这类无信息动词
  U2 vague_error      错误/提示文案是「出错了/系统异常/Error」这类无出路的话
  U3 icon_no_label    图标按钮（aria-label 缺失或只写动词）—— 需 --scan aria
  U4 aria_generic     aria-label 是「删除/编辑/关闭」等无对象单词
  U5 token_appearance 设计令牌用外观名（--color-red）而非语义名（--color-danger）
  U6 i18n_key_text    i18n key 里出现空格/中文/文案式命名（noDataText）
  U7 danger_no_scope  危险操作文案（删除/清空/注销）没写范围或不可逆
  U8 empty_state      「暂无数据 / No data」这类空态文案

用法:
  python check-ui-names.py <path...> [--lang auto|html|jsx|tsx|json|yaml|css]
      [--scan aria|i18n|copy|css|all] [--json] [--out FILE] [--strict] [--quiet]

退出码：0 正常；--strict 且有 Major 时 1；参数/路径错误 2。
依赖：`_common.py`（同目录，原子写）。
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

GENERIC_BUTTONS = {
    "确定", "确认", "提交", "执行", "好的", "好", "是", "否", "下一步",
    "ok", "okay", "submit", "confirm", "yes", "no", "done", "go", "apply", "save",
}
# 注意：`save` 单独出现算泛，但 `保存更改` 不算 —— 判定看是否**只有一个词**且在该集合里。

VAGUE_ERRORS = {
    "出错了", "错误", "系统异常", "操作失败", "失败", "发生错误", "未知错误",
    "error", "an error occurred", "something went wrong", "failed", "failure",
    "unexpected error", "oops",
}

GENERIC_ARIA = {
    "删除", "编辑", "关闭", "提交", "确定", "更多", "菜单", "设置", "打开", "返回",
    "delete", "edit", "close", "submit", "ok", "more", "menu", "settings", "open", "back",
}

DANGER_VERBS = {"删除", "清空", "注销", "重置", "撤销", "移除", "覆盖", "delete", "remove",
                "clear", "reset", "destroy", "wipe", "uninstall", "revoke"}
SCOPE_HINTS = re.compile(r"\d|所有|全部|永久|不可恢复|无法撤销|该|此|all|permanent|cannot be undone|entire", re.I)

EMPTY_STATES = {
    "暂无数据", "没有数据", "无数据", "空空如也",
    "no data", "no results", "nothing here", "empty", "no items",
}

APPEARANCE_TOKEN = re.compile(r"--(?:color-)?(red|blue|green|yellow|orange|purple|pink|gray|grey|black|white|cyan|magenta)\b")
I18N_KEY_BAD = re.compile(r"[\u4e00-\u9fff\s]")
I18N_VALUEISH = re.compile(r"\b(noDataText|errorMessage|buttonLabel|titleText|descriptionText)\b")

EXT_LANG = {
    ".html": "html", ".htm": "html", ".vue": "html",
    ".jsx": "jsx", ".tsx": "tsx", ".js": "jsx", ".ts": "tsx",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".css": "css", ".scss": "css", ".less": "css",
}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "target", "__pycache__", ".venv", "vendor", "coverage"}

# 抓「按钮文案」：HTML 文本、JSX 文本、aria-label、以及 i18n 值
BUTTON_HTML = re.compile(r"<button[^>]*>([^<>{}]{1,40})</button>", re.I | re.S)
# {0,60}：必须能抓到 aria-label=""（空值是「图标按钮没有可读名」的最严重形态）
ARIA_ATTR = re.compile(r'aria-label\s*=\s*["\']([^"\']{0,60})["\']', re.I)
ALT_ATTR = re.compile(r'alt\s*=\s*["\']([^"\']{0,120})["\']', re.I)
# 两种都要抓：
#   语义路径 "orders.empty.title":
#   值式命名 "noDataText":  ← 无点号但结尾是 Text/Label/Message/Title/Button
I18N_KEY = re.compile(
    r'["\']('
    r'[a-zA-Z][\w.\-]*\.[\w.\-]+'                      # orders.empty.title
    r'|[a-z]+[A-Z][A-Za-z]*(?:Text|Label|Message|Title|Button)'  # noDataText
    r'|[^"\']*[\u4e00-\u9fff][^"\']*'                    # 中文 key 本身就该报
    r')["\']\s*:')
CSS_TOKEN = re.compile(r"--[\w-]+\s*:")
JSX_TEXT = re.compile(r">\s*([\u4e00-\u9fff][^<>{}]{0,30}|[A-Z][a-z]+(?:\s+[a-z]+){0,3})\s*<")


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).strip("：:。.!！?？")


def is_generic_button(text):
    t = norm(text).lower()
    return t in GENERIC_BUTTONS


def is_vague_error(text):
    t = norm(text).lower()
    return t in VAGUE_ERRORS


def is_generic_aria(text):
    t = norm(text).lower()
    return t in GENERIC_ARIA


def danger_without_scope(text):
    t = norm(text)
    low = t.lower()
    if not any(v in low for v in DANGER_VERBS):
        return False
    return SCOPE_HINTS.search(t) is None


# 形如 orders.empty.title / noDataText / checkout.payment.submitButton 的 i18n key
I18N_KEY_INLINE = re.compile(r'["\']([A-Za-z][\w\-]*(?:\.[A-Za-z][\w\-]*)+|[a-z]+[A-Z][A-Za-z]*(?:Text|Label|Message|Title|Button))["\']\s*:')


def strip_i18n_keys(line):
    """把 i18n key 从行里剥掉，只留下可能是文案的部分。

    否则 `"orders.empty.title": "还没有项目"` 会因为 key 里的 `empty` 被误判成空态文案。
    """
    return I18N_KEY_INLINE.sub('"" :', line)


def _standalone(needle, haystack):
    """needle 必须是独立词/短语，不能是更长标识符的一部分。"""
    if re.search(r"[a-z0-9]", needle[:1]):
        pat = r"(?<![a-z0-9_.\-])" + re.escape(needle) + r"(?![a-z0-9_.\-])"
    else:
        pat = re.escape(needle)
    return re.search(pat, haystack) is not None


def check_file(path, lang, scans):
    findings = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    lines = text.splitlines()

    def lineno(pos):
        return text[:pos].count("\n") + 1

    def add(rule, sev, line_no, msg, evidence):
        findings.append(dict(file=path, line=line_no, rule=rule, severity=sev,
                             message=msg, evidence=evidence))

    if "copy" in scans or "all" in scans:
        for m in BUTTON_HTML.finditer(text):
            label = norm(m.group(1))
            if label and is_generic_button(label):
                add("generic_button", "Major", lineno(m.start()),
                    f"按钮文案 “{label}” 是无信息动词；改成「动词 + 对象」（如「保存更改」）", label)
            elif label and danger_without_scope(label):
                add("danger_no_scope", "Major", lineno(m.start()),
                    f"危险操作 “{label}” 没写清范围或不可逆性（试写「永久删除 3 个文件」）", label)

    if "aria" in scans or "all" in scans:
        for m in ARIA_ATTR.finditer(text):
            label = norm(m.group(1))
            if not label:
                add("icon_no_label", "Major", lineno(m.start()),
                    "aria-label 为空；图标按钮对读屏用户等于不存在", "aria-label=\"\"")
            elif is_generic_aria(label):
                add("aria_generic", "Major", lineno(m.start()),
                    f"aria-label “{label}” 只有动作没有对象；读屏里十个「删除」无法区分", label)

    if "css" in scans or "all" in scans:
        for m in APPEARANCE_TOKEN.finditer(text):
            add("token_appearance", "Minor", lineno(m.start()),
                f"设计令牌 “{m.group(0)}” 用外观名；改成语义名（--color-danger / --color-success）", m.group(0))

    if "i18n" in scans or "all" in scans:
        for m in I18N_KEY.finditer(text):
            key = m.group(1)
            if I18N_KEY_BAD.search(key):
                add("i18n_key_text", "Major", lineno(m.start()),
                    f"i18n key “{key}” 含空格或中文；key 应是语义路径（orders.empty.title）", key)
            elif I18N_VALUEISH.search(key):
                add("i18n_key_text", "Minor", lineno(m.start()),
                    f"i18n key “{key}” 用文案式命名；改成语义路径（orders.empty.title）", key)

    # 空态与模糊错误：跨语言扫（HTML/JSX/JSON/YAML 都可能出现）
    # 关键防误报：i18n **key**（orders.empty.title / noDataText）不是文案，不能当命中。
    if "copy" in scans or "all" in scans:
        for i, line in enumerate(lines, 1):
            low = line.lower()
            prose = strip_i18n_keys(line)
            if not prose.strip():
                continue
            low_prose = prose.lower()
            for bad in EMPTY_STATES:
                if _standalone(bad, low_prose) and re.search(r'["\'>:]', prose):
                    add("empty_state", "Minor", i,
                        f"空态文案 “{bad}” 只说没数据；应写「现在怎样 + 下一步能做什么」", bad)
                    break
            for bad in VAGUE_ERRORS:
                if _standalone(bad, low_prose) and len(norm(prose)) < 120 and re.search(r'["\'>]', prose):
                    add("vague_error", "Major", i,
                        f"错误文案 “{bad}” 没说出对象/原因/出路", bad)
                    break

    return findings


def iter_targets(paths, lang_opt, scans):
    for target in paths:
        if os.path.isfile(target):
            lang = EXT_LANG.get(os.path.splitext(target)[1].lower())
            if lang:
                yield target, lang
            else:
                print(f"[warn] 不支持的扩展名，跳过：{target}", file=sys.stderr)
            continue
        for dirpath, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in EXT_LANG:
                    yield os.path.join(dirpath, fn), EXT_LANG[ext]


def main():
    ap = argparse.ArgumentParser(description="UI 文案 / 无障碍 / i18n 静态检查")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--scan", default="all", choices=["aria", "i18n", "copy", "css", "all"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    scans = {args.scan}
    all_findings = []
    scanned = 0
    for path, lang in iter_targets(args.paths, args.lang, scans):
        scanned += 1
        try:
            for f in check_file(path, lang, scans):
                all_findings.append(f)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] skip {path}: {type(e).__name__}: {e}", file=sys.stderr)

    if scanned == 0:
        print(f"[error] 没有扫描到任何受支持的文件：{args.paths}", file=sys.stderr)
        return 2

    all_findings.sort(key=lambda x: (SEV.get(x["severity"], 9), x["file"], x["line"]))
    counts = {}
    for f in all_findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    if args.json:
        text = json.dumps(dict(files_scanned=scanned, counts=counts, findings=all_findings),
                          ensure_ascii=False, indent=2)
    elif not args.quiet:
        lines = [f"扫描文件 {scanned} 个（scan={args.scan}）；问题 "
                 f"Critical={counts.get('Critical', 0)} Major={counts.get('Major', 0)} "
                 f"Minor={counts.get('Minor', 0)}", "-" * 70]
        cur = None
        for f in all_findings:
            if f["file"] != cur:
                cur = f["file"]
                lines.append(f"\n{cur}")
            lines.append(f"  [{f['severity']}] {f['line']}: <{f['rule']}> — {f['message']}")
        if not all_findings:
            lines.append("未发现可判定的 UI 命名问题（文案好坏仍需人读）。")
        lines.append("\n提示：本检查器只覆盖可正则化的部分；语气、人称、句首大写由产品的 content style guide 定。")
        text = "\n".join(lines)
    else:
        text = ""

    if args.out:
        atomic_write(args.out, text + "\n")
    elif text:
        print(text)

    if args.strict and counts.get("Major", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
