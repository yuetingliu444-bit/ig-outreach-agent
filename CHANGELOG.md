# Changelog

本项目遵循语义化版本（SemVer）。所有 notable 变更记录于此。

---

## [v1.0.0] — 2026-10-28

首个对外可交付的 MVP 版本。相较早期「作者自用工程」，本轮重点补齐了**工程规范、安全闸、跨平台能力、合规边界与商业化交付物**。

### ✨ 新增
- **配置前置校验（`src/validate.py`）**：`draft` / `send` / `second-touch` / `pipeline` 执行前强制校验 `brand.json` / `pitch.json`——缺失文件给出清晰初始化指令；残留占位符（`[Brand A]`、`example.com`、`示例`、`Your Agency`、`AuroraAudio`、`（填你的品牌名）` 等）直接终止并列出字段，避免发出带模板字样的公关事故。
- **`run.py init` 命令**：一键从 `config/*.example.json` 生成正式配置（已存在则跳过），降低新手门槛。
- **跨平台浏览器探测（`src/browser.py`）**：`CHROME_CANDIDATES` 覆盖 Windows / macOS / Linux 路径；支持在 `settings.json` 的 `browser.executable_path` 手动指定；调试 Chrome 的 profile 目录改为跨平台（`~/.igagent/chrome-profile`），不再依赖 Windows 专属环境变量。
- **英文文档 `README_EN.md`**：与中文 README 一一对应，面向海外 KOL Agency 用户。
- **`SKILL.md`**：标准化声明所有子命令、入参、输出与限制，可作为 Agent 工具集被 Dify / Coze / Cursor / WorkBuddy 等框架识别调用。
- **`INSTALL.md`**：Windows / macOS / Linux 跨平台安装指南，含「不登录演示模式」（虚构样例数据，零配置体验全流程）。
- **`demo/sample_leads.csv` + `tools/seed_demo.py`**：完全虚构的演示数据集，任何人都能 `OUTREACH_DB=data/demo_outreach.db python tools/seed_demo.py` 跑通评分→文案→看板。
- **`.env.example` / `requirements.txt`**：显式声明依赖（playwright / openpyxl / lxml）与环境变量模板。
- **CHANGELOG.md**：本文件。

### 🔧 变更 / 修复
- **浏览器默认模式对齐文档**：`settings.json` 的 `browser.mode` 由 `playwright` 改为 `cdp`、`headless` 由 `true` 改为 `false`，与 SOP 文档和 `--assist` 半自动模式一致（无头模式下人工确认界面无法操作）。
- **合规重构（README / INSTALL）**：顶部强制免责声明；明确「随机延迟 / 指纹跟随 ≠ 合规保障，自动化访问仍违反 IG ToS」；推荐 `--assist` 半自动；引导优先研究 Meta 官方 Messaging API；删除「邮件零风险」等误导性表述。
- **数据与隐私合规专节**：新增 GDPR / CCPA 数据采集合规提示。
- **飞书模块隔离标注**：明确为「仅国内可选扩展」，海外用户可忽略，不影响核心 IG 建联。
- **参数一致性**：统一 README / INSTALL 与 `settings.json` 的阈值（`min_score=45`、`min_followers=1000`、`max_followers=50000000`），明确 `settings.json` 为唯一权威来源。
- **调试脚本归档**：根目录与 `tests/` 下的调试 / 一次性脚本（debug / load_batch / probe / revival / verify_dm 等）统一移入 `.dev/` 并 gitignore，仓库根目录只剩 `run.py` + 文档，职责隔离清晰。
- **安全加固（git）**：`data/`、`dashboard/`、`config/feishu.local.json`、`config/brand.json`、`config/pitch.json`、`config/targets.json` 及真实品牌名单脚本均 gitignore，远程仓库无真实 handle、无真实 token、无运营数据库。

### ⚠️ 已知限制
- **P0 已清零**，以下为已知的产品边界：
- 仅覆盖 Instagram 单一渠道（FB / Google / TT 看板与 Looker Studio 在规划中）。
- 选择器集中在 `src/selectors.py`，IG 前端改版时需人工更新候选列表。
- 无自动化测试套件（现有测试脚本在 `.dev/`，仅供作者本地排障）。
- 演示模式不含真实发送链路，仅用于体验评分 / 文案 / 看板。

### 🚫 风险声明
使用本工具自动发送 Instagram 私信违反 Instagram 服务条款，可能导致 Action Block / 账号封禁。本项目内置风控**仅降低概率，不构成合规保障**。后果由使用者自行承担；作者不对账号封禁、数据泄露或任何使用后果负责。详见 README 顶部免责声明与「数据与隐私合规」节。
