# harness 注入提示词地图与验证工具（操作级）

配套 SKILL.md 的「五个注入面」一节：按图找齐所有注入面、避开危险区、用真实上传验证。
路径约定：Windows 为 `%LOCALAPPDATA%\hermes\`，macOS/Linux 为 `~/.hermes/`；源码树在其中的 `hermes-agent/` 子目录（下文的相对路径均相对源码树）。

## 五个注入面（哪里还有英文）

1. **技能包装**（已翻）：`hermes-agent/agent/skill_commands.py`、`gateway/run_turn.py`、`cron/scheduler_prompt.py`；幂等补丁 `scripts/zh-skill-wrappers.py`（本仓库）。
2. **系统提示正文**：
   - `agent/prompt_builder.py` 常量：`TASK_COMPLETION_GUIDANCE`、`PARALLEL_TOOL_CALL_GUIDANCE`、`TOOL_USE_ENFORCEMENT_GUIDANCE`、`ASYNC_HANDOFF_GUIDANCE`、`OPENAI_MODEL_EXECUTION_GUIDANCE`（最大块）、`HERMES_AGENT_HELP_GUIDANCE` **两变体（with/without skills——容易只翻一个）**、`SESSION_SEARCH_GUIDANCE`、`SKILLS_GUIDANCE`、`SKILL_SAFETY_HEADING`（勿翻，见危险区）。
   - 函数/内联生成：`build_memory_guidance()`（记忆指引段）、运行环境块（`Host:`/`User home directory:`/`Current working directory:`/`Scratch directory:` 标签、Windows 说明常量 `_WINDOWS_BASH_SHELL_HINT`）、平台提示语（CLI：「asterisks, headers…」「Cron jobs … LOCAL-ONLY」；desktop 有独立变体）、`agent/system_prompt.py`（`Timezone:`、`Today's date…`、trailer 标签）。
   - `tools/bot_mode_probe.py`：`_PROTOCOL_HEADING`、`_build_section`、`_remote_paragraph`、`_peer_paragraph`、`"(no teammates yet)"`。
  - `agent/oneshot_footprint.py`：`ONESHOT_SKILLS_LOAD_GUIDANCE`——**一次性会话（`--oneshot`）用的技能块是独立变体**（与主 `SKILLS_GUIDANCE` 两处并存，容易只翻主变体、漏掉它）。
   - 低优先（未启用才可跳过）：`KANBAN_GUIDANCE`（kanban 工具集激活才注入）、`TELEGRAM_RICH_MESSAGES_HINT`、`GOOGLE_MODEL_OPERATIONAL_GUIDANCE`、`WSL_ENVIRONMENT_HINT`。
3. **工具定义**：`tools/*_tool.py` 的 `*_SCHEMA` dict 内所有 `"description"` 值与 `*_TOOL_DESCRIPTION` 常量。别漏：`tools/bot_mode_dm.py`（message_agent）、`tools/tool_search.py`（tool_search/describe/call）、桌面系 `*_preview/read_terminal/read_window/tip/tour/focus_pane/apply_layout/close_terminal*_tool.py`、`tools/computer_use/schema.py`、`tools/process_registry.py`、`tools/cronjob_tools.py`、`tools/session_search_tool.py`、`tools/todo_tool.py`。
4. **技能分类描述**：`skills/*/DESCRIPTION.md` 与 `profiles/*/skills/*/DESCRIPTION.md`（每分类每 profile 一份；frontmatter `description:` 或纯文本）。分类名＝目录名。
5. **技能描述行**：每个 `skills/**/SKILL.md` 的 frontmatter `description`——进每会话 `<available_skills>` 索引（模型据此决定加载哪个技能）；跨 profile 有数百副本。流程：
   - 枚举全部 `SKILL.md`（default＋各 profile）取 `description`；**无 CJK 的**收进唯一清单（去重），逐条翻译后按序回填成「英文→中文」映射；
   - 脚本按映射对全部副本写回：命中替换、每份留 `.bak-zh-skilldesc`；
   - **折叠式 `description: >`（或 `|`）单行正则会抓到 `>` 或截断**——专门检测行尾 `>`/`|` 的写法、读取其后缩进块全文；写回时把整块替换成单行双引号标量；
   - 写回一律双引号包裹；译文避免出现 `"`（用「」）与 `: ` 序列；
   - 验证：全部 `SKILL.md` 的 frontmatter 过 `yaml.safe_load`＋重扫「无 CJK 的描述」=0；盲区：**含任一 CJK 的中英混合行会被放过**（要彻底需白名单复核）。

## 危险区（翻前先 `grep -rn '<常量名>'` 看引用）

