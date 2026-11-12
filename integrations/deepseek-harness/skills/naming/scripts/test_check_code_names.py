#!/usr/bin/env python3
"""回归测试：check-code-names.py 的三层引擎、三大旧缺陷与仓库级聚合。

跑法（在任意目录）：python test_check_code_names.py
退出码：0 = 全部通过；1 = 有失败。

设计意图：这个脚本是**自校验**的——技能声称"能查命名问题"，就必须先证明自己没有退化。
覆盖：
  1. 旧缺陷 A：一行多声明只看第一个（`const a = 1, b = 2, req = 3;`）
  2. 旧缺陷 B：Java 调用行被误判成声明
  3. 旧缺陷 C：TSX 组件与普通函数不可分（小写组件名应报 component_case）
  4. 仓库级近名（near_name）与短名降噪
  5. 重命名影响面三档（auto / manual / risky）
  6. 框架覆写名豁免（do_GET）
  7. 失败透明：不支持的扩展名 → exit 2；零扫描 → 明确告警而非"通过"
  8. --strict 在 Critical 时退出 1
  9. 引擎降级必须打印警告（不静默）
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
SCRIPT = os.path.join(HERE, "check-code-names.py")


def invoke_checker(args):
    proc = subprocess.run([sys.executable, SCRIPT] + args, env=CHILD_ENV, capture_output=True,
                          text=True, encoding="utf-8")
    return proc.returncode, proc.stdout, proc.stderr


def invoke_checker_json(args):
    code, out, err = invoke_checker(args + ["--json"])
    try:
        return code, json.loads(out), err
    except json.JSONDecodeError:
        raise AssertionError(f"非 JSON 输出: {out[:300]} / {err[:300]}")


def write(tmpdir, name, content):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return path


def case_multidecl(engine):
    """旧缺陷 A：一行多声明只看第一个。"""
    d = tempfile.mkdtemp()
    try:
        write(d, "a.ts", "const a = 1, b = 2, req = 3;\n")
        _, payload, _ = invoke_checker_json([d, "--engine", engine, "--no-repo"])
        names = {f["name"] for f in payload["findings"] if f["rule"] == "abbreviation"}
        assert "req" in names, f"[{engine}] 一行多声明漏检 req: {payload}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_java_calls(engine):
    """旧缺陷 B：Java 调用行被当成声明（只应报真实方法声明那行）。"""
    d = tempfile.mkdtemp()
    try:
        write(d, "Sample.java", (
            "public class Sample {\n"
            "    private int count;\n"
            "    public void process(int x) {\n"
            "        helper(req);\n"
            "        this.process(1);\n"
            "    }\n"
            "    private void helper(Object o) {}\n"
            "}\n"))
        _, payload, _ = invoke_checker_json([d, "--engine", engine, "--no-repo"])
        vague = [f for f in payload["findings"] if f["rule"] == "vague_verb"]
        assert vague, f"[{engine}] 漏掉真实的 process 方法声明: {payload}"
        assert all(f["line"] == 3 for f in vague), \
            f"[{engine}] 调用行被误判成声明（应只在第 3 行）: {vague}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_jsx(engine):
    """旧缺陷 C：TSX 组件与普通函数不可分（正则引擎不承诺，跳过）。"""
    if engine == "regex":
        return None
    d = tempfile.mkdtemp()
    try:
        write(d, "Card.tsx", (
            "export function UserCard() { return <div/>; }\n"
            "export function renderRow() { return <span/>; }\n"
            "export function computeTotal() { return 1; }\n"))
        _, payload, _ = invoke_checker_json([d, "--engine", engine, "--no-repo"])
        comp = {f["name"] for f in payload["findings"] if f["rule"] == "component_case"}
        assert "renderRow" in comp, f"[{engine}] 未把小写 JSX 组件判为 component_case: {payload}"
        assert "UserCard" not in comp, f"[{engine}] PascalCase 组件被误报: {payload}"
        assert "computeTotal" not in comp, f"[{engine}] 普通函数被当成组件: {payload}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_near_name():
    d = tempfile.mkdtemp()
    try:
        write(d, "near.ts", "const agentNameList = 1;\nconst agentNameLists = 2;\n")
        _, payload, _ = invoke_checker_json([d, "--engine", "regex"])
        assert any(f["rule"] == "near_name" for f in payload["findings"]), payload
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_short_name_noise():
    """短名（<5 字符）不做编辑距离近名，避免 kids/kinds 噪声。"""
    d = tempfile.mkdtemp()
    try:
        write(d, "short.py", "kids = 1\nkinds = 2\n")
        _, payload, _ = invoke_checker_json([d, "--engine", "regex"])
        assert not [f for f in payload["findings"] if f["rule"] == "near_name"], payload
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_rename_tiers():
    d = tempfile.mkdtemp()
    try:
        write(d, "m.py", (
            "# oldName documented\n"
            "class oldName:\n"
            "    pass\n"
            "def use():\n"
            "    v = oldName()\n"
            "    return v, {'oldName': 1}\n"))
        _, payload, _ = invoke_checker_json([d, "--rename", "oldName=newName"])
        tiers = {f["rule"] for f in payload["findings"] if f["rule"].startswith("rename_")}
        assert {"rename_auto", "rename_manual", "rename_risky"} <= tiers, payload
        assert payload.get("rename", {}).get("risky") == 1, payload.get("rename")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_framework_override():
    d = tempfile.mkdtemp()
    try:
        write(d, "h.py", "class H:\n    def do_GET(self):\n        return 1\n")
        _, payload, _ = invoke_checker_json([d, "--engine", "regex", "--no-repo"])
        assert not [f for f in payload["findings"] if f["rule"] == "vague_verb"], payload
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_unsupported_single_file():
    """单文件扩展名不支持 → exit 2（不静默成功）。"""
    d = tempfile.mkdtemp()
    try:
        path = write(d, "a.zzz", "whatever\n")
        code, out, err = invoke_checker([path])
        assert code == 2, f"未知扩展名单文件应以 2 退出，实际 {code}"
        assert "[error]" in err and "不支持的扩展名" in err, f"err={err!r}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_zero_scan():
    """目录里没有可扫描文件 → 告警 + 明确"不是检查通过"。"""
    d = tempfile.mkdtemp()
    try:
        write(d, "a.zzz", "whatever\n")
        code, out, err = invoke_checker([d])
        assert code == 0
        assert "未扫描到任何受支持的文件" in err or "不受支持" in err, f"空扫描未告警: {err!r}"
        assert "这不是" in out, f"空扫描被静默读成通过: {out!r}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_strict_exit():
    d = tempfile.mkdtemp()
    try:
        write(d, "s.ts", "const userID = 1;\nconst userId = 2;\n")
        code, out, _ = invoke_checker([d, "--engine", "regex", "--strict"])
        assert code == 1, f"--strict 未因 Critical 退出 1: {code} {out[:200]}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_degraded_engine_reports():
    """请求 ast-grep-py 但不可用时必须打印降级警告（本机已装则跳过）。"""
    code, out, err = invoke_checker([SCRIPT, "--engine", "ast-grep-py"])
    if "引擎=ast-grep-py" in out:
        return None
    assert "[warn]" in err, f"降级无警告: {err!r}"
    return True


def main():
    results = []
    for engine in ("ast-grep-py", "regex"):
        for fn in (case_multidecl, case_java_calls, case_jsx):
            try:
                ok = fn(engine)
                results.append((fn.__name__, engine, "SKIP" if ok is None else "PASS", ""))
            except AssertionError as e:
                results.append((fn.__name__, engine, "FAIL", str(e)[:220]))
            except Exception as e:  # noqa: BLE001
                results.append((fn.__name__, engine, "ERROR", f"{type(e).__name__}: {e}"[:220]))

    for fn in (case_near_name, case_short_name_noise, case_rename_tiers,
               case_framework_override, case_unsupported_single_file, case_zero_scan,
               case_strict_exit, case_degraded_engine_reports):
        try:
            ok = fn()
            results.append((fn.__name__, "-", "SKIP" if ok is None else "PASS", ""))
        except AssertionError as e:
            results.append((fn.__name__, "-", "FAIL", str(e)[:220]))
        except Exception as e:  # noqa: BLE001
            results.append((fn.__name__, "-", "ERROR", f"{type(e).__name__}: {e}"[:220]))

    width = max(len(r[0]) for r in results)
    failed = 0
    for name, engine, status, detail in results:
        print(f"{name:<{width}}  {engine:<11}  {status:<5}  {detail}")
        if status in ("FAIL", "ERROR"):
            failed += 1
    print(f"\n{len(results) - failed}/{len(results)} 通过，{failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
