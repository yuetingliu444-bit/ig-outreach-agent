# IG 建联 Agent

自动化跑通「找 KOL → 补全资料 → 打分 → 写个性化私信 → 发送 → 跟进 → 查回复」整条链路。

---

## ⚠️ 先读这一段

**用脚本自动发 Instagram 私信违反 Instagram 服务条款。** 可能后果：临时 Action Block、私信功能被关、账号被封。你用的是**公司品牌号**，封掉的代价是品牌资产，不是换个号重来的事。

所以这个工具默认配置是**保守**的，并且内建熔断：

| 保护机制 | 默认值 | 说明 |
|---|---|---|
| 每日上限 | 35 条 | 养号期内自动降到 8 条 |
| 每小时上限 | 6 条 | 防止短时间爆发 |
| 两条之间的间隔 | 4–12 分钟**随机** | 机械节奏是最容易被识别的特征 |
| 工作时间窗 | 9:00–21:00 | 半夜发消息 = 机器人 |
| 养号期 | 前 7 天降额 | 新号别上来就猛发 |
| 连续失败 | 3 次自动熔断 | 说明环境已经不对劲 |
| 页面限制提示 | 命中立即熔断 24h | "Action Blocked" / "Try Again Later" 等 |
| 文案相似度 | > 0.72 重写 | 同一个句子群发 = 死得快 |

### 强烈建议：用 `--assist` 半自动

```bash
python run.py send --assist --limit 10
```

脚本负责找人、补全、打分、写文案、**打开对话框并把文案填进输入框**；**发送键由你点**。
没有任何一条消息是机器发出去的 —— 节奏和判断都在人手里，风险量级完全不同，但仍保留了自动化的绝大部分效率收益。

### 已经出现 challenge 怎么办

如果看到这样的输出：

```
!! 账号被 Instagram 要求身份验证（challenge）： URL 命中 challenge
```

说明 IG 已经怀疑这个号在用自动化工具（页面提示 "We suspect automated behavior on your account"）。脚本会**自动硬拦截**，任何命令都不会继续。

处理顺序：

1. **什么都别跑**，在浏览器里手动完成验证
2. 冷却 **3–7 天**，期间只做正常手动操作（刷刷首页、点点赞）
3. 把密码改强一点
4. 恢复后只用 `--assist` 半自动模式，每天控制在 10–15 条以内
5. 想彻底规避风险，就用 `python run.py export` 导出商务邮箱走邮件建联

---

**强烈建议的执行顺序：**

1. 第一周用 `--dry-run` 跑，只看文案质量，不真发
2. 第二周真发，但把 `daily_cap` 调到 **8–10**
3. 连续两周没出现任何限制提示，再逐步加到 20 → 35
4. 任何时候出现验证弹窗，**立刻停**，手动把账号养回来

**如果你想要零风险的建联，用 `python run.py export` 导出商务邮箱走邮件。** 邮件建联完全合规，可以放心批量发，而且很多 KOL 简介里就挂了商务邮箱。

---

## 两步开跑

```bash
# 1. 起配置向导，浏览器打开 http://127.0.0.1:8787 填表保存（不用碰 JSON）
python run.py setup

# 2. 登录：浏览器自动打开，你在里面登完，它自己检测到并保存（不用回终端按回车）
python run.py login

# 3. 发
python run.py pipeline --limit 10 --dry-run   # 先看文案
python run.py send --limit 10                 # 真发
```

不想用向导，也可以命令行直配：

```bash
python run.py set-targets --competitors "竞品账号" --keywords "tech reviewer" --hashtags "wirelessmic"
```

Python 路径（本项目用的隔离环境）：
`C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe`

---

## 每日运营工作流（B2B 建联版）

一天的标准循环，三步：

