# IG 建联 Agent · SOP（标准作业流程）

> 这是一份给「不写代码、由 AI 代跑」的你准备的备忘录。
> 忘了前置条件、忘了为什么能直接发、忘了下一步该跑什么 —— 先翻这一页。

---

## 0. 这是什么（一句话）

一个跑在**你自己电脑上**的脚本，帮你自动完成建联全链路：

```
找品牌 → 补资料 → 打分 → 写私信 → 发送 → 查回复 → 二次跟进
```

数据存本地 SQLite（`data/outreach.db`），看板是本地网页（`run.py board`），**不过任何外部服务器**。

---

## 1. 为什么「你能直接登录 IG 帮我发」？（核心机制，务必看懂）

关键在于一个词：**登录态持久化（persistent profile）**。

流程是这样的：

1. 你第一次运行 `python run.py login` —— 脚本打开一个浏览器窗口
2. 你在那个窗口里**手动登录 IG**（输账号密码 + 二步验证）
3. 登录成功后，cookie / 登录凭证被永久写进本机目录 **`ig-agent/data/profile/`**
4. 之后每次运行任何命令（send / enrich / watch），脚本都用**同一个 profile** 启动浏览器 —— 等价于打开一个「已经登录过 IG 的浏览器」
5. 所以我不用你每次重新登录，直接用你存好的登录态去操作

**一句话总结：你只手动登录过一次，之后我每次都「穿你那双已经登录的鞋」去操作。**

所以：
- ❌ 不是我把账号密码记下来了
- ❌ 不是通过某个第三方 API 登录
- ✅ 是**你登录过的浏览器 cookie 被存进了本地目录**，我复用这个目录

**推论（重要）**：如果哪天你换了电脑、清了浏览器、或删掉了 `data/profile/` 目录，登录态就没了，需要重新 `login` 一次。

---

## 2. 前置条件（跑之前必须满足这 5 条）

| # | 前置条件 | 怎么确认 |
|---|---|---|
| 1 | 有一个真实 IG 账号（你的机构品牌号） | 账号能正常登录 |
| 2 | **至少手动登录过一次**，登录态在 `data/profile/` | `data/profile/` 目录存在且有内容 |
| 3 | 环境装好了（隔离 venv + playwright） | 用下面的 Python 路径能跑通 |
| 4 | 账号没被 challenge / block | `python run.py check` 显示 ✓ ok |
| 5 | 浏览器进程能正常起（无 profile 锁、不被沙箱杀） | 命令能正常打开浏览器 |

---

## 3. 环境三件套（固定不变，别忘）

```bash
# 工作目录
C:\Users\Administrator\WorkBuddy\2026-09-17-14-02-51\ig-agent

# Python 解释器（必须用这个，别用系统 python！）
C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe

# 关键文件/目录
data/profile/     ← 登录态（删了要重新 login）
data/outreach.db  ← 数据库（名单+状态都在这里）
config/pitch.json ← 话术（改文案改这里）
config/settings.json ← 风控参数、筛选阈值
```

以后所有命令统一这样跑：

```bash
cd "C:\Users\Administrator\WorkBuddy\2026-09-17-14-02-51\ig-agent"
"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" run.py <命令>
```

---

## 4. 一次完整建联（7 步，一条龙）

| 步骤 | 命令 | 说明 |
|---|---|---|
| ① 登录（只做一次） | `run.py login` | 手动登录 IG，会话保存到 profile |
| ② 体检 | `run.py check` | 只读，看账号有没有被 challenge |
| ③ 找品牌 | `run.py find` | 从关键词/标签/竞品抓用户名 |
| ④ 补资料 | `run.py enrich --limit 40` | 抓粉丝数/简介/邮箱 |
| ⑤ 打分 | `run.py score` | 过滤掉错账号/僵尸号 |
| ⑥ 写文案 | `run.py draft` | 按 pitch.json 生成个性化私信 |
| ⑦ 发送 | `run.py send --limit 20` | 带风控自动发送 |

**一条龙替代**（④~⑦ 全自动）：

```bash
run.py pipeline --limit 20 --dry-run   # 先看文案，不真发
run.py pipeline --limit 20             # 真发
```

**发送的三个模式（风险从高到低）：**

