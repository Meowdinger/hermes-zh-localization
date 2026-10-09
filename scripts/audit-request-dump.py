#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量 Hermes 请求转储（request_dump_*.json）的语言构成——「中文化」的验收工具。

背景：Hermes 设置环境变量 HERMES_DUMP_REQUESTS=1 后，每次发给模型的请求都会把
完整请求体写成该 profile 的 sessions/request_dump_*.json。本脚本解析它，把
「系统提示 / 工具定义 / 对话消息」分块，报告各块的中文（CJK）与英文字母占比
和估算 token——用来验收中文化效果、并定位剩余英文的大头。

用法：
    python audit-request-dump.py <dump.json> [更多 json...]
    python audit-request-dump.py <目录>                  # 跑目录里最新的 3 个
    python audit-request-dump.py <dump.json> --sections  # 附系统提示分节排行
    python audit-request-dump.py <dump.json> --top 20    # 排行长度（默认 15）

只依赖标准库。
"""
import json
import pathlib
import re
import sys
import time

CJK = re.compile(r"[\u4e00-\u9fff]")
ALPHA = re.compile(r"[A-Za-z]")
HEADING = re.compile(r"\n(?=#{1,2} )")


def load_body(path: pathlib.Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    body = (d.get("request") or {}).get("body") or d.get("body") or {}
    if isinstance(body, str):  # 部分版本 body 是二次编码的字符串
        body = json.loads(body)
    return d, body


def counts(s: str):
    return len(CJK.findall(s)), len(ALPHA.findall(s))


def est_tokens(s: str) -> float:
    """粗估 token（用于前后对比即可）：CJK×0.6 + 字母×0.25 + 其余×0.15。"""
    cjk, alpha = counts(s)
    other = max(0, len(s) - cjk - alpha)
    return cjk * 0.6 + alpha * 0.25 + other * 0.15


def zh_ratio(s: str) -> str:
    cjk, alpha = counts(s)
    t = cjk + alpha
    return f"{cjk / t * 100:.1f}%" if t else "—"


def split_blocks(body: dict):
    msgs = body.get("messages") or []
    tools = body.get("tools") or []
    system = ""
    convo = []
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list):
            c = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in c
            )
        c = c or ""
        if m.get("role") == "system" and not system and not convo:
            system = c
        else:
            convo.append(c)
    return system, json.dumps(tools, ensure_ascii=False), "".join(convo)


def report(path: pathlib.Path, sections: bool, top: int) -> None:
    try:
        d, body = load_body(path)
    except Exception as e:  # noqa: BLE001
        print(f"== {path.name}\n   ⚠ 解析失败: {e}\n")
        return
    ts = d.get("timestamp")
    if isinstance(ts, (int, float)):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    system, tools_s, convo = split_blocks(body)
    print(f"== {path.name}")
    if ts:
        print(f"   时间: {ts}")
    for name, s in (("系统提示", system), ("工具定义", tools_s), ("对话消息", convo)):
        cjk, alpha = counts(s)
        print(
            f"   {name}: {len(s):>9,} 字符 | 中文占比 {zh_ratio(s):>6} | "
            f"字母 {alpha:>8,} | ≈{est_tokens(s):>8,.0f} tok"
        )
    print(f"   整包估算: ≈{est_tokens(system + tools_s + convo):,.0f} tok")
    if sections and system:
        parts = [p for p in HEADING.split(system) if p.strip()]
        rows = sorted(parts, key=lambda p: len(ALPHA.findall(p)), reverse=True)[:top]
        print(f"   ── 系统提示分节（按英文字母数 top {top}）──")
        for p in rows:
            cjk, alpha = counts(p)
            head = p.strip().splitlines()[0][:64]
            print(f"     {alpha:>7,} 字母 / {cjk:>6,} 中文 | {head}")
    print()


def main() -> None:
    argv = sys.argv[1:]
    top = 15
    if "--top" in argv:
        i = argv.index("--top")
        top = int(argv[i + 1])
        del argv[i : i + 2]
    sections = "--sections" in argv
    args = [a for a in argv if not a.startswith("--")]
    files = []
    for a in args:
        p = pathlib.Path(a)
        if p.is_dir():
            newest = sorted(
                p.glob("request_dump_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            files += newest[:3]
        else:
            files.append(p)
    if not files:
        print(__doc__)
        sys.exit(2)
    for f in files:
        report(f, sections, top)


if __name__ == "__main__":
    main()