```bash
# 早上：查谁回复了（只读收件箱，自动标记 replied，不自动发任何东西）
python run.py watch

# 上午：开看板，人工过一遍（网页里直接标注意向/标签/备注）
python run.py board          # http://127.0.0.1:8790

# 下午：对「已回复」的人发第二条（media kit + 软性推荐），发完自动标记
python run.py second-touch --limit 5
# 想更稳就 --assist：第二条也由你点发送
python run.py second-touch --limit 5 --assist
```

**为什么 watch 不自动补发 media kit**：回复是「热的对话」，但先人工看一眼回复内容再决定发什么，比机器自动发一条模板链接的转化率高得多。看板的「⏳ 待二次跟进队列」就是干这个的。

没回复的人：4 天后自动到期 bump 一次（`send --followup` 或 `pipeline` 里带），只 bump 一次，不纠缠。

---

## 运营看板（`python run.py board`）

本地服务，数据只进 SQLite，不过任何外部服务器：

- **KPI**：已发送 / 已回复 / 回复率 / 待二次跟进 / 已标注
- **漏斗**：每个环节有多少人，断点一眼可见
- **按来源的回复率**：哪个渠道找来的人更愿意回 —— 下次找人就往那投
- **筛选**：全部 / 待回复 / 已回复 / 已二次跟进 / 已标注
- **在线标注**：每行点「标注」→ 意向等级（🔥高意向 / 🌤观望 / ❄已拒绝 / ⚰无效）+ 标签 + 备注，保存即入库
- 命令行也能标注：`python run.py note @your_target --intent hot --tags "已约会议" --note "Q4 有预算"`

---

## 命令一览

| 命令 | 作用 | 需要开浏览器 |
|---|---|---|
| `setup` | 起配置向导页（127.0.0.1:8787），填表写 config | 否 |
| `chrome` | 开一个调试版真实 Chrome（复用你日常指纹） | 否 | 先跑它 |
| `check` | **只读体检**：账号有没有被 challenge / block | 只读 | 冷却期每天跑 |
| `login` | 开浏览器，你登录，自动检测保存 | 是 | |
| `set-targets` | 配置找人来源 | 否 |
| `find` | 抓潜在 KOL 用户名 | 是 |
| `enrich [--limit N] [--fetch-link]` | 补全粉丝数/简介/邮箱 | 是 |
| `score` | 打分筛选 | 否 |
| `draft` | 生成个性化文案 | 否（可选接 LLM） |
| `send [--limit N] [--dry-run] [--assist] [--followup]` | 带风控发送 | 是 |
| `watch` | 检查谁回复了（只检测，不自动发） | 是 |
| `second-touch [--limit N] [--dry-run] [--assist]` | 对已回复的人发第二条 | 是 |
| `note @user --intent hot --tags "…" --note "…"` | 命令行标注 | 否 |
| `board [--port N]` | 运营看板服务（默认 8790） | 否 |
| `pipeline` | 上面一条龙 | 是 |
| `dashboard` | 生成看板 `dashboard/index.html` | 否 |
| `status` | 看漏斗和风控额度 | 否 |
| `export` | 导出邮箱 CSV | 否 |
| `unfreeze` | 手动解除熔断 | 否 |

---

## 三个找人来源，质量排序

1. **竞品粉丝**（最准）— 关注竞品的人就是你的精准人群。填 `competitors`
2. **关键词搜索** — 走 IG 搜索页，覆盖广但杂
3. **话题标签** — 最杂，需要靠打分过滤。会逐个打开帖子取作者，比较慢

建议：竞品为主，关键词补充，`max_per_source` 别一次开太大。

---

## 打分规则

启发式，满分 100，默认阈值 55（`config/settings.json` → `qualify.min_score`）：

| 项 | 分值 |
|---|---|
| 粉丝数在区间内 | +25（不在区间直接淘汰） |
| 简介命中品类关键词 | +25 |
| 简介命中地区关键词 | +15 |
| 有接单信号（collab / PR / DM for / ambassador / managed by…） | 最高 +20 |
| 有商务邮箱 | +10 |
| 企业号 | +5 |
| 发帖 ≥ 20 | +5 |

