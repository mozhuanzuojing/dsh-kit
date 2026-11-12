#!/usr/bin/env python3
"""回归测试：check-cross-layer.py（跨层命名一致性）。

跑法：python test_check_cross_layer.py
退出码：0 = 全部通过。

覆盖：init 骨架自身干净、三宗陷阱各自能报出、时长的 API/DB 差异化、audit 作用域、
--strict 退出码、参数错误退出码。
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
SCRIPT = os.path.join(HERE, "check-cross-layer.py")


def invoke_cli(args):
    proc = subprocess.run([sys.executable, SCRIPT] + args, env=CHILD_ENV, capture_output=True,
                          text=True, encoding="utf-8")
    return proc.returncode, proc.stdout, proc.stderr


def invoke_cli_json(args):
    code, out, err = invoke_cli(args + ["--json"])
    try:
        return code, json.loads(out), err
    except json.JSONDecodeError:
        raise AssertionError(f"非 JSON: {out[:300]} / {err[:300]}")


def rules(payload):
    return {f["rule"] for f in payload["findings"]}


MAP_HEADER = ("| 概念 | API 字段 | DB 列 | 事件属性 | 指标/属性 | 配置 key | 备注 |\n"
              "|---|---|---|---|---|---|---|\n")


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def case_init_template_is_clean():
    d = tempfile.mkdtemp()
    try:
        out = os.path.join(d, "m.md")
        code, so, se = invoke_cli(["init", "--out", out])
        assert code == 0, f"init 失败: {se}"
        code, payload, _ = invoke_cli_json(["check", "--map", out])
        assert payload["findings"] == [], f"骨架自身不干净: {payload['findings']}"
        assert payload["concepts"] >= 3, payload
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_init_refuses_overwrite():
    d = tempfile.mkdtemp()
    try:
        out = os.path.join(d, "m.md")
        invoke_cli(["init", "--out", out])
        code, _, err = invoke_cli(["init", "--out", out])
        assert code == 2, f"已存在却不拒绝覆盖: {code}"
        assert "--force" in err, err
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_tense_conflict():
    d = tempfile.mkdtemp()
    try:
        m = os.path.join(d, "m.md")
        write(m, MAP_HEADER + "| 创建时间 | published_time | created_at | time | — | — | |\n")
        _, payload, _ = invoke_cli_json(["check", "--map", m])
        assert "tense_conflict" in rules(payload), payload
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_is_prefix_conflict():
    d = tempfile.mkdtemp()
    try:
        m = os.path.join(d, "m.md")
        write(m, MAP_HEADER + "| 布尔状态 | is_disabled | disabled | enabled | — | — | |\n")
        _, payload, _ = invoke_cli_json(["check", "--map", m])
        hit = [f for f in payload["findings"] if f["rule"] == "is_prefix_conflict"]
        assert len(hit) == 2, f"应同时报 API 与 DB 两侧: {hit}"
        assert {h["layer"] for h in hit} == {"api", "db"}, hit
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_duration_api_vs_db():
    """AIP-142：API 层用 Duration 类型，名字不带单位 → 不报；DB/配置层必须带 → 报。"""
    d = tempfile.mkdtemp()
    try:
        m = os.path.join(d, "m.md")
        write(m, MAP_HEADER + "| 超时 | timeout | timeout | duration | — | TIMEOUT | |\n")
        _, payload, _ = invoke_cli_json(["check", "--map", m])
        hits = [f for f in payload["findings"] if f["rule"] == "unit_missing"]
        layers = {h["layer"] for h in hits}
        assert "api" not in layers, f"API 层不该报单位（用 Duration）: {hits}"
        assert {"db", "config"} <= layers, f"DB/配置层应报: {hits}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_measure_needs_unit_in_api():
    """AIP-141：度量字段（size/distance）在 API 层也要带单位。"""
    d = tempfile.mkdtemp()
    try:
        m = os.path.join(d, "m.md")
        write(m, MAP_HEADER + "| 容量 | size | size_bytes | — | — | MAX_SIZE_BYTES | |\n")
        _, payload, _ = invoke_cli_json(["check", "--map", m])
        hits = [f for f in payload["findings"] if f["rule"] == "unit_missing"]
        assert any(h["layer"] == "api" for h in hits), f"度量在 API 层应报单位: {hits}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_malformed_row():
    d = tempfile.mkdtemp()
    try:
        m = os.path.join(d, "m.md")
        write(m, MAP_HEADER + "| 只有两列 | x |\n")
        _, payload, _ = invoke_cli_json(["check", "--map", m])
        assert "row_malformed" in rules(payload), payload
        assert any(f["severity"] == "Critical" for f in payload["findings"]), payload
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_strict_exit():
    d = tempfile.mkdtemp()
    try:
        m = os.path.join(d, "m.md")
        write(m, MAP_HEADER + "| 创建时间 | published_time | created_at | time | — | — | |\n")
        code, _, _ = invoke_cli(["check", "--map", m, "--strict"])
        assert code == 1, f"--strict 未因 Major 退出 1: {code}"
        ok = os.path.join(d, "ok.md")
        invoke_cli(["init", "--out", ok])
        code2, _, _ = invoke_cli(["check", "--map", ok, "--strict"])
        assert code2 == 0, f"干净的骨架不该退出 1: {code2}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_missing_map_exits_2():
    d = tempfile.mkdtemp()
    try:
        code, _, err = invoke_cli(["check", "--map", os.path.join(d, "nope.md")])
        assert code == 2, f"缺表应 exit 2，实际 {code}"
        assert "[error]" in err, err
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_audit_scope():
    """audit 默认只扫 schema 源；--include-code 才扫普通源码。"""
    d = tempfile.mkdtemp()
    try:
        m = os.path.join(d, "m.md")
        write(m, MAP_HEADER + "| 创建时间 | create_time | created_at | time | — | — | |\n")
        src = os.path.join(d, "src")
        os.makedirs(src)
        write(os.path.join(src, "a.py"), "mysterious_counter = 1\n")
        _, p1, _ = invoke_cli_json(["audit", "--map", m, "--code", src])
        assert not p1["findings"], f"默认不该扫 .py: {p1['findings']}"
        _, p2, _ = invoke_cli_json(["audit", "--map", m, "--code", src, "--include-code"])
        assert any(f["rule"] == "unmapped_identifier" for f in p2["findings"]), p2
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    cases = [case_init_template_is_clean, case_init_refuses_overwrite,
             case_tense_conflict, case_is_prefix_conflict, case_duration_api_vs_db,
             case_measure_needs_unit_in_api, case_malformed_row, case_strict_exit,
             case_missing_map_exits_2, case_audit_scope]
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
