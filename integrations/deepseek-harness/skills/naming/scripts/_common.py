"""_common.py — naming 技能脚本的公共工具（唯一实现，禁止各自复制）。

为什么单独一个模块：`check-code-names.py` 与 `check-brand-slop.py` 都需要把
`getUserName` / `get_user_name` / `GET-USER-NAME` 拆成同一套词元。早先两份实现
虽然行为等价，但改一处忘一处就是静默分歧（一次实测：21 个样本 0 差异，但那只是
当时的样本）。现在只有这一份。

**拷贝约束**：脚本不再"单文件可拷走"，要拷就拷整个 `scripts/` 目录。这是有意的
权衡——一致性 > 便携性。

**回归**：改本文件后必须跑 `python scripts/run-all-tests.py`（63 个用例）。
`singular()` 的三个历史 bug（classes→classe / status→statu / aliases→aliase）
都是在这套测试下才暴露的。

公开 API：
  tokenize(name)          -> ["get", "user", "name"]
  strip_sep(name)         -> "getusername"
  singular(word)          -> 去掉复数
  edit_distance_le1(a,b)  -> bool
  atomic_write(path, txt) -> 原子写（临时文件 + os.replace）
  script_profile(name)    -> (latin, cjk, other) 字符脚本统计
"""
import os
import sys
import re
import tempfile
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

__all__ = ["tokenize", "strip_sep", "singular", "edit_distance_le1",
           "atomic_write", "script_profile"]


def tokenize(name):
    """拆分 camelCase / PascalCase / snake_case / kebab / 空格 / 数字 为小写词元。"""
    s = re.sub(r"[^0-9A-Za-z]+", " ", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return [t.lower() for t in s.split() if t]


def strip_sep(name):
    """去掉所有分隔符与前导下划线，用于"仅大小写/分隔符不同"的比较。"""
    return re.sub(r"[^0-9a-z]+", "", name.lower().lstrip("_"))


# 以 s 结尾但**不是**复数的词：单数化会毁掉它们。
NOT_PLURAL = {
    "status", "alias", "address", "class", "process", "access", "analysis", "bus",
    "gas", "canvas", "atlas", "bias", "lens", "series", "species", "news", "data", "media",
}

# 不规则/易错的少数词，显式列出（比通用规则更可靠，且不会误伤 cases/phases）
PLURAL_TO_SINGULAR = {
    "aliases": "alias", "analyses": "analysis", "bases": "base", "cases": "case",
    "phases": "phase", "databases": "database", "interfaces": "interface",
    "licenses": "license", "releases": "release", "responses": "response",
    "processes": "process", "addresses": "address", "classes": "class",
    "children": "child", "people": "person", "indices": "index", "matrices": "matrix",
    "criteria": "criterion",
}


def singular(word):
    """粗粒度单数化（只用于近名比较，不追求语言学正确）。

    修过的三个真实 bug：
      classes -> classe（应 class）
      status  -> statu （ss 守卫没覆盖 us 结尾）
      aliases -> aliase（应 alias）
    """
    w = word.lower()
    if w in NOT_PLURAL:
        return w
    if w in PLURAL_TO_SINGULAR:
        return PLURAL_TO_SINGULAR[w]
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("sses"):
        return w[:-2]
    if len(w) > 3 and w.endswith(("xes", "ches", "shes")):
        return w[:-2]
    if len(w) > 2 and w.endswith("es") and not w.endswith(("ses", "zes", "ces")):
        return w[:-2]
    if len(w) > 2 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def edit_distance_le1(a, b):
    """True 当且仅当 Levenshtein 距离 <= 1（O(n)，不分配矩阵）。"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] != b[j]:
            if skipped:
                return False
            skipped = True
            j += 1
            continue
        i += 1
        j += 1
    return True


def atomic_write(path, text):
    """原子写：先写同目录临时文件，再 os.replace。

    为什么必须这样：`--out` 常被 CI 在检查器还在跑时读取，普通 `open(w)` 会让
    读方看到半截文件（读到的 JSON 不完整，报错还难以归因）。os.replace 在同一
    文件系统内是原子的。
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".naming-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def script_profile(name):
    """返回 (latin_letters, cjk_chars, other_letters)。

    英文规则（后缀/元音/音节）只对拉丁拼写有意义。非拉丁输入必须显式降级，
    不能输出"100 分 + 未命中"这种伪成功。
    """
    latin = cjk = hangul = kana = other = 0
    for c in name:
        if not c.isalpha():
            continue
        if c.isascii():
            latin += 1
        elif "\u3400" <= c <= "\u4dbf" or "\u4e00" <= c <= "\u9fff" or "\uf900" <= c <= "\ufaff":
            cjk += 1
        elif "\uac00" <= c <= "\ud7af":
            hangul += 1
        elif "\u3040" <= c <= "\u30ff":
            kana += 1
        else:
            other += 1
    return latin, cjk, other + hangul + kana
