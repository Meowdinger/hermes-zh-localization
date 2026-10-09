"""把注入到 prompt 里的"技能包装"英文串改成中文（Secretary · 2026-10-07）

背景：用户发现调用技能时 Hermes 会注入英文前缀（如
`[IMPORTANT: The user has invoked the "X" skill, ...]`），导致 DeepSeek 跟着用英文思考。
这些串在 agent/skill_commands.py 等处以硬编码英文写死（未走 i18n）。本脚本逐处替换为中文，
并同步更新与之绑定的"标记常量"（源码注释明确要求二者保持逐字节一致）。

安全性：先备份 .bak-lang-zh → 替换 → py_compile 校验；失败则回滚。
不改：多技能 bundle 路径、纯展示用串（blast radius 控制）。
"""
import os, pathlib, shutil, subprocess, sys

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

EDITS = {
    "agent/skill_commands.py": [
        # ── 标记常量（必须与构造串一致）──
        ('_SKILL_INVOCATION_PREFIX = "[IMPORTANT: The user has invoked the "',
         '_SKILL_INVOCATION_PREFIX = "[重要：用户已调用 "'),
        ('_SINGLE_SKILL_MARKER = "The full skill content is loaded below.]"',
         '_SINGLE_SKILL_MARKER = "完整技能内容已加载在下方。]"'),
        ('_SINGLE_SKILL_INSTRUCTION = "The user has provided the following instruction alongside the skill invocation: "',
         '_SINGLE_SKILL_INSTRUCTION = "用户在调用该技能时附带了以下指令："'),
        ('_AUTO_LOAD_PREFIX = \'[IMPORTANT: The "\'',
         '_AUTO_LOAD_PREFIX = \'[重要：技能 "\''),
        (r'''_AUTO_LOAD_SUFFIX_RE = re.compile(r'" skill is auto-loaded\. Follow its instructions for this session\.\]')''',
         r'''_AUTO_LOAD_SUFFIX_RE = re.compile(r'" 已自动加载。本会话内请按其说明执行。\]')'''),
        ('_SKILL_DIR_NOTE_END = "then run them with the terminal tool using the absolute path."',
         '_SKILL_DIR_NOTE_END = "再用 terminal 工具以绝对路径运行它们。"'),
        # ── 技能目录脚注 ──
        ('''_SKILL_DIR_NOTE = (
    "Resolve any relative paths in this skill (e.g. `scripts/foo.js`, "
    "`templates/config.yaml`) against that directory, then run them "
    "with the terminal tool using the absolute path."
)''',
         '''_SKILL_DIR_NOTE = (
    "本技能里出现的相对路径（例如 `scripts/foo.js`、`templates/config.yaml`）"
    "都相对上面那个目录解析，再用 terminal 工具以绝对路径运行它们。"
)'''),
        # ── setup 跳过提示 ──
        ('''_SETUP_SKIPPED_NOTE = (
    "Required environment setup was skipped. Continue loading the skill "
    "and explain any reduced functionality if it matters."''',
         '''_SETUP_SKIPPED_NOTE = (
    "所需的环境准备被跳过了。照常加载该技能，"
    "若因此功能受限且确有影响，就向用户说明。"'''),
        # ── 单技能调用注记（桌面/CLI 最常见）──
        ('''    note = (f'[IMPORTANT: The user has invoked the "{loaded[2]}" skill, indicating they want '
            "you to follow its instructions. The full skill content is loaded below.]")''',
         '''    note = (f'[重要：用户已调用 "{loaded[2]}" 技能，希望你按其说明执行。'
            "完整技能内容已加载在下方。]")'''),
        # ── CLI 预加载注记 ──
        ('''        lambda name: (f'[IMPORTANT: The user launched this CLI session with the "{name}" skill '
                      "preloaded. Treat its instructions as active guidance for the duration of this "
                      "session unless the user overrides them.]"),''',
         '''        lambda name: (f'[重要：用户以 "{name}" 技能预加载启动了本 CLI 会话。'
                      "本会话期间请把它的说明当作有效指引，除非用户另有指示。]"),'''),
        # ── skills.auto_load 自动加载注记 ──
        ('''            lambda name: (f'[IMPORTANT: The "{name}" skill is auto-loaded via config (skills.auto_load). '
                          "Treat its instructions as active guidance for the duration of this session unless "
                          "the user overrides them.]"),''',
         '''            lambda name: (f'[重要：技能 "{name}" 已通过配置自动加载（skills.auto_load）。'
                          "本会话期间请把它的说明当作有效指引，除非用户另有指示。]"),'''),
        # ── 技能配置头 ──
        ('        parts.append(f"[Skill config (from {display_hermes_home()}/config.yaml):")',
         '        parts.append(f"[技能配置（来自 {display_hermes_home()}/config.yaml）：")'),
    ],
    "gateway/run_turn.py": [
        ('''                    f'[IMPORTANT: The "{_display_name}" skill is auto-loaded. '
                    f"Follow its instructions for this session.]",''',
         '''                    f'[重要：技能 "{_display_name}" 已自动加载。'
                    f"本会话内请按其说明执行。]",'''),
    ],
    "cron/scheduler_prompt.py": [
        ('''            f'[IMPORTANT: The user has invoked the "{skill_name}" skill, indicating they want you to follow its instructions. The full skill content is loaded below.]',''',
         '''            f'[重要：用户已调用 "{skill_name}" 技能，希望你按其说明执行。完整技能内容已加载在下方。]','''),
    ],
}

def main():
    log = []
    changed = []
    for rel, pairs in EDITS.items():
        f = SRC / rel
        txt = f.read_text(encoding="utf-8", errors="strict")
        orig = txt
        hits = 0
        for old, new in pairs:
            if new in txt:
                log.append(f"  {rel}: 已是中文，跳过一处")
                continue
            if old not in txt:
                log.append(f"  ⚠ {rel}: 未命中 → {old.strip()[:70]}")
                continue
            txt = txt.replace(old, new, 1)
            hits += 1
        if txt != orig:
            bak = f.with_suffix(f.suffix + ".bak-lang-zh")
            if not bak.exists():
                shutil.copy2(f, bak)
            f.write_text(txt, encoding="utf-8", newline="")
            changed.append(rel)
            log.append(f"  ✅ {rel}: 替换 {hits} 处（备份 {bak.name}）")

    # 语法校验；失败即回滚
    for rel in changed:
        f = SRC / rel
        p = subprocess.run([str(PY), "-m", "py_compile", str(f)], capture_output=True, text=True)
        if p.returncode != 0:
            log.append(f"  ✗ {rel} 语法错误 → 回滚：{p.stderr[:200]}")
            shutil.copy2(f.with_suffix(f.suffix + ".bak-lang-zh"), f)
        else:
            log.append(f"  ✓ {rel} 语法检查通过")

    print("\n".join(log))

if __name__ == "__main__":
    main()
