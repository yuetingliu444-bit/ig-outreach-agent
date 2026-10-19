"""风控闸门：配额、时间窗、随机间隔、养号期、熔断。

这是整个 Agent 里最重要的模块。Instagram 对自动化私信的检测主要看：
  1) 单位时间内的操作量         -> daily_cap / hourly_cap
  2) 操作的机械规律性           -> 随机间隔 + 随机打字速度
  3) 内容的重复度               -> 相似度检测（在 copywriter 里）
  4) 账号"年龄"与行为积累       -> 养号期，前 N 天降额
  5) 异常反馈                   -> 页面出现限制提示立刻熔断

熔断一旦触发，默认冷却 24 小时，期间任何发送都会被拒绝。
"""
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import selectors as sel


class SafetyGuard:
    def __init__(self, cfg, data_dir: Path):
        s = cfg.settings.get("safety", {})
        self.daily_cap = s.get("daily_cap", 35)
        self.hourly_cap = s.get("hourly_cap", 6)
        self.min_interval = s.get("min_interval_sec", 240)
        self.max_interval = s.get("max_interval_sec", 720)
        self.active_hours = s.get("active_hours", {"start": 9, "end": 21})
        self.active_days = s.get("active_days", [0, 1, 2, 3, 4, 5, 6])
        self.warmup_days = s.get("warmup_days", 7)
        self.warmup_daily_cap = s.get("warmup_daily_cap", 8)
        self.max_consecutive_failures = s.get("max_consecutive_failures", 3)
        self.cooldown_hours = s.get("cooldown_after_block_hours", 24)

        self.warmup_start = cfg.s("account", "warmup_start_date")
        self.state_path = data_dir / "safety_state.json"
        self.state = self._load()

    # ---------- 状态 ----------
    def _load(self):
        if self.state_path.exists():
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"date": "", "sent_today": 0, "by_hour": {}, "consecutive_failures": 0,
                "blocked_until": 0, "block_reason": "", "last_sent_at": 0, "total_sent": 0}

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _rollover(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            self.state["date"] = today
            self.state["sent_today"] = 0
            self.state["by_hour"] = {}
            self.state["consecutive_failures"] = 0
            self._save()

    # ---------- 养号 ----------
    def in_warmup(self) -> bool:
        if not self.warmup_start:
            return False
        try:
            start = datetime.strptime(self.warmup_start, "%Y-%m-%d")
        except Exception:
            return False
        return datetime.now() < start + timedelta(days=self.warmup_days)

    def effective_daily_cap(self) -> int:
        return self.warmup_daily_cap if self.in_warmup() else self.daily_cap

    # ---------- 检查 ----------
    def can_send(self) -> tuple:
        """返回 (是否允许, 原因)"""
        self._rollover()
        now = time.time()

        if now < self.state.get("blocked_until", 0):
            until = datetime.fromtimestamp(self.state["blocked_until"]).strftime("%m-%d %H:%M")
            return False, f"熔断中，{until} 之后恢复（原因：{self.state.get('block_reason','')}）"

        if datetime.now().weekday() not in self.active_days:
            return False, "今天不在允许发送的星期内"

        hour = datetime.now().hour
        if not (self.active_hours["start"] <= hour < self.active_hours["end"]):
            return False, f"不在工作时间窗（{self.active_hours['start']}:00-{self.active_hours['end']}:00）"

        cap = self.effective_daily_cap()
        if self.state["sent_today"] >= cap:
            return False, f"今日配额已满 {self.state['sent_today']}/{cap}"

        hkey = str(hour)
        if self.state["by_hour"].get(hkey, 0) >= self.hourly_cap:
            return False, f"本小时配额已满（{self.hourly_cap} 条）"

        last = self.state.get("last_sent_at", 0)
        if last and (now - last) < self.min_interval:
            wait = int(self.min_interval - (now - last))
            return False, f"距上一条仅 {int(now-last)}s，还需等待 {wait}s"

        return True, "ok"

    def next_interval(self) -> int:
        return random.randint(self.min_interval, self.max_interval)

    # ---------- 记账 ----------
    def record_send(self):
        self._rollover()
        self.state["sent_today"] += 1
        self.state["total_sent"] = self.state.get("total_sent", 0) + 1
        hkey = str(datetime.now().hour)
        self.state["by_hour"][hkey] = self.state["by_hour"].get(hkey, 0) + 1
        self.state["last_sent_at"] = time.time()
        self.state["consecutive_failures"] = 0
        self._save()

    def record_failure(self, reason: str = ""):
        self._rollover()
        self.state["consecutive_failures"] = self.state.get("consecutive_failures", 0) + 1
        self._save()
        if self.state["consecutive_failures"] >= self.max_consecutive_failures:
            self.trip(f"连续失败 {self.state['consecutive_failures']} 次：{reason}")

    def trip(self, reason: str, hours: int = None):
        hours = hours if hours is not None else self.cooldown_hours
        self.state["blocked_until"] = time.time() + hours * 3600
        self.state["block_reason"] = reason
        self.state["consecutive_failures"] = 0
        self._save()

    def reset_block(self):
        self.state["blocked_until"] = 0
        self.state["block_reason"] = ""
        self._save()

    def summary(self) -> str:
        self._rollover()
        cap = self.effective_daily_cap()
        tag = " [养号期]" if self.in_warmup() else ""
        blocked = ""
        if time.time() < self.state.get("blocked_until", 0):
            blocked = " ⚠ 熔断中"
        return (f"今日 {self.state['sent_today']}/{cap}{tag}{blocked} ｜ "
                f"累计 {self.state.get('total_sent',0)} 条")

    # ---------- 页面检测 ----------
    @staticmethod
    def looks_blocked(page_text: str) -> str:
        for p in sel.BLOCK_PHRASES:
            if p.lower() in (page_text or "").lower():
                return p
        return ""
