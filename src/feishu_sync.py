"""本地建联台账 → 飞书多维表格（Base）同步。

把 SQLite 里的建联数据同步到飞书多维表格，支持增量：
  - 按「IG账号」字段匹配：飞书里已有的记录做更新，没有的做新增
  - 每天 9:00 自动运营时调用一次，飞书在线文档永远是新的

依赖：飞书 CLI `lark-cli`（已通过 WorkBuddy 飞书连接器完成认证）。
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .report import (  # noqa: E402
    ACTION_STATUSES, DIRECTION_LABEL, STATUS_LABEL,
    classify_direction,
)

# 飞书多维表格坐标 —— 凭证不写死在源码里，否则公开仓库会暴露你的私表地址。
# 读取顺序：环境变量 FEISHU_BASE_TOKEN / FEISHU_TABLE_ID → config/feishu.local.json（已 gitignore）
def _feishu_credentials():
    tok = os.environ.get("FEISHU_BASE_TOKEN", "").strip()
    tid = os.environ.get("FEISHU_TABLE_ID", "").strip()
    if tok and tid:
        return tok, tid
    p = Path(__file__).resolve().parent.parent / "config" / "feishu.local.json"
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            tok = (d.get("base_token") or "").strip()
            tid = (d.get("table_id") or "").strip()
            if tok and tid:
                return tok, tid
        except Exception:
            pass
    return "", ""


BASE_TOKEN, TABLE_ID = _feishu_credentials()
BASE_URL = f"https://my.feishu.cn/base/{BASE_TOKEN}" if BASE_TOKEN else ""

# 本地状态 → 飞书 select 选项（必须与飞书表 options 完全一致）
STATUS_OPTION = {
    "drafted": "待发送",
    "sent": "已发送·待回复",
    "replied": "已回复",
    "second_touched": "已回复·已跟进",
    "followed_up": "已跟进·待回复",
    "failed": "发送失败",
    "rejected": "已淘汰",
}

# 个人飞书 profile（非 Transsion 租户）
LARK = ["lark-cli.cmd", "base", "--profile", "personal"]


def _lark(args, **kw):
    r = subprocess.run(LARK + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    return r.stdout, r.stderr, r.returncode


def _lark_json(args, payload: dict, **kw):
    """payload 中文较多时，内联 --json 在 Windows 命令行会乱码，
    所以写临时 UTF-8 文件后用 --json @file 传递。"""
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     encoding="utf-8", delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        path = f.name
    try:
        return _lark(args + ["--json", "@" + path, "--as", "user"], **kw)
    finally:
        try:
            Path(path).unlink()
        except Exception:
            pass


def _ms(ts):
    """秒级 unix → 毫秒时间戳；空值返回 None。"""
    if not ts:
        return None
    return int(float(ts) * 1000)


def _direction(lead):
    intent = (lead.get("intent") or "").strip()
    if intent in ("hot", "warm", "cold"):
        return DIRECTION_LABEL[intent]
    d = (lead.get("direction") or "").strip()
    if d in ("hot", "warm", "cold", "pending"):
        return DIRECTION_LABEL[d]
    return DIRECTION_LABEL[classify_direction(lead.get("reply_snippet"))]


def build_records(store):
    """本地 SQLite → 飞书记录列表（每条的 key 是 IG账号，用于 diff）。"""
    leads = [l for l in store.all() if l.get("status") in ACTION_STATUSES]
    leads.sort(key=lambda l: -(l.get("sent_at") or 0))
    out = {}
    for l in leads:
        st = l.get("status")
        out[l["username"]] = {
            "品牌": l.get("full_name") or "",
            "IG账号": "@" + (l.get("username") or ""),
            "粉丝数": l.get("followers") or 0,
            "状态": [STATUS_OPTION.get(st, st)],
            "发送时间": _ms(l.get("sent_at")),
            "回复时间": _ms(l.get("replied_at")),
            "回复内容": (l.get("reply_snippet") or "")[:500],
            "回复方向": [_direction(l)],
            "邮箱": (l.get("email") or "")[:60],
            "社交线索": (l.get("social_links") or "")[:200],
            "备注": (l.get("notes") or "")[:300],
        }
    return out


def fetch_remote():
    """读飞书表现有记录，返回 {IG账号: record_id}（分页取全量）。"""
    mapping = {}
    offset = 0
    while True:
        out, err, code = _lark(["+record-list", "--base-token", BASE_TOKEN,
                                "--table-id", TABLE_ID,
                                "--format", "json",
                                "--offset", str(offset),
                                "--limit", "200", "--as", "user"])
        if code != 0:
            return mapping, f"record-list 失败: {err or out[:200]}"
        try:
            data = json.loads(out).get("data", {})
        except Exception:
            return mapping, f"record-list 解析失败: {out[:200]}"
        ids = data.get("record_id_list", [])
        rows = data.get("data", [])
        # 字段顺序以表头为准，动态定位「IG账号」列
        fields = data.get("fields") or []
        try:
            acct_idx = fields.index("IG账号")
        except ValueError:
            acct_idx = 0
        for rid, row in zip(ids, rows):
            if rid and row:
                acct = str(row[acct_idx]).lstrip("@").lower()
                mapping[acct] = rid
        if not data.get("has_more"):
            break
        offset += len(ids)
    return mapping, None


def sync(store) -> dict:
    """增量同步：新增 + 更新，返回统计。"""
    if not BASE_TOKEN or not TABLE_ID:
        print("[feishu] 未配置飞书凭证：请设置环境变量 FEISHU_BASE_TOKEN / FEISHU_TABLE_ID，"
              "或创建 config/feishu.local.json（参考 config/feishu.local.example.json）")
        return {"error": "no feishu credentials"}
    local = build_records(store)
    remote, err = fetch_remote()
    if err:
        print(f"[feishu] 读取飞书表失败：{err}")
        return {"error": err}

    to_create, to_update = [], {}
    for username, rec in local.items():
        if username in remote:
            to_update[remote[username]] = rec
        else:
            to_create.append(rec)

    created = updated = 0
    # 批量新增（每批最多 200）
    for i in range(0, len(to_create), 200):
        batch = to_create[i:i + 200]
        out, err, code = _lark_json(["+record-batch-create", "--base-token", BASE_TOKEN,
                                     "--table-id", TABLE_ID],
                                    {"create_records": batch})
        if code == 0:
            created += len(batch)
        else:
            print(f"[feishu] 新增失败：{err or out[:200]}")

    # 批量更新
    if to_update:
        out, err, code = _lark_json(["+record-batch-update", "--base-token", BASE_TOKEN,
                                     "--table-id", TABLE_ID],
                                    {"update_records": to_update})
        if code == 0:
            updated = len(to_update)
        else:
            print(f"[feishu] 更新失败：{err or out[:200]}")

    result = {"created": created, "updated": updated, "url": BASE_URL}
    print(f"[feishu] 同步完成：新增 {created} 条，更新 {updated} 条")
    print(f"[feishu] 在线表格：{BASE_URL}")
    return result


def sync_cli(store):
    """供 run.py 调用。"""
    return sync(store)
