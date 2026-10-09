# hermes-zh-localization

把 [Hermes Agent](https://hermes-agent.nousresearch.com/docs/) 注入到大模型请求里的**英文提示词全量中文化**——让 DeepSeek 这类模型「用中文想、用中文答」。

模型的思考与输出语言跟着上下文主体语言走；Hermes 的系统提示、工具说明、技能索引默认是英文，会把模型带偏、拉低中文表现。本仓库把「怎么把它翻成中文」固化为一整套**方法 + 工具**：流程文档、幂等补丁脚本、注入面地图、验收工具、快照补丁。

## 效果（真实请求转储实测，24h profile）

| 块 | 翻前·中文占比 | 翻后·中文占比 |
|---|---|---|
| 系统提示 | 2.3% | **54.7%** |
| 工具定义 | 0.0% | **42.1%** |
| 整包估算 | ≈16.5K tok | **≈12.1K tok（-26%）** |

> 口径：中文字符 ÷（中文字符 + 英文字母）。剩余部分多为**必须保留**的路径、命令、代码、字段名与协议串（见下文「危险区」）。

## 内容

| 路径 | 是什么 |
|---|---|
| `SKILL.md` | 技能主文件——装进 `~/.hermes/skills/`（或任意 profile 的 skills 目录）后，agent 可按流程执行 |
| `references/harness-prompt-map.md` | **五个注入面**的逐常量地图 + 危险区清单 + 验证方法（动手前先读它） |
| `scripts/zh-skill-wrappers.py` | 第 0 轮：技能包装（调用技能时注入的前缀/后缀） |
| `scripts/zh-harness-prompts.py` | 第 1 轮：系统提示主常量 |
| `scripts/zh-harness-prompts-2.py` | 第 2 轮：运行环境块 / Bot 模式块 / 小常量 / 时区 |
| `scripts/audit-request-dump.py` | 验收工具：量请求转储里的语言占比、定位剩余英文大头 |
| `patches/zh-harness-2026-10-09.patch` | v0.21.x（2026-10）全量快照补丁（38 文件） |

三个补丁脚本都是**幂等**的：按常量名/片段定位；已含中文的跳过、找不到的报警；每文件备份（`.bak-zh-*`）、改完 `py_compile` 校验、失败自动回滚。加 `--check` 只对账、不改动。

## 快速开始

```bash
# 1) 先对账（只读），再应用（脚本自动探测 Hermes 安装树；HERMES_ROOT 可覆盖）
python scripts/zh-skill-wrappers.py --check
python scripts/zh-skill-wrappers.py
python scripts/zh-harness-prompts.py       # 支持 --check
python scripts/zh-harness-prompts-2.py     # 支持 --check

# 2) 重启常驻进程——Python 进程启动即载入旧模块，不重启不生效：
#    桌面 App（后端随它）、`hermes gateway run`、各 `hermes serve`

# 3) 验收：打开真实上传转储，量占比
HERMES_DUMP_REQUESTS=1 hermes -p <profile> chat -q "只回复：1" --oneshot
python scripts/audit-request-dump.py <hermes 数据目录>/profiles/<profile>/sessions/ --sections
```

同版本一键补丁（v0.21.x）：

```bash
cd <hermes-agent 源码树>
git apply --3way <本仓库>/patches/zh-harness-2026-10-09.patch
```

## 危险区（保持英文，别翻）

少数常量被运行时逻辑用**英文文本**做匹配（翻掉会让检测/剥除逻辑静默失配）：

- `SKILL_SAFETY_HEADING` —— 被 `sessions` 的 repair 路径用于匹配历史 system_prompt；
- `RUNTIME_ENVIRONMENT_HEADING`、`CONTROL_FRAME_OPENERS` —— 运行时校验/检测标记；
- `model_tools.py` 里对工具描述做英文子串替换/修剪的匹配器——翻对应文案时须同步改匹配器（保留旧英文变体兼容）。

完整清单与判断方法见 `references/harness-prompt-map.md` 的「危险区」一节。

## 注意

- 快照补丁对应 Hermes **v0.21.x（2026-10）**；`hermes update` 会覆盖源码——升级后重放补丁或重跑幂等脚本。
- 本仓库只覆盖「**这一份安装树**」；多机环境逐机处理（每台机器各有自己的源码树）。
- 别承诺「100% 中文」：路径、命令、代码、字段名、枚举、协议串永远保留英文——现实目标是把英文从约 3/4 压到 15–25%。

## 许可

MIT，见 [LICENSE](LICENSE)。
