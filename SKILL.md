---
name: hermes-zh-localization
description: "把 Hermes 注入大模型的英文提示词翻成中文：盘点、批量改、验收与升级重放。"
version: 0.1.0
author: meowdinger, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Localization, Chinese, Prompt, Harness, i18n]
    category: autonomous-ai-agents
---

# Hermes 中文化（harness 提示词 → 中文）

把 Hermes 发给大模型请求里的英文内容（系统提示、工具说明、技能包装、技能索引）批量翻成中文，让模型「用中文想、用中文答」。本技能给出整套流程、幂等补丁脚本、注入面地图与验收工具；换其他语言时原理相同（把替换对换成目标语言即可）。在真实多 bot 环境（9 个 profile）实战验证过。

## When to Use

- 模型在英文思考/回复（或中文表现被英文上下文拉低），想把 Hermes 或某个 profile 的提示词中文化。
- `hermes update` 覆盖源码后，要**重放**已有的中文化补丁。
- 要评估「上传给模型的请求里还剩多少英文、大头在哪」。

**Don't use for**：翻译第三方技能/用户内容；改 show 层的 i18n 文案（`display.language`）——那是另一件事，本方法针对「硬编码、不进 i18n 的注入提示词」。

## 五个注入面（先认全，再动手）

| # | 注入面 | 主要位置 |
|---|---|---|
| 1 | 技能包装（调用技能时注入的前后缀） | `agent/skill_commands.py`、`gateway/run_turn.py`、`cron/scheduler_prompt.py` |
| 2 | 系统提示正文 | `agent/prompt_builder.py`、`agent/system_prompt.py`、`agent/oneshot_footprint.py`、`tools/bot_mode_probe.py` |
| 3 | 工具定义（description 全文） | `tools/*_tool.py` 的 `*_SCHEMA` / `*_TOOL_DESCRIPTION` |
| 4 | 技能分类描述 | `skills/*/DESCRIPTION.md`（每 profile 一份） |
| 5 | 技能描述行（进每会话技能索引） | 所有 `SKILL.md` 的 frontmatter `description` |

逐常量的完整清单、危险区、验证细节在 **`references/harness-prompt-map.md`——动手前先读它**。

## 怎么跑

### A. 用本仓库脚本重放（推荐）

```bash
python scripts/zh-skill-wrappers.py       # 第 0 轮：技能包装（14 处）
python scripts/zh-harness-prompts.py      # 第 1 轮：系统提示主常量
python scripts/zh-harness-prompts-2.py    # 第 2 轮：运行环境块 / Bot 模式块 / 小常量 / 时区
```

三个脚本都**幂等**：按常量名/片段定位；已含中文的跳过、找不到的报警；每文件备份（`.bak-zh-*`）、改完 `py_compile` 校验、失败自动回滚。`--check` 只对账不改动。脚本自动探测 Hermes 安装树（`%LOCALAPPDATA%\hermes\hermes-agent`、`~/.hermes/hermes-agent` 等；`HERMES_ROOT` 可覆盖）。

### B. 同版本一键补丁

`patches/zh-harness-2026-10-09.patch` 为 v0.21.x（2026-10）全量 diff（38 文件）：

```bash
cd <hermes-agent 源码树>
git apply --3way <patches/zh-harness-2026-10-09.patch>
```

### C. 全新版本/更大范围

按 `references/harness-prompt-map.md` 的清单逐面处理。工具定义这类「×N 重复件」可派子代理批量翻，但**交付后必须自己复验**（全量编译 + schema 键名零改动 + 真实工具调用冒烟）。

## 改完必做：重启常驻进程

Python 进程启动即把模块载入内存——**不重启不生效**。要重启：

- 桌面 App（其后端随它一起重启）；
- `hermes gateway run`（计划任务托管，**不随 App 重启**）；
- 各 `hermes serve`（如 `--isolated` 起的固定口后端；看门狗托管的杀进程等自愈即可）。

判定「哪份代码在跑」：比对补丁文件 `LastWriteTime` 与进程 `StartTime`——进程早于补丁 = 还是旧代码。

## 验收（真实上传测量，不写测试桩）

```bash
# 打开转储开关：每次请求把完整请求体写到该 profile 的 sessions/request_dump_*.json
HERMES_DUMP_REQUESTS=1 hermes -p <profile> chat -q "只回复：1" --oneshot

# 量占比 + 定位剩余英文大头
python scripts/audit-request-dump.py <...>/sessions/ --sections
```

实测参考（本机 24h profile，翻前 → 翻后）：系统提示中文占比 2.3% → 54.7%；工具定义 0.0% → 42.1%；整包估算 ≈16.5K → ≈12.1K tok。

## 铁律与坑（血换的）

1. **危险区先 `grep -rn '<常量名>'` 看引用再动**：`SKILL_SAFETY_HEADING`、`RUNTIME_ENVIRONMENT_HEADING`、`CONTROL_FRAME_OPENERS` 等被运行时逻辑按**英文文本**匹配——保持英文（完整表在 references）。翻错会让检测/剥除逻辑静默失配（不报错、行为变暗）。
2. **「标记常量」与构造/解析串逐字节同步**：技能包装的前缀/后缀与其正则是一对（源码注释写死该约束），改一个必须同步另一个，并复核会话标题/预览解析未坏。
3. **英文子串匹配器要同步**：如 `model_tools.py` 对工具描述做英文文本替换/修剪——对应文案翻掉后匹配器会失效；翻译时一并改匹配器（中文变体在前、保留旧英文变体兼容）。
4. **对既有文件用 `patch` 定点替换**，别整体重写（Hermes 的 `write_file` 对既有文件会拒绝，这是信号不是 bug）；批量重复件（技能副本 ×N）才用 Python 脚本 + 命中计数。
5. **`py_compile` 挡语法错，挡不住「引号地狱」**：写「生成替换对的脚本」时，三引号字符串里的引号/转义极易被剥一层——写完先编译、再 `--check` 对账；发现「未命中」先查记录是否过时，别硬修。
6. **协议串保持英文**：steer 标记、控制帧等跨组件（含桌面端 TS）字节匹配的协议串不单边改。
7. **证据件/冻结件字节不动**（SHA 绑定的件：要翻只翻副本并在报告里单列）。

## Pitfalls

- **别承诺「100% 中文」**：路径、命令、代码、字段名、枚举、协议串永远保留英文——现实目标是把英文从约 3/4 压到 15–25%。
- **只覆盖「这一份安装树」**：多机环境逐机处理；云端/其他机器各跑各的，没有捷径。
- **`hermes update` 会覆盖源码**：升级后重放补丁（B）或重跑幂等脚本（A），再重启。
- **验证别偷懒**：改了源码 ≠ 生效；生效 = 重建进程 + 真实上传 dump 量出来的占比变化。

## Verification

- [ ] 三个脚本 `--check` 全绿（「已是中文，跳过」），无「未命中」告警
- [ ] 全部被改文件 `py_compile` 通过
- [ ] 重启后 `HERMES_DUMP_REQUESTS=1` 实抓一次：`audit-request-dump.py` 显示各块中文占比符合预期
- [ ] 危险区项抽查：`SKILL_SAFETY_HEADING` 等仍为英文
- [ ] 冒烟：跑一次真实工具调用 / 调一次技能，注入文本为中文、功能正常
