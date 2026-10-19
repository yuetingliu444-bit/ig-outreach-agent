"""配置加载。全部用 JSON，避免额外依赖。"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)


def _load_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class Config:
    def __init__(self):
        self.settings = _load_json(CONFIG_DIR / "settings.json")
        self.brand = _load_json(CONFIG_DIR / "brand.json")
        targets_path = CONFIG_DIR / "targets.json"
        self.targets = _load_json(
            targets_path,
            {"hashtags": [], "keywords": [], "competitors": [], "max_per_source": 60},
        )
        self.pitch = _load_json(CONFIG_DIR / "pitch.json")

    def save_targets(self, targets: dict):
        with open(CONFIG_DIR / "targets.json", "w", encoding="utf-8") as f:
            json.dump(targets, f, ensure_ascii=False, indent=2)
        self.targets = targets

    def s(self, *path, default=None):
        """按路径取 settings 里的值，如 s('safety','daily_cap')"""
        cur = self.settings
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return default
            cur = cur[p]
        return cur

    @property
    def profile_dir(self) -> str:
        d = self.s("account", "profile_dir", default="data/profile")
        return str(BASE_DIR / d)

    @property
    def db_path(self) -> str:
        return str(DATA_DIR / "outreach.db")


def load() -> Config:
    return Config()
