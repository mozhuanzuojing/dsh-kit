#!/usr/bin/env python3
"""回归测试：check-ui-names.py（界面文案 / 无障碍 / i18n）。

跑法：python test_check_ui_names.py
退出码：0 = 全部通过。

成对用例：该报的必须报，**合规的写法必须不误报**（比"能报"更重要）。
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
SCRIPT = os.path.join(HERE, "check-ui-names.py")


def invoke_cli(args):
    return subprocess.run([sys.executable, SCRIPT] + args, env=CHILD_ENV, capture_output=True,
                          text=True, encoding="utf-8")


def judge(files):
    """files: {name: content} → 返回 {rule: [findings]}。"""
    d = tempfile.mkdtemp()
    try:
        for name, content in files.items():
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) != d else None
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        proc = invoke_cli([d, "--json"])
        assert proc.returncode == 0, f"退出码异常 {proc.returncode}: {proc.stderr[:200]}"
        payload = json.loads(proc.stdout)
        out = {}
        for f in payload["findings"]:
            out.setdefault(f["rule"], []).append(f)
        return out
    finally:
        shutil.rmtree(d, ignore_errors=True)


def has(rules, name):
    return bool(rules.get(name))


def case_generic_button():
    r = judge({"a.html": "<button>确定</button><button>Submit</button>"})
    got = {f["evidence"].lower() for f in r.get("generic_button", [])}
    assert "确定" in got and "submit" in got, f"两个泛化按钮都应命中（evidence 保留原样，比较时归一）: {got}"
    return True


def case_good_buttons_not_flagged():
    """带对象的动词不该被误报。"""
    r = judge({"a.html": "<button>保存更改</button><button>发布</button>"
                         "<button>永久删除 3 个文件</button>"})
    assert not has(r, "generic_button"), f"合规按钮被误报: {r.get('generic_button')}"
    assert not has(r, "danger_no_scope"), f"带范围的危险操作被误报: {r.get('danger_no_scope')}"
    return True


def case_danger_without_scope():
    r = judge({"a.html": "<button>删除</button><button>清空</button>"})
    got = {f["evidence"] for f in r.get("danger_no_scope", [])}
    assert {"删除", "清空"} <= got, r
    return True


def case_aria_generic_and_empty():
    r = judge({"a.html": '<button aria-label="删除">x</button>'
                         '<button aria-label="">y</button>'
                         '<button aria-label="删除订单 #1024">z</button>'})
    generic = [f["evidence"].lower() for f in r.get("aria_generic", [])]
    assert "删除" in generic, r
    assert has(r, "icon_no_label"), "空 aria-label 应报 icon_no_label"
    assert "删除订单 #1024" not in generic, "带对象的 aria-label 被误报"
    return True


def case_empty_state():
    r = judge({"a.html": "<div>暂无数据</div>"})
    assert has(r, "empty_state"), r
    good = judge({"a.html": "<div>还没有项目。点击「新建项目」开始。</div>"})
    assert not has(good, "empty_state"), f"合规空态被误报: {good.get('empty_state')}"
    return True


def case_vague_error():
    r = judge({"a.html": "<span>出错了</span><span>Something went wrong</span>"})
    assert has(r, "vague_error"), r
    good = judge({"a.html": "<span>无法保存：文件名包含 / 字符。改名后重试。</span>"})
    assert not has(good, "vague_error"), f"合规错误文案被误报: {good.get('vague_error')}"
    return True


def case_design_token():
    r = judge({"a.css": ":root{--color-red:#f00;--color-danger:#d00;--color-success:#0a0}"})
    got = [f["evidence"] for f in r.get("token_appearance", [])]
    assert "--color-red" in got, r
    assert "--color-danger" not in got, "语义令牌被误报"
    return True


def case_i18n_key():
    r = judge({"a.json": '{"orders.empty.title": "x", "noDataText": "y", "订单 标题": "z"}'})
    got = [f["evidence"] for f in r.get("i18n_key_text", [])]
    assert "orders.empty.title" not in got, f"合规 key 被误报: {got}"
    assert any("noDataText" in g for g in got), f"值式 key 未报: {got}"
    assert any("订单" in g for g in got), f"含中文的 key 未报: {got}"
    return True


def case_strict_exit():
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "a.html"), "w", encoding="utf-8") as f:
            f.write("<button>确定</button>")
        code = invoke_cli([d, "--strict"]).returncode
        assert code == 1, f"--strict 未因 Major 退出 1: {code}"
        with open(os.path.join(d, "ok.html"), "w", encoding="utf-8") as f:
            f.write("<button>保存更改</button>")
        code2 = invoke_cli([os.path.join(d, "ok.html"), "--strict"]).returncode
        assert code2 == 0, f"干净文件不该退出 1: {code2}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_unsupported_exits_2():
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "a.zzz"), "w", encoding="utf-8") as f:
            f.write("x")
        proc = invoke_cli([d])
        assert proc.returncode == 2, f"无受支持文件应 exit 2，实际 {proc.returncode}"
        assert "[error]" in proc.stderr, proc.stderr
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_scan_filter():
    """--scan aria 时不应报 CSS/按钮类问题。"""
    r = judge({"a.html": "<button>确定</button><button aria-label='删除'>x</button>"})
    assert has(r, "generic_button"), r
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "a.html"), "w", encoding="utf-8") as f:
            f.write("<button>确定</button><button aria-label='删除'>x</button>")
        payload = json.loads(invoke_cli([d, "--scan", "aria", "--json"]).stdout)
        rules = {f["rule"] for f in payload["findings"]}
        assert "generic_button" not in rules, f"--scan aria 不该报按钮: {rules}"
        assert "aria_generic" in rules, rules
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    cases = [case_generic_button, case_good_buttons_not_flagged, case_danger_without_scope,
             case_aria_generic_and_empty, case_empty_state, case_vague_error,
             case_design_token, case_i18n_key, case_strict_exit,
             case_unsupported_exits_2, case_scan_filter]
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