| 常量/串 | 机制 | 结论 |
|---|---|---|
| `SKILL_SAFETY_HEADING`「## Skill Safety Rule」 | 被 tests 与压缩摘要引用 | 保持英文；只翻 `SKILLS_GUIDANCE` 其余部分 |
| `RUNTIME_ENVIRONMENT_HEADING` | 持久化提示的 cwd 校验标记 | 不动 |
| `CONTROL_FRAME_OPENERS` | 控制帧检测模式 | 不动 |
| `STEER_MARKER_OPEN/CLOSE` | 投递与提示共用同一常量 | 可翻；先 grep 全部引用（如 conversation_compression），投递/描述同步 |
| `_PROTOCOL_HEADING` | `strip_legacy_protocol` 用它剥旧 SOUL 段 | 可翻；剥除器改成新旧标题双匹配（`_LEGACY_HEADINGS`） |
| `_SKILL_INVOCATION_PREFIX` 等包装标记 | 构造/解析逐字节一致 | 已翻版本已同步正则；再动必再同步 |
| `model_tools.py` 的 `_trim_delegate_restrictions`、`_VAULT_INPUT_TOOL_HINT` | 对工具描述做**英文子串替换/修剪**——被替换文案翻成中文后 matcher 静默失效 | 翻对应文案时同步 matcher：中文变体在前、旧英文变体保留兼容 |
| `conversation_compression.py` steer fallback 字面量 | 与投递/桌面端共用协议串 | 不单边改；协议串本身保持英文 |

还有：翻译常量前先确认「该常量确实进入上传」（对比 request_dump 里出现的段落），没进上传的（按平台/模型分叉的变体）可以不做。

## 验证（真实上传测量）

- 开关：`HERMES_DUMP_REQUESTS=1`（`agent/turn_api_request.py` 的 preflight 处 `env_var_enabled("HERMES_DUMP_REQUESTS")`）→ 每次请求写 `request_dump_*.json` 到该 profile 的 `sessions/`；另：API 4xx（不可重试客户端错误/重试耗尽）也会自动转储（`agent/_dump_api_request_debug`）。
- 解析：dump JSON → `request.body`（**可能是字符串，需二次 `json.loads`**）→ 分 system / tools / 其余对话三块。
- 量法：CJK 字符数与 ASCII 字母数占比；tok 估算 ≈ CJK×0.6 + 字母×0.25 + 其余×0.15（用于前后对比即可）。
- 定位残余：系统提示按 `\n(?=#{1,2} )` 切块、按大小排序，先看英文大头。
- 示例：`HERMES_DUMP_REQUESTS=1 <hermes.exe> -p <profile> chat -q "只回复：1" --oneshot`。跑通会真实产生一次模型调用（便宜）。

## 修改与重放机制

- 备份后缀统一：`.bak-zh-harness`（harness 源码）、`.bak-zh-desc`（DESCRIPTION.md）、`.bak-zh-skill`（技能正文）、`.bak-zh-tools`（子代理翻工具）。
- 单点改＝`patch` 工具；批量重复件＝Python 脚本（幂等判据＝目标块含 CJK 即跳过；命中数写日志）。
- 重放：收尾 `git diff > zh-harness-<面>.patch`（本仓库 `patches/` 有 2026-10 的 v0.21.x 快照）；升级覆盖后 `git apply` 或重跑幂等脚本（`scripts/`）。
- **重启实操**：`hermes gateway restart` 存在且可用；重启后几秒内会短暂看到多个 `gateway run` 进程（spawn/退出过渡）——**别急判「重复进程」**，等几秒后用 netstat 认「谁在听端口」＋父进程链。看门狗托管的 `serve --isolated`：**直接杀进程等自愈**（约 1 分钟内日志 `NOT ANSWERING -> restarting` → `restored (HTTP 200 verified)`），再验云端端到端（`ssh <云主机> curl 127.0.0.1:<转发口>`）。桌面 App 只能人工重启。
- **子代理派工单模板**（工具定义批量翻译）：
  - 只翻「发给大模型的说明」＝`*_DESCRIPTION` 常量内容 + `*_SCHEMA` 里所有 `"description"` 值（含相邻字符串拼接组、f"…"）；
  - 不动：工具名/参数键/enum/default/type/required/注释/docstring/日志/路径/命令/URL/占位符 `{…}`/markdown 记号；
  - 术语表：tool→工具、tool call→工具调用、session→会话、turn→回合、skill→技能、patch→补丁、sandbox→沙箱、workspace→工作区；
  - 每文件流程：先 `cp <file> <file>.bak-zh-tools` → 改 → venv `python -m py_compile <file>` → 失败回滚并报告 → 自查残留成句英文（连续 ≥6 英文词为嫌疑）；
  - 报告：逐文件改动处数/编译结果/残留清单；禁止动清单外文件、禁止跑 hermes 命令、禁止重启任何进程。
  - 交付后父代理自验：全部文件 py_compile + 导入构建 schema 对照工具名/参数名 + 抽样真跑几个工具调用。
