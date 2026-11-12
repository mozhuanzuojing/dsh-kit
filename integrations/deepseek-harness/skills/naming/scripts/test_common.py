#!/usr/bin/env python3
"""回归测试：_common.py（脚本公共模块）。

跑法：python test_common.py
退出码：0 = 全部通过。

重点测 `atomic_write`：它是"CI 读到半截文件"这个故障的唯一防线，
所以必须验证——写入成功、失败时不留残骸、目标原内容不被破坏。
"""
import io
import os
import shutil
import sys
import tempfile
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _common  # noqa: E402


def case_tokenize():
    got = _common.tokenize("getUserName")
    assert got == ["get", "user", "name"], got
    assert _common.tokenize("get_user_name") == ["get", "user", "name"]
    assert _common.tokenize("GET-USER-NAME") == ["get", "user", "name"]
    assert _common.tokenize("HTTPResponse") == ["http", "response"], _common.tokenize("HTTPResponse")
    assert _common.tokenize("") == []
    return True


def case_strip_sep_and_singular():
    assert _common.strip_sep("_UserName") == "username"
    assert _common.strip_sep("user-name") == "username"
    assert _common.singular("users") == "user"
    assert _common.singular("policies") == "policy"
    assert _common.singular("classes") == "class"
    assert _common.singular("status") == "status", "ss 结尾不该被砍"
    return True


def case_edit_distance():
    assert _common.edit_distance_le1("agentName", "agentNames")
    assert _common.edit_distance_le1("abc", "abd")
    assert not _common.edit_distance_le1("abc", "xyz")
    assert not _common.edit_distance_le1("a", "abcd")
    assert _common.edit_distance_le1("", "a")
    return True


def case_script_profile():
    latin, cjk, other = _common.script_profile("Acme")
    assert (latin, cjk, other) == (4, 0, 0), (latin, cjk, other)
    latin, cjk, other = _common.script_profile("字节跳动")
    assert latin == 0 and cjk == 4, (latin, cjk, other)
    latin, cjk, other = _common.script_profile("Glidely笔记")
    assert latin == 7 and cjk == 2, (latin, cjk, other)
    return True


def case_atomic_write_creates():
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "out.txt")
        _common.atomic_write(p, "hello\n")
        assert io.open(p, encoding="utf-8").read() == "hello\n"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_atomic_write_replaces_without_leftovers():
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "out.txt")
        _common.atomic_write(p, "old\n")
        _common.atomic_write(p, "new\n")
        assert io.open(p, encoding="utf-8").read() == "new\n"
        leftovers = [f for f in os.listdir(d) if f != "out.txt"]
        assert not leftovers, f"残留临时文件: {leftovers}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_atomic_write_keeps_original_on_failure():
    """写入失败时，目标文件的**原内容必须保持完整**（这是原子性的核心）。"""
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "out.txt")
        _common.atomic_write(p, "original\n")
        try:
            _common.atomic_write(p, object())  # 非字符串 → f.write 抛 TypeError
        except TypeError:
            pass
        else:
            raise AssertionError("应当抛出 TypeError")
        assert io.open(p, encoding="utf-8").read() == "original\n", "失败后原文件被破坏"
        leftovers = [f for f in os.listdir(d) if f != "out.txt"]
        assert not leftovers, f"失败后残留临时文件: {leftovers}"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_atomic_write_no_trailing_newline_added():
    """不要偷偷改变内容（写入什么就是什么）。"""
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "out.txt")
        _common.atomic_write(p, "abc")
        assert io.open(p, encoding="utf-8").read() == "abc"
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    cases = [case_tokenize, case_strip_sep_and_singular, case_edit_distance,
             case_script_profile, case_atomic_write_creates,
             case_atomic_write_replaces_without_leftovers,
             case_atomic_write_keeps_original_on_failure,
             case_atomic_write_no_trailing_newline_added]
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