| 模式 | 命令 | 谁点发送 | 风险 |
|---|---|---|---|
| 全自动 | `send --limit 20` | 脚本 | 高（纯机器发） |
| 半自动 | `send --assist --limit 5` | **你** | 低（脚本只填文案） |
| 预览 | `send --dry-run` | 不发送 | 无 |

---

## 5. 日常运营节奏（每天三步）

```bash
# 早上：查谁回复了（只读收件箱，自动标记 replied，不自动发）
run.py watch

# 上午：开看板，人工过一遍（网页里标注意向/标签/备注）
run.py board          # 打开 http://127.0.0.1:8790

# 下午：对「已回复」的人发第二条（media kit + 软性推荐）
run.py second-touch --limit 5 --assist   # 稳妥起见半自动
```

- 没回复的人：4 天后自动 bump 一次，只 bump 一次
- 标注：看板里点「标注」，或命令行 `run.py note @user --intent hot --tags "已约会议" --note "Q4 有预算"`

---

## 6. 风控红线（绝对不能做）

| 红线 | 为什么 |
|---|---|
| 不写死 timezone 成别的地区 | 时区跳变 = 一级风控信号（9/17 challenge 的根因） |
| 不同时开两个浏览器操作同一账号 | 会话冲突 |
| challenge 未解除时跑任何命令 | 加重嫌疑 |
| 首条私信带外链 | 会被折叠进 Requests，且更容易触发风控 |
| 同一句话群发（相似度 >0.72） | 机器特征，脚本会自动重写 |

**账号被 challenge（要求身份验证）的标准处理：**

```
1. 立刻停手，什么都别跑
2. 浏览器里手动完成验证
3. 冷却 3–7 天，只用这台浏览器正常手动刷 IG
4. 每天跑一次 run.py check，直到显示 ok
5. 恢复后只用 --assist 半自动
```

---

## 7. 常见坑 & 排查（踩过的都记在这）

| 症状 | 原因 | 解法 |
|---|---|---|
| 命令卡住没输出 | 前台启动浏览器被沙箱杀 | 浏览器任务必须 `run_in_background` 跑 |
| 启动报 profile 锁 | 残留 Chromium 进程占着 `data/profile` | 用 PowerShell 按 `*ig-agent*profile*` 清理残留进程 |
| 某个账号粉丝数异常低（如 @some_brand=1777） | handle 抓成了同名小号 | 标记 rejected，人工在 IG 搜官方号后补录 |
| 粉丝=0 或抓不到资料 | IG 限流 | 重置为 new 单独重试；仍失败标记 failed 不再卡 |
| 发送报「Target page closed」 | 你中途关了浏览器 | 不计失败、不熔断，队列保留，重跑即可 |
| 文案里出现 `[哇R]` 乱码 | 小红书表情码不兼容 IG | 去掉，只留纯文字 |

---

## 8. 命令速查表

| 命令 | 作用 | 开浏览器 |
|---|---|---|
| `login` | 手动登录，保存会话 | 是 |
| `check` | 只读体检（challenge / block） | 只读 |
| `chrome` | 开调试版真实 Chrome（恢复期用） | 否 |
| `find` | 抓潜在品牌用户名 | 是 |
| `enrich --limit N` | 补全粉丝数/简介/邮箱 | 是 |
| `score` | 打分筛选 | 否 |
| `draft` | 生成个性化文案 | 否 |
| `send --limit N` | 带风控发送 | 是 |
| `watch` | 查谁回复了 | 是 |
| `second-touch` | 对已回复者发第二条 | 是 |
| `note @user --intent hot` | 命令行标注 | 否 |
| `board` | 运营看板（127.0.0.1:8790） | 否 |
| `pipeline` | 一条龙 | 是 |
| `status` | 看漏斗 + 风控额度 | 否 |
| `export` | 导出邮箱 CSV（邮件建联，零风险） | 否 |
| `unfreeze` | 解除熔断 | 否 |
| `dashboard` | 生成看板 `dashboard/index.html` | 否 |

---

## 9. 合规提醒

用脚本自动发 IG 私信**违反 Instagram 服务条款**，可能被封号。你用的是公司品牌号，封掉是品牌资产损失。

- 想零风险：`run.py export` 导出商务邮箱，走**邮件建联**（完全合规，可放心批量发）
- 想继续用 IG 但降低风险：只用 `--assist` 半自动，发送键自己点