品类/地区关键词取自 `config/brand.json` 的 `target_categories` / `target_regions`，改那里就行。

### 可选：接 LLM 提升质量

把 `config/brand.json` 填好后，在 `settings.json` 里开：

```json
"llm": { "enabled": true, "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY" }
```

然后 `set OPENAI_API_KEY=sk-xxx`。开了之后打分会用 LLM 复核，文案会针对每个 KOL 的简介单独写，回复率会明显高一档。不开也能跑，用模板 + 变量生成。

---

## 目标类型：你在找谁

`config/settings.json` → `qualify.target_type`

| 值 | 找的是 | 打分看什么 |
|---|---|---|
| `brand` | **有出海需求的品牌方 / 跨境卖家**（当前默认） | 有没有挂外链（独立站/店铺）+20、品牌信号（shop now / official / 跨境 / 出海 / 源头工厂…）最高 +20 |
| `creator` | 创作者 / KOL | 接单信号（collab / PR / DM for / ambassador / managed by…）最高 +20 |

这两种目标的信号完全不一样，选错会把真正对口的人判成低分。

## 话术

文案直接用 `config/pitch.json` 里的话术，两种模式（`settings.json` → `outreach.pitch_mode`）：

- **`optimized`（默认）** — 你的话术主体一字不改，前面加一句针对对方的个性化开头，链接等对方回复后再发
- **`verbatim`** — 所有人收到完全相同的一段话。**不建议**：这是封号风险最高、回复率最低的做法

相关开关：

```jsonc
"outreach": {
  "pitch_mode": "optimized",
  "link_in_first_message": false,   // 首条不带链：带外链的冷私信会被折叠进 Requests，且更容易触发风控
  "media_kit_on_reply": true,       // 对方一回复，自动补发带 media kit 链接的第二条
  "pitch_lang": "auto"              // 简介含中文自动发中文版，否则英文版
}
```

想看实际会发出去什么，不联网就能预览：

```bash
python tests/demo_pitch.py
```

---

## 飞书多维表格同步配置（可选）

把本地建联台账（`data/outreach.db`）同步到飞书多维表格，方便在手机/网页端看进度、团队协作。**纯可选**，不配也能正常跑建联。

**前置条件**

- 装好飞书 CLI `lark-cli` 并完成授权（本项目通过 WorkBuddy 飞书连接器认证，使用 `--profile personal` 个人版）。
- 在飞书建一张多维表格，状态选项需和 `src/feishu_sync.py` 里的 `STATUS_OPTION` 对照表一致（drafted→待发送 / sent→已发送·待回复 / replied→已回复 / failed→发送失败 / rejected→已淘汰 …）。

**配置凭证（不要写死在代码里）**

仓库已把 token 抽离，你只需要在本地放一份私有配置文件：

```bash
# 1. 复制模板
cp config/feishu.local.example.json config/feishu.local.json

# 2. 编辑 feishu.local.json，填入你的两个值
#    base_token —— 飞书多维表格 URL 里 my.feishu.cn/base/<这段就是>
#    table_id   —— 表格的 table_id（URL 里 tblxxxxxxxx 那段）
```

`feishu.local.json` 已被 `.gitignore` 忽略，**不会进版本库**，可放心填真实值。

不想用文件，也可以走环境变量（适合 CI / 容器）：

```bash
set FEISHU_BASE_TOKEN=你的base_token
set FEISHU_TABLE_ID=你的table_id
```

读取优先级：环境变量 `FEISHU_BASE_TOKEN` / `FEISHU_TABLE_ID` → 本地 `config/feishu.local.json`。

**同步**

```bash
python run.py feishu
```

策略是**增量同步**：按 IG 账号匹配，飞书里已有记录做更新、没有的做新增。每天 9:00 的自动化会调用一次，让在线表永远是最新的。

---

## 调参

全部在 `config/settings.json`：

