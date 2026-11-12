#!/usr/bin/env python3
"""回归测试：check-brand-slop.py（AI 味体检器）。

跑法：python test_check_brand_slop.py
退出码：0 = 全部通过。

设计意图：contrast 用例成对出现——「该报警的」必须报，「正常名字」必须不误报。
只测**提示器**的行为，不测审美。
"""
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CHILD_ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
# 子进程也不写 __pycache__，避免污染技能目录

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-brand-slop.py")


def judge(*names):
    proc = subprocess.run([sys.executable, SCRIPT, *names, "--json"],
                          env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, f"退出码非 0: {proc.returncode} / {proc.stderr[:200]}"
    payload = json.loads(proc.stdout)
    return {r["name"]: r for r in payload["results"]}


def rules_of(entry):
    return {h["rule"] for h in entry["hits"]}


def case_slop_suffixes():
    got = judge("Glidely", "Parsify", "Syncora", "Brightrix")
    for name in got:
        assert "slop_suffix" in rules_of(got[name]), f"{name} 未报 slop_suffix: {got[name]}"
    return True


def case_real_words_pass():
    """正常真实词不应报 Major（Sentry/Vault/Prism/Nimbus/Strive 是常用真实词）。"""
    got = judge("Sentry", "Vault", "Prism", "Nimbus", "Strive")
    for name, entry in got.items():
        majors = [h for h in entry["hits"] if h["severity"] == "Major"]
        assert not majors, f"{name} 误报 Major: {majors}"
    return True


def case_empty_corporate_words():
    got = judge("DataSyncHQ", "Bright Solutions", "MetaFlow")
    assert "empty_word" in rules_of(got["DataSyncHQ"]), got["DataSyncHQ"]
    assert "empty_word" in rules_of(got["Bright Solutions"]), got["Bright Solutions"]
    assert "empty_word" in rules_of(got["MetaFlow"]), got["MetaFlow"]
    return True


def case_ai_tokens():
    got = judge("NeuralWriter", "AIWriter", "CopilotKit", "MagicWand")
    for name in got:
        assert "ai_prefix" in rules_of(got[name]), f"{name} 未报 ai_prefix: {got[name]}"
    return True


def case_thesaurus():
    got = judge("Apex", "Pinnacle", "Zenith")
    for name in got:
        assert "thesaurus" in rules_of(got[name]), f"{name} 未报 thesaurus"
    return True


def case_stunt_spelling():
    got = judge("Brightrix", "Strykr")
    for name in got:
        assert "stunt_spelling" in rules_of(got[name]), f"{name} 未报 stunt_spelling: {got[name]}"
    # 正常的 3 连辅音（str/spr/spl）不该报
    ok = judge("Strive", "Sprint", "Splash")
    for name, entry in ok.items():
        assert "stunt_spelling" not in rules_of(entry), f"{name} 误报 stunt_spelling"
    return True


def case_shorter_is_better_reported_only():
    """长度只作 Minor 提示，不出现 Major。"""
    got = judge("NeuralWriterAutomation")
    majors = [h for h in got["NeuralWriterAutomation"]["hits"]
              if h["rule"] == "length_syllable" and h["severity"] == "Major"]
    assert not majors, "length_syllable 不该是 Major"
    return True


def case_strict_exit():
    proc = subprocess.run([sys.executable, SCRIPT, "Glidely", "--strict"],
                          env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 1, f"--strict 未因 Major 命中退出 1: {proc.returncode}"
    proc2 = subprocess.run([sys.executable, SCRIPT, "Sentry", "--strict"],
                           env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8")
    assert proc2.returncode == 0, f"干净名字在 --strict 下不应退出 1: {proc2.returncode}"
    return True


def case_nonzero_exit_never_blocks():
    """不带 --strict 时恒为 0（提示器不阻断流水线）。"""
    proc = subprocess.run([sys.executable, SCRIPT, "Syncora", "AIWriter"],
                          env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, f"默认退出码应为 0，实际 {proc.returncode}"
    return True


def case_non_latin_is_unchecked():
    """中文/日文/韩文名必须报"未检查"，不得静默给 100 分（伪成功）。"""
    got = judge("字节跳动", "小鹅通", "トヨタ", "삼성")
    for name, entry in got.items():
        assert entry["score"] is None, f"{name} 不该给出分数（应为未检查）: {entry}"
        assert any(h["rule"] == "not_supported" for h in entry["hits"]), f"{name} 未标记 not_supported"
        asserts = [h for h in entry["hits"] if h["severity"] == "Major"]
        assert not asserts, f"{name} 不应产生 Major（英文规则不适用）: {asserts}"
    return True


def case_non_latin_does_not_break_strict():
    """--strict 不应因"未检查"而返回 1（未检查不是失败，是没做）。"""
    proc = subprocess.run([sys.executable, SCRIPT, "字节跳动", "--strict"],
                          env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, f"中文名在 --strict 下不应退出 1: {proc.returncode}"
    assert "未检查" in proc.stderr or "not" in proc.stderr.lower(), f"stderr 未提示未检查: {proc.stderr!r}"
    return True


def case_mixed_latin_cjk_still_checked():
    """拉丁+中混合（如 WeChat 类品牌的中文侧混合名）按拉丁规则检查。"""
    got = judge("Glidely笔记")
    assert got["Glidely笔记"]["score"] is not None, "含拉丁字母时应正常检查"
    return True


def main():
    cases = [case_slop_suffixes, case_real_words_pass, case_empty_corporate_words,
             case_ai_tokens, case_thesaurus, case_stunt_spelling,
             case_shorter_is_better_reported_only, case_strict_exit,
             case_nonzero_exit_never_blocks, case_non_latin_is_unchecked,
             case_non_latin_does_not_break_strict, case_mixed_latin_cjk_still_checked]
    failed = 0
    width = max(len(c.__name__) for c in cases)
    for c in cases:
        try:
            c()
            print(f"{c.__name__:<{width}}  PASS")
        except AssertionError as e:
            print(f"{c.__name__:<{width}}  FAIL  {str(e)[:220]}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"{c.__name__:<{width}}  ERROR  {type(e).__name__}: {str(e)[:200]}")
            failed += 1
    print(f"\n{len(cases) - failed}/{len(cases)} 通过，{failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
