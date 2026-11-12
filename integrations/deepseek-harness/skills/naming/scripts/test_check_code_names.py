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
        _, payload, err = invoke_checker_json([d, "--engine", engine, "--no-repo"])
        if payload.get("engine") != engine:
            # 引擎没真正跑起来（未安装/降级）：这是环境限制，不是通过，也不是缺陷
            assert "[warn]" in err, f"[{engine}] 引擎降级但无警告: {err!r}"
            return None
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


# 故意写坏的样例：覆盖函数名 / 变量名 / 否定式布尔 / 缩写，且全部是**声明节点**
# （函数形参不在 AST_DECL_SPECS 里，任何引擎都不该报，别把它写进期望）
BAD_SAMPLE_TS = (
    "export function processData(input: any) {\n"
    "  const userObj = {};\n"
    "  const req = input;\n"
    "  const isNotReady = false;\n"
    "  return userObj, req, isNotReady;\n"
    "}\n"
)
BAD_EXPECTED = {"processData", "userObj", "req", "isNotReady"}


def case_bad_sample_never_false_green(engine):
    """反假绿：坏名样例在每个引擎下都必须报出问题。

    背景：旧 CLI 引擎调用 `sg run --kind`（该子命令没有 --kind），每个 kind 都失败后被
    `continue` 吞掉 → 抽取结果为空 → findings=0 → 输出“未发现明显命名问题”。
    这个用例锁死那条路径：引擎只要跑了就必须有结论，不许静默通过。
    引擎不可用而真实降级时**必须**有 [warn]，此时该引擎的断言跳过（环境限制 ≠ 通过）。
    """
    d = tempfile.mkdtemp()
    try:
        write(d, "bad.ts", BAD_SAMPLE_TS)
        code, payload, err = invoke_checker_json([d, "--engine", engine, "--no-repo"])
        assert code == 0, f"[{engine}] 退出码异常 {code}: {err[:200]}"
        if payload.get("engine") != engine:
            # 明确降级：必须留痕，然后跳过（不把环境缺失算成"引擎合格"）
            assert "[warn]" in err, f"[{engine}] 引擎降级但无警告: {err!r}"
            return None
        got = {f["name"] for f in payload["findings"]}
        missing = BAD_EXPECTED - got
        assert not missing, (f"[{engine}] 坏名样例漏检 {sorted(missing)}；"
                             f"engine字段={payload.get('engine')} err={err[:200]!r}")
        # 逐文件 engine 标注必须与实际引擎一致（降级过的文件不能沿用全局引擎名）
        labels = {f.get("engine") for f in payload["findings"]}
        assert labels == {engine}, f"[{engine}] findings 的 engine 标注不一致: {labels}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_cli_engine_actually_extracts():
    """CLI 引擎必须真的抽取到声明（而不是 0 条后靠正则兜底冒充）。

    直接比对 JSON 里的逐文件 engine 标注：只要 CLI 可用且规则跑通，
    findings 的 engine 就必须是 ast-grep-cli；否则说明回退发生了。
    """
    if not (shutil.which("ast-grep") or shutil.which("sg")):
        return None
    d = tempfile.mkdtemp()
    try:
        write(d, "bad.java", (
            "public class Bad {\n"
            "    private String req;\n"
            "    public void processData(String reqId) { }\n"
            "}\n"))
        code, payload, err = invoke_checker_json([d, "--engine", "ast-grep-cli", "--no-repo"])
        assert code == 0, f"退出码异常 {code}: {err[:200]}"
        assert payload["findings"], f"CLI 引擎 0 findings（假绿）: {payload}"
        engines = {f.get("engine") for f in payload["findings"]}
        assert engines == {"ast-grep-cli"}, f"findings 未标注为 CLI 引擎: {engines}, err={err[:200]!r}"
        names = {f["name"] for f in payload["findings"]}
        # 方法声明必须被抽取到：正则引擎在 Java 上抽不到 processData 这个名字
        assert "processData" in names, f"CLI 未抽取到方法声明: {sorted(names)}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_cli_engine_matches_regex_recall():
    """CLI 引擎的召回不得低于正则引擎（同一份坏名样例）。"""
    if not (shutil.which("ast-grep") or shutil.which("sg")):
        return None
    d = tempfile.mkdtemp()
    try:
        write(d, "bad.ts", BAD_SAMPLE_TS)
        _, cli_payload, _ = invoke_checker_json([d, "--engine", "ast-grep-cli", "--no-repo"])
        _, rx_payload, _ = invoke_checker_json([d, "--engine", "regex", "--no-repo"])
        cli_names = {(f["name"], f["rule"]) for f in cli_payload["findings"]}
        rx_names = {(f["name"], f["rule"]) for f in rx_payload["findings"]}
        missing = rx_names - cli_names
        assert not missing, f"CLI 引擎比正则丢结果: {sorted(missing)}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_cli_annotations_and_comments(engine):
    """CLI 引擎在带注解/注释的声明上取名必须正确。

    两个真实缺陷（在 424 个 Java 文件的语料上暴露）：
      · `@Transactional(...)` 被当成「标识符后跟 (」→ 方法名取成 Transactional；
      · 函数体注释 `// TODO Auto-generated method stub` 里的 "method stub" 命中关键字规则
        → 方法名取成 stub，真实方法名 doInsert 完全漏检。
    两者都表现为「名字错了/漏了」，但 findings 数不为 0，所以只有断言具体名字才抓得住。
    """
    if engine == "regex":
        return None                     # 正则引擎没有片段取名问题
    if not (shutil.which("ast-grep") or shutil.which("sg")):
        return None
    d = tempfile.mkdtemp()
    try:
        write(d, "Annotated.java", (
            "public class Annotated {\n"
            "    @Override\n"
            "    @Transactional(rollbackFor = Exception.class)\n"
            "    public void doFlowClearResult(String flowId) throws Exception {\n"
            "        // TODO Auto-generated method stub\n"
            "        return;\n"
            "    }\n"
            "    public void doInsert(String data) {\n"
            "        /* method stub */\n"
            "    }\n"
            "}\n"))
        _, payload, err = invoke_checker_json([d, "--engine", engine, "--no-repo"])
        if payload.get("engine") != engine:
            return None
        names = {f["name"] for f in payload["findings"]}
        assert "Transactional" not in names, f"[{engine}] 注解名被当成声明名: {sorted(names)}"
        assert "stub" not in names, f"[{engine}] 注释文本被当成声明名: {sorted(names)}"
        assert "doFlowClearResult" in names, f"[{engine}] 注解方法名漏检: {sorted(names)}"
        assert "doInsert" in names, f"[{engine}] 注释后的方法名漏检: {sorted(names)}"
        # 行号必须指向真实声明行（不带注解前缀的那一行）
        line_of = {f["name"]: f["line"] for f in payload["findings"]}
        assert line_of.get("doFlowClearResult") == 4, \
            f"[{engine}] 注解方法行号应指向声明行 4，实际 {line_of.get('doFlowClearResult')}"
        assert line_of.get("doInsert") == 8, \
            f"[{engine}] 方法行号应指向声明行 8，实际 {line_of.get('doInsert')}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    results = []
    for engine in ("ast-grep-py", "ast-grep-cli", "regex"):
        for fn in (case_multidecl, case_java_calls, case_jsx, case_bad_sample_never_false_green,
                   case_cli_annotations_and_comments):
            try:
                ok = fn(engine)
                results.append((fn.__name__, engine, "SKIP" if ok is None else "PASS", ""))
            except AssertionError as e:
                results.append((fn.__name__, engine, "FAIL", str(e)[:220]))
            except Exception as e:  # noqa: BLE001
                results.append((fn.__name__, engine, "ERROR", f"{type(e).__name__}: {e}"[:220]))

    for fn in (case_near_name, case_short_name_noise, case_rename_tiers,
               case_framework_override, case_unsupported_single_file, case_zero_scan,
               case_strict_exit, case_degraded_engine_reports,
               case_cli_engine_actually_extracts, case_cli_engine_matches_regex_recall):
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
