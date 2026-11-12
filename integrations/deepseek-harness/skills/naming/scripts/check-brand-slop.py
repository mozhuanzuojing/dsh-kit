#!/usr/bin/env python3
"""check-brand-slop.py — 名字的「AI 味」体检（product 模式辅助）。

定位：**启发式提示器，不是裁判**。它把 `anti-patterns.md` 里可判定的部分机器化，
输出「命中项 + 证据片段 + 建议」，由人决定是否采纳。任何一项命中都不代表名字必须弃用。

检查项（product 侧）：
  S1 slop_suffix      AI 味后缀（-ly/-ify/-ora/-ix/-able/-aholic…）
  S2 empty_word       空洞企业词 / 首词填充 / 次词空泛（Solutions/Labs/Platform/Hub/Flow…）
  S3 category_modifier 类别词+修饰（CloudGuard/DataSync 式）
  S4 ai_prefix        AI 前缀/后缀（AIWriter/Copilot 模仿/Smart/Neural）
  S5 thesaurus       同义词库高频词（Apex/Pinnacle/Summit/Zenith）
  S6 fake_latinate   假拉丁/希腊词根（-ex/-iq/-ora 组合）
  S7 stunt_spelling   过度拼写变形（去元音、K 替 C 的连续出现）
  S8 rhyme_stack      过度押韵/重复音（CocaCola 式在 B2B 里显得轻佻）
  S9 length_syllable  音节数超出经验甜区（只提示，不作否决）

用法:
  python check-brand-slop.py "NameOne" "NameTwo" ... [--json] [--out FILE] [--quiet]

退出码: 恒为 0（提示器不阻断流水线）；--strict 时若有 S1/S2/S4 命中返回 1。

依赖：`_common.py`（同目录，词元切分与原子写；要拷就拷整个 scripts/）。

语言边界（重要）：**只支持拉丁拼写**。中文/日文/韩文名输出"未检查"而不是"通过"——
英文的后缀/元音/音节规则对它们无意义，静默给满分就是伪成功。中文名请走
`references/zh-phonetics.md` 的 8 项自检表。
"""
import argparse
import json
import os
import re
import sys
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import atomic_write, script_profile, tokenize  # noqa: E402

# ---------------------------------------------------------------- 词表

SLOP_SUFFIXES = ["ly", "ify", "ora", "ix", "able", "aholic", "esque", "ista", "ium", "eon", "ia"]
EMPTY_WORDS = {
    "solutions", "labs", "lab", "platform", "hq", "systems", "technologies", "group",
    "global", "network", "holdings", "ventures", "partners", "consulting", "services",
    "hub", "base", "flow", "sync", "link", "stack", "forge", "shift", "scape", "verse",
    "craft", "wise", "path", "nest", "box", "core", "omni",
}
FILLER_PREFIX = {
    "smart", "auto", "cloud", "ai", "data", "cyber", "next", "digital", "true", "pure",
    "open", "fast", "easy", "pro", "ultra", "hyper", "super", "meta", "omni",
}
AI_TOKENS = {"ai", "copilot", "pilot", "gpt", "llm", "neural", "neuro", "magic", "spell", "wand", "conjure"}
THESAURUS = {
    "apex", "pinnacle", "summit", "zenith", "catalyst", "beacon", "horizon", "nexus",
    "synergy", "momentum", "elevate", "ascend", "prime", "elite", "vanguard", "atlas",
}
FAKE_LATINATE = re.compile(r"(?:[a-z]{2,})(?:ex|iq|ora|yx|eon|um)$", re.I)
CATEGORY_TERMS = {
    "guard", "watch", "sync", "monitor", "tracker", "scanner", "manager", "builder",
    "editor", "reader", "writer", "viewer", "finder", "checker", "cleaner",
}
VOWELS = set("aeiouy")

