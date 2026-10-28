# 安装与运行指南（Windows / macOS）

本指南面向**第一次接触这个项目**的人。目标：从零到能跑通「找人 → 评分 → 看板」，再决定要不要登录 Instagram 真发。

> 想先看效果、不想登录任何账号？直接跳到文末 **「不登录的演示模式」**，3 条命令就能看到完整流程。

---

## 1. 环境要求

| 依赖 | 是否必需 | 说明 |
|---|---|---|
| Python 3.10+ | ✅ 必需 | 项目本体 |
| Chrome / Chromium | ✅ 必需（要真发私信时） | `playwright` 会自动装一个；也可复用你本机已登录的真实 Chrome（`run.py chrome`） |
| `pip install -r requirements.txt` | ✅ 必需 | playwright / openpyxl / lxml |
| OpenAI API Key | ⚠️ 可选 | 不填则用模板文案，功能完整 |
| 飞书 CLI `lark-cli` | ⚠️ 可选 | 仅当你要同步到飞书多维表格 |
| Instagram 账号 | ⚠️ 可选 | 仅当你要真发私信；**建议先用演示模式** |

---

## 2. 安装

### Windows（PowerShell）

```powershell
# 1. 克隆
git clone https://github.com/yuetingliu444-bit/ig-outreach-agent.git
cd ig-outreach-agent

# 2. 建虚拟环境（推荐，避免污染全局 Python）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# 若提示禁止脚本，先执行：Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 3. 装依赖
pip install -r requirements.txt
playwright install chromium      # 拉一个 Chromium 给脚本用

# 4. 准备配置（复制示例模板，按需改）
cp config/brand.json.example config/brand.json      # 若不存在示例，可先 run.py setup 向导生成
cp .env.example .env                                # 填 API Key / 代理（可选）
```

### macOS / Linux（终端）

```bash
# 1. 克隆
git clone https://github.com/yuetingliu444-bit/ig-outreach-agent.git
cd ig-outreach-agent

# 2. 建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 准备配置
cp config/brand.json.example config/brand.json
cp .env.example .env
```

---

## 3. 首次配置（两种方式）

**方式 A：向导（不用碰 JSON）**

```bash
python run.py setup        # 浏览器打开 http://127.0.0.1:8787 填表保存
```

**方式 B：命令行直配**

```bash
python run.py set-targets --competitors "竞品账号" --keywords "tech reviewer" --hashtags "wirelessmic"
```

品牌档案（`config/brand.json`）决定文案质量，至少填 `target_categories` / `target_regions` / 你的产品简介。

---

## 4. 登录 Instagram（仅当你要真发）

默认走 **CDP 模式**：复用你本机已经登录的真实 Chrome（指纹最稳）。

```bash
python run.py chrome       # 开一个带调试端口的真实 Chrome，在里面手动登录 IG（窗口保持开着）
python run.py check        # 体检确认登录态为 ok
```

> 无显示器 / 服务器环境：把 `config/settings.json` 的 `browser.mode` 改成 `"playwright"`，
> 脚本会自带一个 Chromium（`headless` 可设 `true`）。但指纹是新设备，风控风险更高，仅建议临时使用。

> ⚠️ 自动发私信违反 Instagram 服务条款。本项目定位是「**合规建联辅助 + 人工审核**」：
> 默认提供 `--assist` 半自动（脚本填好对话框，**发送键由你点**）、`--dry-run` 只预览不真发、
> 以及多级风控熔断。请只为**你有权代表的品牌账号**使用，并遵守平台规则与当地法律。
> 需要程序化发送时，优先研究 Meta 官方 Messaging API 的授权条件。

---

## 5. 快速开始（真发前建议先 dry-run）

```bash
python run.py pipeline --limit 10 --dry-run   # 只看会生成的文案，不联网发
python run.py send --limit 10 --assist         # 半自动：对话框填好，发送键你点
python run.py status                           # 看漏斗和风控额度
```

---

## 6. 不登录的演示模式（推荐先跑这个）

用一套**完全虚构**的样例数据，不连 Instagram、不填任何 Key，就能体验
「线索评分 → 文案 → 看板 → 人工标注」。数据全部是 `example.com` 假域名，无任何真实联系人。

```bash
# Windows
set OUTREACH_DB=data/demo_outreach.db
python tools/seed_demo.py
python run.py status          # 看漏斗（已发送 / 已回复 / 待发送 …）
python run.py dashboard       # 生成看板 dashboard/index.html

# macOS / Linux
export OUTREACH_DB=data/demo_outreach.db
python3 tools/seed_demo.py
python3 run.py status
python3 run.py dashboard
```

还可以试人工标注（纯本地，不联网）：

```bash
python run.py note @nova_tech_reviews --intent hot --tags "高意向" --note "demo 标注"
```

`OUTREACH_DB` 指向独立数据库，**不会污染你的真实 `data/outreach.db`**。要回到真实库， unset 该变量即可。

---

## 7. 飞书同步（可选）

见 README「飞书多维表格同步配置」：复制 `config/feishu.local.example.json` 为 `config/feishu.local.json` 填 token，然后 `python run.py feishu`。

---

## 8. 常见问题

| 现象 | 排查 |
|---|---|
| `ModuleNotFoundError: No module named 'playwright'` | 确认已激活 venv 且执行过 `pip install -r requirements.txt` |
| 浏览器启动失败 / Crashpad | 默认 CDP 模式需本地有桌面版 Chrome：先 `python run.py chrome` 再发；无显示器服务器改 `settings.json` 的 `browser.mode` 为 `"playwright"`（自带 Chromium，可 `headless:true`） |
| API Key 无效 | 检查 `.env` 里 `OPENAI_API_KEY` 是否填对、是否被 gitignore 忽略而未加载 |
| 登录后脚本说未登录 | 确认 `config/settings.json` 的 `account.profile_dir` 指向的目录和 `login` 用的是同一个 |
| 发不出去（not_found） | 对方关了私信 / 账号不存在，属正常，会自动标 `failed` |

---

## 9. 安全与隐私

- **登录态 / 联系人 / 建联记录**全部存在本地 `data/`（已被 `.gitignore` 忽略，**不会上传**）。
- **飞书 token / API Key** 只在本地 `config/feishu.local.json` 和 `.env`（均 gitignore），源码不硬编码。
- **清理**：删除 `data/` 目录即可抹掉全部本地数据；`config/feishu.local.json`、`.env` 删掉即移除凭证。
- **数据不发给任何第三方**：除你主动配置的 OpenAI / 飞书端点外，代码不向外发送你的库。

---

## 10. 命令一览（速查）

`setup` · `init` · `login` · `find` · `enrich` · `score` · `draft` · `send [--dry-run|--assist]` ·
`watch` · `second-touch` · `note` · `board` · `pipeline` · `dashboard` · `status` ·
`export` · `feishu` · `unfreeze`

详见 `README.md`。
