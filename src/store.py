"""名单与状态存储（SQLite，零依赖）。

状态机：
  new        刚抓到，还没看资料
  enriched   资料补全完成
  qualified  通过打分，等待写文案     (score >= min_score)
  rejected   打分没过
  drafted    文案已生成，等待发送
  sent       已发送，等待回复
  replied    对方回复了 —— 这是你要的
  second_touched 已回复 + 已发第二条（media kit / 达人推荐）
  followed_up 已发过跟进
  failed     发送失败（找不到人 / 对方关闭私信）
  blocked    风控熔断，暂停

意向标注（intent，人工在看板里点）：
  hot   已约会议 / 明确有需求
  warm  有回复、在考虑
  cold  明确拒绝 / 暂时不做
  dead  账号无效 / 不是决策人
"""
import sqlite3
import time
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  username        TEXT PRIMARY KEY,
  full_name       TEXT,
  bio             TEXT,
  followers       INTEGER DEFAULT 0,
  following       INTEGER DEFAULT 0,
  posts           INTEGER DEFAULT 0,
  is_business     INTEGER DEFAULT 0,
  email           TEXT,
  external_url    TEXT,
  source          TEXT,
  discovered_at   REAL,
  score           INTEGER DEFAULT 0,
  tags            TEXT,
  reason          TEXT,
  message         TEXT,
  status          TEXT DEFAULT 'new',
  sent_at         REAL,
  baseline_msgs   INTEGER DEFAULT 0,
  replied_at      REAL,
  reply_snippet   TEXT,
  followup_count  INTEGER DEFAULT 0,
  attempts        INTEGER DEFAULT 0,
  notes           TEXT,
  intent          TEXT,
  second_touched_at REAL,
  second_message  TEXT
);
CREATE INDEX IF NOT EXISTS idx_status ON leads(status);

CREATE TABLE IF NOT EXISTS events (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT,
  kind    TEXT,
  detail   TEXT,
  ts       REAL
);
"""

# 老数据库补列用（CREATE TABLE IF NOT EXISTS 不会给已存在的表加列）
MIGRATIONS = [
    ("intent", "TEXT"),
    ("second_touched_at", "REAL"),
    ("second_message", "TEXT"),
]


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        for col, typ in MIGRATIONS:
            try:
                self.conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass  # 列已存在
        self.conn.commit()

    # ---------- 写入 ----------
    def upsert_lead(self, username: str, **fields):
        username = username.lstrip("@").lower()
        cur = self.conn.execute("SELECT username FROM leads WHERE username=?", (username,))
        if cur.fetchone():
            if fields:
                cols = ", ".join(f"{k}=?" for k in fields)
                self.conn.execute(
                    f"UPDATE leads SET {cols} WHERE username=?",
                    tuple(fields.values()) + (username,),
                )
        else:
            fields.setdefault("discovered_at", time.time())
            fields.setdefault("status", "new")
            cols = "username, " + ", ".join(fields)
            placeholders = ", ".join("?" * (len(fields) + 1))
            self.conn.execute(
                f"INSERT INTO leads ({cols}) VALUES ({placeholders})",
                (username,) + tuple(fields.values()),
            )
        self.conn.commit()

    def update(self, username: str, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(
            f"UPDATE leads SET {cols} WHERE username=?",
            tuple(fields.values()) + (username.lstrip("@").lower(),),
        )
        self.conn.commit()

    def log(self, username: str, kind: str, detail: str = ""):
        self.conn.execute(
            "INSERT INTO events (username, kind, detail, ts) VALUES (?,?,?,?)",
            (username, kind, detail, time.time()),
        )
        self.conn.commit()

    # ---------- 查询 ----------
    def get(self, username: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT * FROM leads WHERE username=?", (username.lstrip("@").lower(),)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def by_status(self, *statuses: str) -> List[Dict[str, Any]]:
        if not statuses:
            cur = self.conn.execute("SELECT * FROM leads ORDER BY discovered_at DESC")
        else:
            q = ",".join("?" * len(statuses))
            cur = self.conn.execute(
                f"SELECT * FROM leads WHERE status IN ({q}) ORDER BY score DESC, discovered_at DESC",
                statuses,
            )
        return [dict(r) for r in cur.fetchall()]

    def all(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM leads").fetchall()]

    def has_event(self, username: str, kind: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM events WHERE username=? AND kind=? LIMIT 1",
            (username.lstrip("@").lower(), kind),
        )
        return cur.fetchone() is not None

    def recent_messages(self, limit: int = 50) -> List[str]:
        cur = self.conn.execute(
            "SELECT message FROM leads WHERE message IS NOT NULL AND message != '' "
            "ORDER BY sent_at DESC LIMIT ?",
            (limit,),
        )
        return [r[0] for r in cur.fetchall() if r[0]]

    def funnel(self) -> Dict[str, int]:
        cur = self.conn.execute("SELECT status, COUNT(*) c FROM leads GROUP BY status")
        return {r[0]: r[1] for r in cur.fetchall()}

    # ---------- 运营查询 ----------
    def needs_second_touch(self) -> List[Dict[str, Any]]:
        """已回复、但还没发第二条的 —— 二次跟进队列。"""
        cur = self.conn.execute(
            "SELECT * FROM leads WHERE status='replied' "
            "AND (second_touched_at IS NULL OR second_touched_at=0) "
            "ORDER BY replied_at ASC")
        return [dict(r) for r in cur.fetchall()]

    def stats(self) -> Dict[str, Any]:
        """看板 KPI + 分来源回复率。"""
        f = self.funnel()
        sent = f.get("sent", 0) + f.get("followed_up", 0) \
            + f.get("replied", 0) + f.get("second_touched", 0)
        replied = f.get("replied", 0) + f.get("second_touched", 0)
        total = sum(f.values())
        by_source = {}
        cur = self.conn.execute(
            "SELECT source, status, COUNT(*) c FROM leads GROUP BY source, status")
        for src, st, c in cur.fetchall():
            d = by_source.setdefault(src or "unknown", {})
            d[st] = c
        src_rows = []
        for src, d in sorted(by_source.items(),
                             key=lambda kv: -sum(kv[1].values())):
            s = d.get("sent", 0) + d.get("followed_up", 0) \
                + d.get("replied", 0) + d.get("second_touched", 0)
            r = d.get("replied", 0) + d.get("second_touched", 0)
            src_rows.append({
                "source": src, "total": sum(d.values()), "sent": s,
                "replied": r, "rate": round(r / s * 100, 1) if s else 0,
            })
        intent_rows = {}
        cur = self.conn.execute(
            "SELECT intent, COUNT(*) c FROM leads WHERE intent IS NOT NULL AND intent != '' "
            "GROUP BY intent")
        for it, c in cur.fetchall():
            intent_rows[it] = c
        return {
            "total": total, "sent": sent, "replied": replied,
            "rate": round(replied / sent * 100, 1) if sent else 0,
            "awaiting_reply": f.get("sent", 0) + f.get("followed_up", 0),
            "second_touch_queue": len(self.needs_second_touch()),
            "annotated": sum(intent_rows.values()),
            "intents": intent_rows,
            "by_source": src_rows,
            "funnel": f,
        }

    def close(self):
        self.conn.close()