# 只用 y 作元音的正常英文词（不该被“去元音式变形”规则误伤）。
# 这是一份**有限白名单**，不是词典：命中不了就按变形处理，误报由人复核（提示器不阻断）。
Y_VOWEL_WORDS = {
    "rhythm", "rhythms", "myth", "myths", "gym", "gyms", "lynx", "crypt", "crypts",
    "tryst", "sylph", "lymph", "nymph", "nymphs", "hymn", "hymns", "psych", "psychs",
    "flyby", "gypsy", "pygmy", "syzygy", "myrrh", "glyph", "glyphs", "sphynx",
}


# ---------------------------------------------------------------- 工具


def syllables(name):
    """粗估英文音节数：按元音簇计数，末尾不发音 e 减一。"""
    word = re.sub(r"[^a-z]", "", name.lower())
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and not word.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def max_consonant_run(name):
    """最长连续辅音串长度；`y` 视为元音。用来区分「去元音式变形」与正常的英文拼写。"""
    best = cur = 0
    for ch in name.lower():
        if not ch.isalpha():
            cur = 0
            continue
        if ch in "aeiouy":
            cur = 0
        else:
            cur += 1
            best = max(best, cur)
    return best


def vowel_ratio(name):
    """元音占比（y 计作元音），仅用于展示。"""
    s = name.lower()
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c in "aeiouy") / len(letters)


# ---------------------------------------------------------------- 规则

def check_one(name):
    """返回 [{rule, severity, message, evidence}]。

    只支持拉丁拼写。非拉丁名返回一条 `not_supported`（Minor）并**跳过所有英文规则**，
    调用方必须把它显示成"未检查"，不能当成"通过"。
    """
    hits = []
    latin, cjk, other = script_profile(name)
    if latin == 0:
        hits.append(dict(
            rule="not_supported", severity="Minor",
            message="名字不含拉丁字母，本检查器的规则（英文后缀/元音/音节）不适用；"
                    "这不是「没问题」，是「没检查」——中文/日文/韩文名请走 references/zh-phonetics.md 的 8 项自检",
            evidence=f"latin=0, cjk={cjk}, other={other}"))
        return hits

    low = name.lower()
    toks = tokenize(name)

    def add(rule, sev, msg, evidence):
        hits.append(dict(rule=rule, severity=sev, message=msg, evidence=evidence))

    # S1 slop 后缀
    for suf in SLOP_SUFFIXES:
        if low.endswith(suf) and len(low) > len(suf) + 2:
            add("slop_suffix", "Major",
                f"以 “-{suf}” 结尾，属 AI 生成名高频后缀；若无法说明为何必须有它，替换",
                f"-{suf}")
            break

    # S2 空洞词
    for t in toks:
        if t in EMPTY_WORDS:
            add("empty_word", "Major", f"含空洞词 “{t}”（不传达任何具体信息）", t)
            break
    for t in toks[:1]:
        if t in FILLER_PREFIX:
            add("empty_word", "Minor", f"首词是填充词 “{t}”，盖住后一半还剩具体含义吗？", t)

    # S3 类别词 + 修饰
    tok_set = set(toks)
    if tok_set & CATEGORY_TERMS and len(toks) >= 2:
        cat = sorted(tok_set & CATEGORY_TERMS)
        add("category_modifier", "Minor",
            f"疑似“类别词+修饰”（{cat[0]}），描述清楚但不易记；把描述交给 tagline", cat[0])

    # S4 AI 词
    for t in toks:
        if t in AI_TOKENS:
            add("ai_prefix", "Major", f"含 AI 时代热词 “{t}”，会随品类降温而过时", t)
            break

    # S5 同义词库
    for t in toks:
        if t in THESAURUS:
            add("thesaurus", "Minor", f"“{t}” 是同义词库高频词，已被大量使用", t)
            break

    # S6 假拉丁
    if FAKE_LATINATE.search(low) and low not in THESAURUS:
        add("fake_latinate", "Minor", "词尾像人造拉丁/希腊（-ex/-iq/-ora/-eon），有“唬人 2 秒”风险",
            FAKE_LATINATE.search(low).group(0))

    # S7 过度拼写变形
    letters = re.sub(r"[^a-z]", "", low)
    if letters:
        run = max_consonant_run(letters)
        if run >= 4 and len(letters) >= 4:
            add("stunt_spelling", "Major",
                f"出现 {run} 个连续辅音，读不出＝记不住（注意：正常英文词很少超过 3 连辅音）",
                f"{run} consecutive consonants")
        elif (len(letters) >= 5 and not (set(letters) & set("aeiou"))
              and letters not in Y_VOWEL_WORDS):
            add("stunt_spelling", "Major",
                "整词没有 a/e/i/o/u，靠 y 撑元音（“去元音”式变形）；除非本就是英文词，否则读不出",
                "no aeiou")
        k_ratio = letters.count("k") / len(letters)
        if k_ratio > 0.28 and len(letters) >= 5:
            add("stunt_spelling", "Minor",
                f"字母 k 占比 {k_ratio:.0%}，疑 K 替 C 式变形（2010 年套路）", "k-heavy")

    # S8 押韵堆叠
    if len(toks) >= 2:
        firsts = [t[0] for t in toks if t]
        if len(firsts) >= 2 and len(set(firsts)) == 1:
            add("rhyme_stack", "Minor", "连续押头韵，易记但也易显轻佻；B2B 慎用", "".join(firsts))

    # S9 音节数（只提示）
    syl = syllables(name)
    if syl > 3:
        add("length_syllable", "Minor",
            f"约 {syl} 个音节，超过“2 音节便于口播”的经验区；长度只作权重、不作否决",
            f"{syl} syl")

    return hits



