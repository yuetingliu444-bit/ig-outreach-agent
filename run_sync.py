import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.store import Store
from src.feishu_sync import sync

store = Store("data/outreach.db")
result = sync(store)
print("RESULT:", result)
