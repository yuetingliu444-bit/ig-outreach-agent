"""Instagram 网页端选择器集中管理。

Instagram 前端改版非常频繁，所有选择器集中在这一个文件里。
一旦脚本找不到元素，只需要改这里，不用动业务代码。
每个条目都是"候选列表"，按顺序尝试，命中第一个可见的就用。
"""

# ---------- 登录态 ----------
# IG 界面语言会随浏览器/账号语言切换（中文界面 aria-label 是「首页」「新建帖子」），
# 所以每个文本类选择器都要中英双语候选，否则语言一翻全链路失效。
LOGGED_IN_MARKERS = [
    'a[href="/direct/inbox/"]',
    'svg[aria-label="Home"]',
    'svg[aria-label="首页"]',
    '[aria-label="New post"]',
    '[aria-label="新建帖子"]',
]

LOGIN_FORM = [
    'input[name="username"]',
    'input[aria-label="Phone number, username, or email"]',
    'input[aria-label="手机号、用户名或邮箱"]',
]

# ---------- 个人主页 ----------
PROFILE_OG_DESCRIPTION = 'meta[property="og:description"]'
PROFILE_BIO_BLOCK = [
    'header section > div',
    'section > div > span',
]
PROFILE_EMAIL_BUTTON = [
    'a[href^="mailto:"]',
    'div[role="button"]:has-text("Email")',
    'div[role="button"]:has-text("邮箱")',
    'div[role="button"]:has-text("电子邮件")',
]
PROFILE_EXTERNAL_LINK = [
    'header a[href*="l.instagram.com"]',
    'header a[target="_blank"]',
]

# ---------- 新建私信 ----------
NEW_MESSAGE_ENTRY = [
    'svg[aria-label="New message"]',
    'div[role="button"]:has-text("Send message")',
    'div[role="button"]:has-text("发消息")',
    'a[href="/direct/new/"]',
]

DM_SEARCH_INPUT = [
    'input[name="queryBox"]',
    'input[placeholder="Search..."]',
    'input[placeholder="搜索"]',
    'input[aria-label="Search input"]',
    'input[aria-label="搜索输入框"]',
    'div[role="dialog"] input',
]

DM_RESULT_CANDIDATES = [
    'div[role="dialog"] div[role="button"]',
    'div[role="dialog"] [data-testid="user-result"]',
]

DM_NEXT_BUTTON = [
    'div[role="button"]:has-text("Chat")',
    'div[role="button"]:has-text("Next")',
    'div[role="button"]:has-text("聊天")',
    'div[role="button"]:has-text("下一页")',
    'button:has-text("Next")',
]

# ---------- 主页发起私信（主流程） ----------
# IG 新版：/direct/new/ 的搜索经常搜不到真人账号（只返回高仿号），
# 最可靠的是打开对方主页 → 点「发消息」→ 底部弹出内联 composer。
PROFILE_MESSAGE_BUTTON = [
    'div[role="button"]:has-text("发消息")',
    'div[role="button"]:has-text("Message")',
    'button:has-text("Message")',
    'header div[role="button"]:has-text("消息")',
]

# ---------- 内联 composer ----------
DM_MESSAGE_INPUT = [
    "div[contenteditable='true'][role='textbox']",
    'div[role="textbox"][aria-label="Message"]',
    'div[aria-label="Message"][contenteditable="true"]',
    'textarea[placeholder="Message..."]',
    'textarea[placeholder="发消息..."]',
    'div[contenteditable="true"][role="textbox"]',
    'div[role="textbox"]',
]

# 发送按钮：打完字才出现，且是 aria-label 形式（中文界面「发送」）
DM_SEND_BUTTON = [
    '[aria-label="发送"]',
    '[aria-label="Send"]',
    'div[role="button"]:has-text("发送")',
    'div[role="button"]:has-text("Send")',
    'button:has-text("Send")',
    'svg[aria-label="Send"]',
]

# ---------- 收件箱 ----------
INBOX_THREAD = [
    'div[role="listitem"]',
    '[aria-label="Chats"] > div > div',
]

THREAD_MESSAGE = [
    'div[role="row"]',
    'div[class*="message"]',
]

# ---------- 风控：页面出现这些文字 = 被限制 ----------
BLOCK_PHRASES = [
    "Action Blocked",
    "Try Again Later",
    "We restrict certain activity",
    "temporarily blocked",
    "unusual activity",
    "Please wait a few minutes",
    " confirming it's you",
    "Suspicious Login Attempt",
    "suspect automated behavior",
    # 中文界面
    "操作过于频繁",
    "暂时限制",
    "已被限制",
    "异常活动",
    "请稍等几分钟",
]

# ---------- 身份验证挑战（碰到必须立刻停手） ----------
CHALLENGE_URL_HINTS = ["challenge", "scraping_warning", "checkpoint", "confirmemail"]
CHALLENGE_TEXT_HINTS = [
    "suspect automated behavior",
    "confirm it's you",
    "confirm your identity",
    "suspicious login attempt",
    "we noticed unusual activity",
    "verify it's you",
    # 中文界面
    "检测到异常活动",
    "确认是您本人",
    "确认您的身份",
    "可疑的登录",
]

# ---------- 探索页 / 发现 ----------
EXPLORE_TAG_POST_LINK = 'a[href^="/p/"], a[href^="/reel/"]'
EXPLORE_SEARCH_RESULT = 'a[href^="/"]'
FOLLOWERS_DIALOG = [
    'div[role="dialog"]',
]
