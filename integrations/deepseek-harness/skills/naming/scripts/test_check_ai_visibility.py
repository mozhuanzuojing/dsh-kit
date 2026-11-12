#!/usr/bin/env python3
"""回归测试：check-ai-visibility.py（L1.5 采集与统计）。

跑法：python test_check_ai_visibility.py
退出码：0 = 全部通过。

测试用一个**本地假引擎**（内联 python -c），不联网、不花钱。
覆盖：默认 prompt 不含品牌、collect 落盘、失败计入分母、提及判定不被前缀名误伤、
score 输出带 n 且不出现"排名"、--strict 门槛、缺文件 exit 2。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CHILD_ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
# 子进程也不写 __pycache__，避免污染技能目录

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-ai-visibility.py")

# 假引擎：读到含 "pick" 的 prompt 就提到 Acme，否则不提；加 --fail 时模拟失败。
FAKE = ('python -c "import sys,json; d=json.loads(sys.stdin.readline()); '
        'p=d[\'prompt\'].lower(); '
        'a=(\'I recommend Acme for that.\' if \'pick\' in p else \'Consider other options.\'); '
        'print(json.dumps({\'answer\':a,\'citations\':[\'https://acme.example/\'] if \'Acme\' in a else []}))"')

FAKE_FAIL_HALF = ('python -c "import sys,json; d=json.loads(sys.stdin.readline()); '
                  'sys.exit(1) if d[\'run\']==1 and \'Compare\' in d[\'prompt\'] else None; '
                  'print(json.dumps({\'answer\':\'I recommend Acme.\',\'citations\':[]}))"')


def invoke_cli(args):
    return subprocess.run([sys.executable, SCRIPT] + args, env=CHILD_ENV, capture_output=True,
                          text=True, encoding="utf-8")


def case_prompts_print():
    proc = invoke_cli(["prompts"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count(". ") >= 5, proc.stdout
    assert "品牌名" in proc.stdout, proc.stdout
    return True


def case_collect_and_score():
    d = tempfile.mkdtemp()
    try:
        obs = os.path.join(d, "obs.jsonl")
        proc = invoke_cli(["collect", "--cmd", FAKE, "--brand", "Acme", "--engine", "fake",
                    "--runs", "1", "--out", obs])
        assert proc.returncode == 0, proc.stderr
        assert os.path.isfile(obs), "观测文件未生成"
        n = sum(1 for line in open(obs, encoding="utf-8") if line.strip())
        assert n == 5, f"应有 5 条观测，实际 {n}"

        out = invoke_cli(["score", "--obs", obs, "--brand", "Acme", "--json"])
        payload = json.loads(out.stdout)
        assert payload["observations"] == 5, payload
        assert payload["valid"] == 5, payload
        assert payload["mentions"] == 1, f"只有 pick 那条应提及: {payload}"
        assert "排名" in payload["discipline"], payload
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_failure_counted_in_denominator():
    d = tempfile.mkdtemp()
    try:
        obs = os.path.join(d, "obs.jsonl")
        invoke_cli(["collect", "--cmd", FAKE_FAIL_HALF, "--brand", "Acme", "--engine", "fake",
             "--runs", "1", "--out", obs])
        out = invoke_cli(["score", "--obs", obs, "--brand", "Acme", "--json"])
        payload = json.loads(out.stdout)
        assert payload["errors"] == 1, f"失败应计 1 条: {payload}"
        assert payload["valid"] == 4, payload
        assert payload["observations"] == 5, "总观测应含失败"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_word_boundary_mention():
    """Acme 不该命中 Acmecorp / Acme2 / xAcme。"""
    d = tempfile.mkdtemp()
    try:
        obs = os.path.join(d, "obs.jsonl")
        rows = [
            dict(engine="e", prompt="p1", invoke_cli=1, brand="Acme", ok=True,
                 answer="We like Acmecorp and Acme2 and xAcme.", citations=[]),
            dict(engine="e", prompt="p2", invoke_cli=1, brand="Acme", ok=True,
                 answer="We like Acme.", citations=[]),
        ]
        with open(obs, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        out = invoke_cli(["score", "--obs", obs, "--brand", "Acme", "--json"])
        payload = json.loads(out.stdout)
        assert payload["mentions"] == 1, f"只应命中整词那一条: {payload}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_brand_in_prompt_rejected():
    d = tempfile.mkdtemp()
    try:
        proc = invoke_cli(["collect", "--cmd", FAKE, "--brand", "Acme", "--engine", "fake",
                    "--prompt", "Is Acme good?", "--runs", "1",
                    "--out", os.path.join(d, "o.jsonl")])
        assert proc.returncode == 2, f"prompt 含品牌名应 exit 2，实际 {proc.returncode}"
        assert "[error]" in proc.stderr, proc.stderr
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_strict_threshold():
    d = tempfile.mkdtemp()
    try:
        obs = os.path.join(d, "obs.jsonl")
        invoke_cli(["collect", "--cmd", FAKE, "--brand", "Acme", "--engine", "fake",
             "--runs", "1", "--out", obs])
        code = invoke_cli(["score", "--obs", obs, "--brand", "Acme", "--strict",
                    "--min-rate", "0.9"]).returncode
        assert code == 1, f"提及率 0.2 < 0.9 应退出 1，实际 {code}"
        code2 = invoke_cli(["score", "--obs", obs, "--brand", "Acme", "--strict",
                     "--min-rate", "0.1"]).returncode
        assert code2 == 0, f"提及率 0.2 >= 0.1 应退出 0，实际 {code2}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_missing_obs_exits_2():
    d = tempfile.mkdtemp()
    try:
        proc = invoke_cli(["score", "--obs", os.path.join(d, "nope.jsonl"), "--brand", "Acme"])
        assert proc.returncode == 2, proc.returncode
        assert "[error]" in proc.stderr, proc.stderr
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_output_says_not_ranking():
    d = tempfile.mkdtemp()
    try:
        obs = os.path.join(d, "obs.jsonl")
        invoke_cli(["collect", "--cmd", FAKE, "--brand", "Acme", "--engine", "fake",
             "--runs", "1", "--out", obs])
        out = invoke_cli(["score", "--obs", obs, "--brand", "Acme"]).stdout
        assert "不是排名" in out or "不得写成排名" in out or "提及率" in out, out
        assert "第 1 名" not in out and "排名第" not in out, out
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    cases = [case_prompts_print, case_collect_and_score,
             case_failure_counted_in_denominator, case_word_boundary_mention,
             case_brand_in_prompt_rejected, case_strict_threshold,
             case_missing_obs_exits_2, case_output_says_not_ranking]
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
