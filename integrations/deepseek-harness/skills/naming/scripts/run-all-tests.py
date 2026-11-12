#!/usr/bin/env python3
"""run-all-tests.py — 一键跑全部回归（CI 与本地都用这一条）。

用法：python scripts/run-all-tests.py
退出码：0 = 全绿；1 = 有失败。

为什么要有它：技能里有 6 个测试文件，逐条跑容易漏。这个 runner 顺序执行、
汇总通过/失败数，并且**任何子测试失败都不会被后续成功掩盖**。
"""
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
SUITES = [
    ("test_common.py", "公共模块：tokenize / singular / atomic_write"),
    ("test_check_code_names.py", "代码命名：三层引擎 + 近名 + rename 分档"),
    ("test_check_brand_slop.py", "品牌 AI 味：9 条规则 + 语言门"),
    ("test_check_cross_layer.py", "跨层命名：三宗陷阱 + 单位 + audit 作用域"),
    ("test_check_ai_visibility.py", "L1.5：采集/统计/失败计入分母/禁止排名"),
    ("test_check_ui_names.py", "UI 层：按钮/aria/令牌/i18n/空态"),
]


def parse_summary(summary):
    """从 "N/M 通过，K 失败" 里取 (passed, failed, total)。

    子测试的格式是 `{len-failed}/{len} 通过，{failed} 失败`，所以：
      · 斜杠右边是**总数**，不是失败数（早期版本在这里读错，把 8/8 读成 8 通过 8 失败）
      · 失败数以“K 失败”为准；解析不出来时返回 (0, 0, 0)，让该 suite 判为 FAIL 而不是假绿
    """
    import re
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*通过[，,]\s*(\d+)\s*失败", summary)
    if m:
        return int(m.group(1)), int(m.group(3)), int(m.group(2))
    m2 = re.search(r"(\d+)\s*/\s*(\d+)\s*通过", summary)
    if m2:
        passed, total = int(m2.group(1)), int(m2.group(2))
        return passed, total - passed, total
    return 0, 0, 0


def main():
    total_pass = total_fail = 0
    rows = []
    for script, desc in SUITES:
        path = os.path.join(HERE, script)
        if not os.path.isfile(path):
            rows.append((script, "MISSING", 0, 0))
            total_fail += 1
            continue
        proc = subprocess.run([sys.executable, path], env=CHILD_ENV, capture_output=True,
                              text=True, encoding="utf-8")
        out = (proc.stdout or "").strip().splitlines()
        summary = out[-1] if out else "(无输出)"
        passed, failed, total = parse_summary(summary)
        total_pass += passed
        total_fail += failed
        # 退出码与"0 失败"必须**同时**成立才算 PASS；任一为假都不算绿
        status = "PASS" if proc.returncode == 0 and failed == 0 and total > 0 else "FAIL"
        rows.append((script, status, passed, failed))

    width = max(len(r[0]) for r in rows)
    print(f"{'suite':<{width}}  {'status':<8} {'pass':>4} {'fail':>4}  what")
    print("-" * 100)
    for (script, status, passed, failed), (_, desc) in zip(rows, SUITES):
        print(f"{script:<{width}}  {status:<8} {passed:>4} {failed:>4}  {desc}")
    print("-" * 100)
    print(f"合计：{total_pass} 通过 / {total_fail} 失败")
    if total_fail:
        print("\n有失败：逐条修掉再交付，不要带着红的测试往下走。", file=sys.stderr)
        return 1
    print("全绿。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
