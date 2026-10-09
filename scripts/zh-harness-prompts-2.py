#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 2 轮：harness 提示词中文化（运行环境块 / Bot 模式块 / 小常量 / 时区）。
幂等；每文件备份 .bak-zh-harness（与第 1 轮共用同一备份）。
"""
import os, pathlib, re, shutil, subprocess, sys

# ── 定位 Hermes 安装树（自动探测；可用环境变量 HERMES_ROOT 覆盖）──
def _find_src() -> pathlib.Path:
    cands = []
    v = os.environ.get("HERMES_ROOT")
    if v:
        cands += [pathlib.Path(v), pathlib.Path(v) / "hermes-agent"]
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA")
        if la:
            cands.append(pathlib.Path(la) / "hermes" / "hermes-agent")
    cands += [
        pathlib.Path.home() / ".hermes" / "hermes-agent",
        pathlib.Path.home() / ".local" / "share" / "hermes" / "hermes-agent",
    ]
    for c in cands:
        if (c / "agent" / "prompt_builder.py").exists():
            return c
    raise SystemExit(
        "找不到 Hermes 安装树（应含 agent/prompt_builder.py）；"
        "请用环境变量指定：HERMES_ROOT=<hermes 数据目录或 hermes-agent 目录>"
    )


SRC = _find_src()
PY = SRC / "venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
if not PY.exists():
    PY = pathlib.Path(sys.executable)
CJK = re.compile(r"[\u4e00-\u9fff]")


def find_const_block(text, name):
    """NAME = (...) 或 NAME = "..." 的整块区间。"""
    m = re.search(rf"^{re.escape(name)}\s*(?::[^=\n]+)?=\s*", text, re.M)
    if not m:
        return None
    i = m.start()
    k = m.end()
    if k < len(text) and text[k] == "(":
        j = k; depth = 0
        while j < len(text):
            if text[j] == "(": depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0: return i, j + 1
            j += 1
        return None
    if k < len(text) and text[k] == '"':
        j = k + 1
        while j < len(text) and text[j] != '"': j += 1
        return i, j + 1
    return None


CONST_FIXES = {
    "agent/prompt_builder.py": {
        "_WINDOWS_BASH_SHELL_HINT": r'''_WINDOWS_BASH_SHELL_HINT = (
    "Shell：在这台 Windows 机器上，你的 `terminal` 工具通过 bash（git-bash / MSYS）执行命令，不是 PowerShell，"
    "也不是 cmd.exe。terminal 调用里请用 POSIX shell 语法（`ls`、`$HOME`、`&&`、`|`、单引号字符串）。"
    "MSYS 风格路径（如 `/c/Users/<user>/...`）与原生 `C:\\Users\\<user>\\...` 路径可同时使用。PowerShell "
    "内建命令（`Get-ChildItem`、`$env:FOO`、`Select-String`）不可用——改用对应的 POSIX 写法（`ls`、"
    "`$FOO`、`grep`）。给「原生 Windows 程序」（git、rg、node、python 等）传路径参数时不会做转换：MSYS "
    "路径转换这里已关闭，所以 `git -C /c/Users/x` 或 `node /tmp/a.js` 会报 'cannot change to'/'not "
    "found'，尽管 `cd /c/Users/x`（bash 内建）能用。给原生工具请传 `C:/Users/x` 这种正斜杠原生路径；"
    "原生工具必须读取的临时文件优先放 `$LOCALAPPDATA/Temp`（或 `$TMPDIR`，Hermes 已把它指向自家的 scratch 目录）"
    "——绝不要用裸的 `/tmp`。在 pty 后台进程里回答提示符时，用 process(submit)——不要用 process(write) 带一个"
    "孤立的结尾换行：Windows PTY 上的 Enter 是回车符，单独的 `\\n` 不会被当作行终止符，子进程的提示符会静默地"
    "永不返回。CLI 提供非交互路径时（flags、`--with-token`、配置文件、用 curl 轮询的 OAuth 设备码流程），"
    "优先用它，而不是去驱动交互提示。"
)''',
        "SESSION_SEARCH_GUIDANCE": r'''SESSION_SEARCH_GUIDANCE = (
    "当用户提到过去某次对话里的东西、或你怀疑存在相关的跨会话上下文时，先用 session_search 回忆起来，"
    "不要让用户重复一遍。"
)''',
        "SKILLS_GUIDANCE": r'''SKILLS_GUIDANCE = (
    "当你摸索出一套非平凡的工作流时，用 skill_manage 记下来，供以后复用。\n\n"
    f"{SKILL_SAFETY_HEADING}\n"
    "含 `[SKILL_PRUNED]` 占位的技能，是内容在上下文压缩中丢失、已无法读取的——在依赖它做任何事之前，"
    "先用 skill_view(name='...') 重新加载。重新加载后，忽略该技能残留的 `[SKILL_PRUNED]` 标记；"
    "它们是更早的压缩留下的历史痕迹。"
)''',
        # ⚠ 注意：SKILL_SAFETY_HEADING（「## Skill Safety Rule」）有意保持英文、不翻——
        # hermes_cli/sessions_cmd.py 用它匹配（历史）system_prompt 以探测技能块（repair 路径）；
        # 译成中文后，中文标题匹配不上「翻译前生成的英文标题」，会误报「技能块缺失」。故此条不翻。
    },
}

SNIPPET_FIXES = [
    ("agent/prompt_builder.py",
     '    host_lines = [f"Host: {host}", f"User home directory: {os.path.expanduser(\'~\')}"]',
     '    host_lines = [f"主机: {host}", f"用户主目录: {os.path.expanduser(\'~\')}"]', True),
    ("agent/prompt_builder.py",
     '        host_lines.append(f"Current working directory: {resolve_agent_cwd()}")',
     '        host_lines.append(f"当前工作目录: {resolve_agent_cwd()}")', False),
    ("agent/prompt_builder.py",
     '''        host_lines.append(f"Scratch directory: {get_scratch_dir()} (TMPDIR points here; write temporary files "
                          "and probes there, never under the system temp dir; entries idle for 24h are pruned)")''',
     '''        host_lines.append(f"临时目录: {get_scratch_dir()}（TMPDIR 指向这里；临时文件与探测脚本写在这，不要用系统临时目录；"
                          "闲置 24 小时的条目会被清理）")''', False),
    ("agent/prompt_builder.py",
     '''        "Note: on Windows, the machine hostname (e.g. from `hostname` or uname) is NOT the username. "
        "Use the 'User home directory' above to construct paths under C:\\\\Users\\\\<user>\\\\, never the hostname."''',
     '''        "注意：在 Windows 上，机器名（如 `hostname` 或 uname 得到的）不是用户名。"
        "构造 C:\\\\Users\\\\<user>\\\\ 下的路径时，请用上面的「用户主目录」，绝不要用机器名。"''', False),
    ("agent/system_prompt.py",
     '        timestamp_line = f"Timezone: {\', \'.join(_bits)}" if _bits else ""',
     '        timestamp_line = f"时区: {\', \'.join(_bits)}" if _bits else ""', False),
    # ── bot_mode_probe.py ──
    ("tools/bot_mode_probe.py",
     '_PROTOCOL_HEADING = "## Messaging other agents"',
     '_PROTOCOL_HEADING = "## 与其他机器人互通消息"', False),
    ("tools/bot_mode_probe.py",
     '''        "\\n\\nTeammates on OTHER connected machines (reachable through the "
        "Desktop relay — message them with message_agent exactly like local "
        "teammates; replies arrive as completion notifications the same "
        "way, or via reply_delivery=\\\"poll\\\" as below):\\n" + "\\n".join(lines)''',
     '''        "\\n\\n在其他已连接机器上的队友（经 Desktop relay 可达——用 message_agent 发消息，方式与本地队友完全相同；"
        "回复同样以完成通知送达，或按下文说的 reply_delivery=\\\"poll\\\"）：\\n" + "\\n".join(lines)''', False),
    ("tools/bot_mode_probe.py",
     '''        "\\n\\nTeammates on OTHER machines: this install also has peer gateways "
        f"registered ({listed}). Message an agent on a peer the same way — "
        'message_agent with target "<peer>/<agent-name>" (or "<peer>" alone '
        "for the peer's main agent). Run `hermes peer list` for the live "
        "peer list."''',
     '''        "\\n\\n其他机器上的队友：本机还注册了 peer 网关"
        f"（{listed}）。给 peer 上的 agent 发消息方式相同——"
        'message_agent 的 target 填 "<peer>/<agent-name>"（或只写 "<peer>" '
        "发给该 peer 的主 agent）。运行 `hermes peer list` 查看实时 peer 列表。\""''', False),
    ("tools/bot_mode_probe.py",
     '''        f"{_PROTOCOL_HEADING}\\n"
        "This install runs Bot Mode: each Hermes profile is an agent teammate with "
        'one canonical "Bot Chat" conversation, and you have the `message_agent` '
        "tool to DM any of them. It is FIRE-AND-FORGET: it delivers your message "
        "with your attribution prefixed automatically and returns an acknowledgement "
        "immediately — it never returns the reply. Send it, finish your turn, and "
        "the reply arrives later as a background-process completion notification "
        "that wakes you; relay it to the user then, attributed to that agent — unless "
        "the ack returns reply_delivery=\\\"poll\\\", in which case follow its "
        "process(action=\\\"wait\\\") instruction before ending the turn. "
        "COMPOSE every message yourself — say what YOU need from that agent; never "
        "forward the user's words verbatim, and never reveal private 1:1 chat "
        "content. When the user says \\\"ask <name>\\\" or \\\"tell <name> ...\\\", that is "
        "a handoff: pick the right teammate from the roster below, message them "
        "with message_agent, and report back naming which agent replied. Message "
        "ONE clearly relevant teammate; don't fan out to several unless the user "
        "explicitly asked.\\n"
        f'When YOU receive a "Message from 🤖 <name> (@<handle>):" message, a '
        "teammate agent is talking to you (not the user): address them, reply "
        "concisely via message_agent to their handle, and if it is a pure FYI "
        "with nothing to add, staying silent is fine — never ping-pong "
        "acknowledgements.\\n"
        f"You are `@{_handle(me)}`. Your teammates (live roster; roles from their "
        "profiles):\\n"''',
     '''        f"{_PROTOCOL_HEADING}\\n"
        "本机开启了 Bot Mode：每个 Hermes profile 都是一名机器人队友，各自有一条规范的主对话「Bot Chat」；"
        "你有 `message_agent` 工具，可以私信其中任何一个。它是「发出即忘」的：投递时自动带上你的署名，"
        "并立刻返回一个回执——但它永远不会把对方的回复带回来。发出、结束你的回合；对方的回复稍后会以"
        "「后台进程完成通知」的形式送达并唤醒你——届时把它转述给用户，并注明是哪个机器人回的。"
        "除非回执返回 reply_delivery=\\\"poll\\\"，那就照它给的 process(action=\\\"wait\\\") 指示，等完再结束回合。"
        "每条消息都必须自己组织——说清「你」需要对方做什么；绝不把用户的原话照抄转发，也绝不泄露私聊内容。"
        "当用户说「问一下 <名字>」或「告诉 <名字> ……」时，那是交接：从下面的名单里挑准队友，用 message_agent 发过去，"
        "回报时说明是哪个机器人回复的。只发给一个明确相关的队友；除非用户明说要广泛问，不要群发多人。\\n"
        f'当「你」收到「Message from 🤖 <名字> (@<handle>):」这样的消息时，说明是一个机器人队友在跟你说话（不是用户）：'
        "用 message_agent 回复对应 handle，简洁作答；如果纯属告知、没什么可补充的，保持安静即可——绝不要来回互发客套确认。\\n"
        f"你是 `@{_handle(me)}`。你的队友（实时名单；角色取自各自的 profile）：\\n"''', False),
    ("tools/bot_mode_probe.py",
     '    roster_block = "\\n".join(roster_lines) or "- (no teammates yet)"',
     '    roster_block = "\\n".join(roster_lines) or "- （暂无队友）"', False),
]


def main():
    check_only = "--check" in sys.argv
    log = []
    changed = set()
    for rel, consts in CONST_FIXES.items():
        f = SRC / rel
        t = f.read_text(encoding="utf-8", errors="replace")
        for name, new in consts.items():
            span = find_const_block(t, name)
            if not span:
                log.append(f"  ⚠ {rel}: {name} 未找到"); continue
            block = t[span[0]:span[1]]
            if CJK.search(block):
                log.append(f"  = {name}: 已是中文，跳过"); continue
            log.append(f"  ✅ {name}: 替换（{len(block)} → {len(new)} 字）")
            if not check_only:
                t = t[:span[0]] + new + t[span[1]:]
                changed.add(rel)
        if rel in changed and not check_only:
            bak = f.with_suffix(f.suffix + ".bak-zh-harness")
            if not bak.exists(): shutil.copy2(f, bak)
            f.write_text(t, encoding="utf-8", newline="")

    for rel, old, new, allx in SNIPPET_FIXES:
        f = SRC / rel
        t = f.read_text(encoding="utf-8", errors="replace")
        tag = old.strip().splitlines()[0][:58]
        if old not in t:
            # 判断是否已翻：取 new 里第一段连续中文（≥3 字）做特征串、去空白后比对。
            # （不能只看 new 首行——如 bot_mode 段的 new 首行是 f-string 引用行、不含中文。）
            m = re.search(r"[一-鿿]{2,}", new)
            if m and m.group(0) in re.sub(r"[\s]", "", t):
                log.append(f"  = [{tag}]: 已是中文，跳过"); continue
            log.append(f"  ⚠ [{tag}]: 未命中"); continue
        n = t.count(old) if allx else 1
        log.append(f"  ✅ [{tag}]: 替换 ×{n}")
        if not check_only:
            t = t.replace(old, new) if allx else t.replace(old, new, 1)
            changed.add(rel)
            bak = f.with_suffix(f.suffix + ".bak-zh-harness")
            if not bak.exists(): shutil.copy2(f, bak)
            f.write_text(t, encoding="utf-8", newline="")

    for rel in changed:
        p = subprocess.run([str(PY), "-m", "py_compile", str(SRC / rel)], capture_output=True, text=True)
        if p.returncode != 0:
            log.append(f"  ✗ {rel} 语法错误 → 回滚: {p.stderr[:220]}")
            shutil.copy2((SRC / rel).with_suffix((SRC / rel).suffix + ".bak-zh-harness"), SRC / rel)
        else:
            log.append(f"  ✓ {rel} 语法检查通过")
    print("\n".join(log) or "无需改动")


if __name__ == "__main__":
    main()