def score(hits):
    """0-100 的粗分：只用于排序，不是质量证明。未检查（not_supported）不给分。"""
    if any(h["rule"] == "not_supported" for h in hits):
        return None
    weight = {"Major": 12, "Minor": 5}
    penalty = sum(weight.get(h["severity"], 0) for h in hits)
    return max(0, 100 - penalty)


def main():
    ap = argparse.ArgumentParser(description="命名 AI-slop 体检（启发式提示器）")
    ap.add_argument("names", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    results = []
    for name in args.names:
        hits = check_one(name)
        results.append(dict(name=name, syllables=syllables(name), score=score(hits), hits=hits))

    if args.json:
        text = json.dumps(dict(results=results), ensure_ascii=False, indent=2)
    elif not args.quiet:
        lines = []
        for r in results:
            if r["score"] is None:
                lines.append(f"{r['name']}  —  未检查（非拉丁名，英文规则不适用）")
            else:
                lines.append(f"{r['name']}  —  slop score {r['score']}/100（{r['syllables']} 音节）")
                if not r["hits"]:
                    lines.append("  （未命中已知模式；这只是没有明显 AI 味，不代表名字好）")
            for h in r["hits"]:
                lines.append(f"  [{h['severity']}] {h['rule']}: {h['message']}  ← {h['evidence']}")
            lines.append("")
        lines.append("提示器只做筛查：命中≠否决，未命中≠好名。语义、故事、可用性仍走主流程。")
        text = "\n".join(lines)
    else:
        text = ""

    if args.out:
        atomic_write(args.out, text + "\n")
    elif text:
        print(text)

    unchecked = [r["name"] for r in results if r["score"] is None]
    if unchecked and not args.quiet:
        print(f"[warn] {len(unchecked)} 个名字未检查（非拉丁）：{', '.join(unchecked[:5])}"
              f"{' …' if len(unchecked) > 5 else ''}——请改用 zh-phonetics 的自检表", file=sys.stderr)

    if args.strict:
        for r in results:
            if any(h["rule"] in ("slop_suffix", "empty_word", "ai_prefix") and h["severity"] == "Major"
                   for h in r["hits"]):
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