```jsonc
"safety": {
  "daily_cap": 35,            // 想保守就改 10
  "hourly_cap": 6,
  "min_interval_sec": 240,    // 别低于 180
  "max_interval_sec": 720,
  "active_hours": {"start": 9, "end": 21},
  "warmup_days": 7,
  "warmup_daily_cap": 8
},
"qualify": {
  "min_followers": 2000,      // 按你的品类调
  "max_followers": 500000,
  "min_score": 55
}
```

养号期：在 `account.warmup_start_date` 填 `"2026-09-17"`，接下来 7 天自动降额到 8 条/天。

---

## 出问题了怎么办

**账号被 challenge（要求身份验证）—— 最严重，按这个来**

challenge 是风险阶梯的第 2 级（共 5 级），离封号还远，但方向错了会一路滑下去。

```
1. 立刻停手。任何命令、任何重试都会加重嫌疑。
2. 在浏览器里手动完成验证（手机 / 邮箱验证码）。
3. 冷却 3–7 天，只用这台浏览器正常手动刷 IG。
4. 每天跑一次 python run.py check，直到显示 ok。
5. 恢复后第一步：python run.py chrome   ← 用真实浏览器，别再自己起 Chromium
```

**为什么会被 challenge（血的教训）**

IG 的自动化检测分两层，**第二层你才看得见，第一层才是致命的**：

| 层 | 检测什么 | 我们能不能伪装 |
|---|---|---|
| ① 设备指纹 | 新设备？时区跳变？UA 陌生？ | **能，而且必须做对** |
| ② 行为模式 | 发送节奏像不像机器 | 能（限速 + 随机间隔，已实现） |

第一次用 Playwright 登录时，配置里写死了 `"timezone": "America/Los_Angeles"`，
人在国内却从洛杉矶登录 —— 这是 IG 的一级风控信号，**登录这个动作本身就触发了 challenge，
跟发没发消息基本无关**。

现在已修：`locale` / `timezone` 一律 `"auto"`（跟随系统），
并且默认走 `browser.mode: "cdp"` —— 接管你真实的 Chrome，指纹就是你日常那个。

**绝对不要做的事**
- 不要在 `settings.json` 里把 timezone 改成别的地区
- 不要同时开两个浏览器操作同一个账号
- 不要在 challenge 未解除时跑任何命令
Instagram 前端经常改版。所有选择器集中在 `src/selectors.py`，每个条目都是候选列表。改这一个文件就行，不用动业务代码。改完重跑即可。

**被熔断了**
`python run.py status` 看原因，`python run.py unfreeze` 解除。但先想清楚为什么被熔断——如果是页面提示了限制，建议停 24–48 小时再继续。

**发送失败 `not_found`**
对方关闭了私信、账号不存在、或是被限制了。会自动标记 `failed`，不会重试。

**想看数据**
`python run.py dashboard`，打开 `dashboard/index.html`。

---

## 目录结构

```
ig-agent/
├── run.py                 命令行入口
├── config/
│   ├── settings.json      风控参数、筛选阈值
│   ├── brand.json         品牌档案（决定文案质量）
│   └── targets.json       找人来源（用 set-targets 生成）
├── src/
│   ├── selectors.py       ← 选择器集中在这里，改版了改这里
│   ├── safety.py          风控闸门：配额 / 时间窗 / 熔断
│   ├── browser.py         浏览器会话
│   ├── discovery.py       找人（关键词 / 标签 / 竞品粉丝）
│   ├── enrich.py          资料补全（粉丝数 / 简介 / 邮箱）
│   ├── qualify.py         打分
│   ├── copywriter.py      个性化文案 + 去重
│   ├── sender.py          发送 + 跟进
│   ├── watcher.py         查回复
│   ├── store.py           SQLite 状态机
│   └── dashboard.py       看板渲染
├── data/                  数据库、浏览器 profile、风控状态
├── dashboard/index.html   看板
└── tests/smoke.py         离线冒烟测试（python tests/smoke.py）
```
