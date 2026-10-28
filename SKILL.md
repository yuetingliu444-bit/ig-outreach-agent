---
name: ig-outreach-agent
description: >-
  当用户任务涉及 Instagram 达人 / KOL / 海外红人建联、出海品牌营销、找人打分写私信、线索跟进或建联看板时使用。
  负责把"发现潜在 KOL/品牌 → 补全资料 → 评分筛选 → 个性化文案 → 发送(半自动) → 回复跟进 → 看板/飞书同步"串成可操作工作流。
  仅在用户明确要做 Instagram / 海外达人建联、且接受人工审核模式时使用；不要用于规避平台检测或无人值守群发。
---

# IG 建联 Agent（Skill）

## 概述

这是一个**业务核心用 Python 实现、可由 Agent 通过 CLI 调用的达人建联工具**，不是一段塞进提示词的脚本。
它把完整的达人营销工作流拆成可独立调用的命令，Agent 负责理解任务、做判断、编排命令；Python 负责稳定可测试的业务逻辑。

> **定位**：合规建联辅助 + 人工审核（MVP）。自动发 Instagram 私信违反 IG 服务条款，因此默认提供
> `--dry-run`（只预览不真发）与 `--assist`（脚本填好对话框、**发送键由人点**）两种安全模式。

## 何时使用

- 用户要"找 Instagram 上的 KOL / 达人 / 竞品粉丝"
- 用户要"给达人写个性化建联私信 / 批量生成 outreach 文案"
- 用户要"筛选线索、打分、跟进回复、管理建联进度"
- 用户要"把建联名单同步到飞书多维表格 / 导出 CSV"
- 用户在做"出海品牌红人营销"相关任务

## 何时**不**使用

- 用户想做"绕过检测 / 稳定群发 / 无人值守自动发"——**拒绝**，并说明合规边界（见下）
- 用户要的是通用社媒运营之外的事（如涨粉、投流）——不在本 Skill 范围
- 没有安装依赖 / 没有浏览器环境，且用户只想要理论建议——直接给方法论即可，不必调用命令

## 能力边界（CLI 命令）

所有命令通过 `python run.py <command>` 调用（详见 `README.md` / `INSTALL.md`）：

| 命令 | 作用 | 需要浏览器/登录 |
|---|---|---|
| `setup` | 配置向导（本地网页填表） | 否 |
| `find` | 抓潜在 KOL / 品牌用户名 | 是 |
| `enrich` | 补全粉丝数 / 简介 / 邮箱 | 是 |
| `score` | 按启发式打分筛选 | 否 |
| `draft` | 生成个性化文案（可接 LLM） | 否 |
| `send [--dry-run\|--assist]` | 带风控发送；`--dry-run` 只预览，`--assist` 发送键由人点 | 是 |
| `watch` | 检查谁回复了（只读，不自动发） | 是 |
| `second-touch` | 对已回复者发第二条 | 是 |
| `note @user --intent hot` | 命令行标注意向/标签 | 否 |
| `board` / `dashboard` / `status` | 运营看板 / 看板 HTML / 漏斗统计 | 否 |
| `export` | 导出商务邮箱 CSV | 否 |
| `feishu` | 同步到飞书多维表格 | 否（需 lark-cli 授权） |
| `unfreeze` | 手动解除风控熔断 | 否 |

## 依赖与安装

- Python ≥ 3.10；`pip install -r requirements.txt`（playwright / openpyxl / lxml）
- `playwright install chromium`
- 首次配置：`python run.py setup`，或 `cp config/brand.json.example config/brand.json` 后填品牌档案
- 完整跨平台步骤见 `INSTALL.md`

## 凭证与配置（不硬编码）

- LLM：`OPENAI_API_KEY`（可选，不填走模板文案）
- 飞书：复制 `config/feishu.local.example.json` 为 `config/feishu.local.json` 填 token，或设 `FEISHU_BASE_TOKEN` / `FEISHU_TABLE_ID`
- 以上均写入 `.env` / 本地 `*.local.json`（已被 `.gitignore` 忽略），源码不含任何真实凭证
- 登录态、联系人、建联记录全部在本地 `data/`，不向外发送

## 安全与人工审批边界（必须守住）

1. **默认不要自动发送**。优先建议 `--dry-run` 验收文案，再 `--assist` 半自动（人点发送）。
2. **命中页面限制提示（Action Blocked / Try Again Later）立即熔断 24h**，不要重试。
3. **账号被 challenge 时停止一切命令**，提示用户手动验证 + 冷却 3–7 天。
4. **高影响操作（发送 / 删除 / 修改）保留人工审批**；只读与本地分析（score / draft / status / dashboard）可自动跑。
5. **绝不为"绕过平台检测"优化**。随机延迟、真实浏览器、指纹跟随只是降低误触发概率，不是合规保障。

## 不做什么（红线）

- 不宣称"每天发多少条就安全"
- 不把指纹伪装 / 随机延迟包装成合规能力
- 不自动批量冷私信；不替代 Meta 官方 Messaging API 的授权场景
- 不把邮件建联说成"零风险"（仍需遵守反垃圾邮件法、退订机制、数据来源合法）

## 调用示例

```
# 先看会生成什么文案（不联网发）
python run.py pipeline --limit 10 --dry-run

# 半自动：对话框填好，发送键由用户点
python run.py send --limit 10 --assist

# 不登录也能验收：载入虚构样例看漏斗/看板
set OUTREACH_DB=data/demo_outreach.db
python tools/seed_demo.py
python run.py status
```

## 验证（干净环境）

找一台没有开发工具的机器，严格按 `INSTALL.md` 从克隆开始安装。只要一个陌生用户仍需远程指导，说明交付尚未产品化。
