#!/usr/bin/env python3
"""check-ai-visibility.py — L1.5 生成式可提及性（离线可复现版）。

背景：`ai-era.md` §4 定义了三引擎 × 5 条买家 prompt × 3 次 = 45 次观测的方法，
但一直只有方法没有脚本。本脚本把**方法本身**固化下来，并要求调用方自带凭据与
一个"回答生成器"——技能包不代付 API 费用，也不内置任何厂商 SDK。

设计：**采集与统计分离**。
  collect   调外部命令拿回答，落成 observations.jsonl（每条：引擎/prompt/run/回答）
  score     读 jsonl，算提及/前三/引用，强制带 n，禁止输出"排名"

外部命令契约（`--cmd`，任何厂商都能接）：
  命令从 stdin 读一行 JSON：{"prompt": "...", "engine": "...", "run": 1}
  往 stdout 写一行 JSON：{"answer": "...", "citations": ["https://..."]}
  非 0 退出 = 该次观测失败，记为 error（**不静默丢弃**，计入分母并在报告里单列）

为什么不让脚本直接调 API：凭据不该写进技能包；且不同厂商的回包结构差异极大，
把"取回答"这一层交给用户自己的 5 行脚本，比内置任何 SDK 都更稳。

用法:
  python check-ai-visibility.py collect --cmd "python my_llm.py" --brand Acme \
      --engine gpt --engine claude --engine gemini --runs 3 --out obs.jsonl
  python check-ai-visibility.py score --obs obs.jsonl --brand Acme [--json] [--strict]
  python check-ai-visibility.py prompts            # 打印默认 5 条买家 prompt

退出码：0 正常；--strict 且"提及率 < 阈值"时 1；参数/文件错误 2。
依赖：`_common.py`（同目录）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import atomic_write  # noqa: E402

# 默认 5 条"买家式"prompt：**不含任何品牌名**，否则等于给被追踪品牌开后门。
DEFAULT_PROMPTS = [
    "What tools do people actually use for {category}?",
    "Which {category} product should I pick for a small team?",
    "Compare the top options for {category} in 2025.",
    "I need something for {category} that is easy to start with. What do you suggest?",
    "What are the alternatives people mention for {category}?",
]

PROMPT_BAN = re.compile(r"\b(the best|top 10|ranked|ranking)\b", re.I)


def parse_args():
    ap = argparse.ArgumentParser(description="L1.5 生成式可提及性采集与统计")
    # 注意：dest 不能叫 cmd —— collect 子命令里有 --cmd 选项，同名会被覆盖
    sub = ap.add_subparsers(dest="sub", required=True)

    p_c = sub.add_parser("collect", help="调外部命令采集回答")
    p_c.add_argument("--cmd", required=True, help="外部回答生成命令（见文件头契约）")
    p_c.add_argument("--brand", required=True)
    p_c.add_argument("--category", default="this kind of software")
    p_c.add_argument("--engine", action="append", required=True, help="引擎名，可重复")
    p_c.add_argument("--runs", type=int, default=3)
    p_c.add_argument("--prompt", action="append", default=None,
                     help="自定义 prompt（可重复；默认用内置 5 条，{category} 会被替换）")
    p_c.add_argument("--out", default="observations.jsonl")
    p_c.add_argument("--timeout", type=int, default=120)

    p_s = sub.add_parser("score", help="统计提及率（带 n，不出排名）")
    p_s.add_argument("--obs", required=True)
    p_s.add_argument("--brand", required=True)
    p_s.add_argument("--json", action="store_true")
    p_s.add_argument("--out", default=None)
    p_s.add_argument("--strict", action="store_true")
    p_s.add_argument("--min-rate", type=float, default=0.0,
                     help="--strict 下要求的最低提及率（0-1），默认 0 即不做门槛")

    sub.add_parser("prompts", help="打印默认 5 条买家 prompt")
    return ap.parse_args()


def build_prompts(custom, category):
    src = custom if custom else DEFAULT_PROMPTS
    out = []
    for p in src:
        text = p.replace("{category}", category).strip()
        if PROMPT_BAN.search(text):
            print(f"[warn] prompt 含排名类字眼，会诱导模型复述榜单而非自发提及：{text}", file=sys.stderr)
        out.append(text)
    return out


def check_prompts_do_not_leak_brand(prompts, brand):
    """prompt 里出现被追踪品牌名 = 数据无效（等于直接问它）。"""
    bad = [p for p in prompts if brand.lower() in p.lower()]
    if bad:
        print(f"[error] prompt 含被追踪品牌名 “{brand}”，会污染观测：{bad[0]}", file=sys.stderr)
        return False
    return True


def call_engine(cmd, prompt, engine, run, timeout):
    payload = json.dumps({"prompt": prompt, "engine": engine, "run": run}, ensure_ascii=False)
    try:
        proc = subprocess.run(cmd, shell=True, input=payload + "\n", capture_output=True,
                              text=True, encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(error="timeout")
    if proc.returncode != 0:
        return dict(error=f"exit {proc.returncode}: {(proc.stderr or '')[:200]}")
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        return dict(error="empty stdout")
    try:
        reply = json.loads(line[-1])
    except json.JSONDecodeError:
        return dict(error=f"非 JSON 输出: {line[-1][:160]}")
    if "answer" not in reply:
        return dict(error="缺少 answer 字段")
    return dict(answer=str(reply["answer"]), citations=reply.get("citations") or [])


def cmd_collect(args):
    prompts = build_prompts(args.prompt, args.category)
    if not check_prompts_do_not_leak_brand(prompts, args.brand):
        return 2

    records = []
    total = len(prompts) * len(args.engine) * args.runs
    done = 0
    for engine in args.engine:
        for prompt in prompts:
            for run in range(1, args.runs + 1):
                res = call_engine(args.cmd, prompt, engine, run, args.timeout)
                rec = dict(engine=engine, prompt=prompt, run=run,
                           brand=args.brand, ok="error" not in res)
                rec.update(res)
                records.append(rec)
                done += 1
                if "error" in res:
                    print(f"[warn] {engine} run{run}: {res['error'][:80]}", file=sys.stderr)
                print(f"  {done}/{total}", file=sys.stderr)

    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    atomic_write(args.out, text + "\n")
    errs = sum(1 for r in records if not r["ok"])
    print(f"写入 {args.out}：{len(records)} 条（失败 {errs} 条，失败也计入分母）")
    return 0


def mentions(text, brand):
    """品牌提及判定：大小写不敏感的整词匹配（避免 Acme 命中 Acmecorp）。"""
    if not text:
        return False
    pat = r"(?<![A-Za-z0-9])" + re.escape(brand) + r"(?![A-Za-z0-9])"
    return re.search(pat, text, re.I) is not None


def cmd_score(args):
    if not os.path.isfile(args.obs):
        print(f"[error] 找不到观测文件 {args.obs}", file=sys.stderr)
        return 2
    records = []
    with open(args.obs, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"[warn] 跳过无法解析的行：{line[:80]}", file=sys.stderr)

    if not records:
        print("[error] 观测文件为空", file=sys.stderr)
        return 2

    brand = args.brand
    obs = len(records)
    errors = sum(1 for r in records if not r.get("ok", True))
    valid = [r for r in records if r.get("ok", True)]
    hit = [r for r in valid if mentions(r.get("answer", ""), brand)]
    cited = [r for r in hit if any(brand.lower() in (c or "").lower() for c in (r.get("citations") or []))]
    first3 = [r for r in hit if r["answer"].lower().index(brand.lower()) < max(120, len(r["answer"]) // 4)]

    by_engine = {}
    for r in valid:
        e = r.get("engine", "?")
        b = by_engine.setdefault(e, dict(n=0, hit=0))
        b["n"] += 1
        if mentions(r.get("answer", ""), brand):
            b["hit"] += 1

    rate = len(hit) / len(valid) if valid else 0.0
    result = dict(brand=brand, observations=obs, valid=len(valid), errors=errors,
                  mentions=len(hit), in_first_quarter=len(first3), cited=len(cited),
                  mention_rate=round(rate, 4), by_engine=by_engine,
                  discipline="只能报提及率与 n；不得写成排名；跨厂商分数不可比")

    if args.json:
        text = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        lines = [
            f"生成式可提及性 — {brand}",
            "-" * 60,
            f"提及 {len(hit)}/{len(valid)} 次"
            f"（总观测 {obs}，其中失败 {errors} 条仍计入分母）",
            f"其中 出现靠前 {len(first3)} 次、被引用 {len(cited)} 次",
            f"提及率 {rate:.1%}",
        ]
        if by_engine:
            lines.append("分引擎：")
            for e, b in sorted(by_engine.items()):
                r = b["hit"] / b["n"] if b["n"] else 0
                lines.append(f"  {e}: {b['hit']}/{b['n']}（{r:.0%}）")
        lines += [
            "",
            "纪律：以上是**提及率**，不是排名；不同厂商分母/采样不同，分数不可横向比较；",
            "单次快照不可用作趋势（同 prompt 重复运行结果方差极大，见 references/ai-era.md §4）。",
        ]
        if errors:
            lines.append(f"注意：{errors} 条采集失败已计入分母，若失败集中在某一引擎，该引擎的比率不可用。")
        text = "\n".join(lines)

    if args.out:
        atomic_write(args.out, text + "\n")
    else:
        print(text)

    if args.strict and args.min_rate > 0 and rate < args.min_rate:
        return 1
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = parse_args()
    if args.sub == "prompts":
        for i, p in enumerate(DEFAULT_PROMPTS, 1):
            print(f"{i}. {p}")
        print("\n用 --category 替换 {category}；这些 prompt 都不含品牌名（防止直接问到自己）。")
        return 0
    if args.sub == "collect":
        return cmd_collect(args)
    return cmd_score(args)


if __name__ == "__main__":
    sys.exit(main())
