"""配置前置校验（P0 安全闸）。

在 draft / send 之前强制检查 brand.json / pitch.json：
  1) 文件是否存在 —— 不存在给出清晰的初始化命令；
  2) 是否还残留示例占位符 —— 命中则直接终止，避免发出带
     "（填你的品牌名）" / "[Brand A]" 这类模板字样的垃圾私信，造成公关事故。

返回 True 表示配置可用，False 表示已拦截（并已在 stderr/stdout 打印原因）。
"""
import json
import re
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

# 必须存在的配置文件（缺失即拦截）
REQUIRED_FILES = {
    "brand.json": "品牌档案（决定文案质量）",
    "pitch.json": "话术模板（首条 / 第二条 / 跟进文案）",
}

# 命中任一即视为「未替换的模板」
PLACEHOLDER_PATTERNS = [
    re.compile(r"\[[^\]]+\]"),          # [Brand A] / [品牌A]
    re.compile(r"example\.com", re.I),  # https://your-media-kit.example.com
    re.compile(r"示例"),                 # （示例·虚构品牌）
    re.compile(r"留空"),                 # （示例留空：...）
    re.compile(r"填你的"),               # （填你的品牌名）
    re.compile(r"Your Agency", re.I),   # 示例里的机构签名占位
    re.compile(r"AuroraAudio"),         # 示例虚构品牌名
    re.compile(r"占位"),                 # 占位符
    re.compile(r"\bTODO\b", re.I),       # TODO
    re.compile(r"xxxx+", re.I),          # xxxx 占位
]

# 关键字段为空也视为没配置好
REQUIRED_FIELDS = {
    "brand.json": [("brand_name", "品牌名"), ("target_categories", "目标品类"), ("target_regions", "目标地区")],
    "pitch.json": [("pitch_en", "英文话术"), ("pitch_zh", "中文话术"), ("signature", "机构签名")],
}


def _scan_placeholders(obj, path=""):
    """递归扫描字符串值里的占位符，返回 [(字段路径, 命中片段)]。"""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += _scan_placeholders(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _scan_placeholders(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        s = obj.strip()
        if not s:
            return hits
        for pat in PLACEHOLDER_PATTERNS:
            m = pat.search(s)
            if m:
                hits.append((path, s[:80]))
                break
    return hits


def validate() -> bool:
    """校验配置。返回 False 时已在标准输出打印清晰原因，调用方应直接 return。"""
    # 1) 文件存在性
    missing = []
    raw = {}
    for fname, desc in REQUIRED_FILES.items():
        p = CONFIG_DIR / fname
        if not p.exists():
            missing.append((fname, desc))
            continue
        try:
            raw[fname] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print("!" * 64)
            print(f"!! {fname} 不是合法 JSON，请把括号 / 引号改对：{e}")
            print("!" * 64)
            return False

    if missing:
        print("!" * 64)
        print("!! 缺少配置文件，无法继续。请先初始化（复制示例模板并填写）：")
        for fname, desc in missing:
            print(f"!!   cp config/{fname}.example config/{fname}    # {desc}")
        print("!! 或运行：python run.py init")
        print("!! 然后编辑里面的内容（把占位符换成你自己的真实信息），再重跑。")
        print("!" * 64)
        return False

    # 2) 关键字段非空
    bad_fields = []
    for fname, fields in REQUIRED_FIELDS.items():
        obj = raw.get(fname, {})
        for key, label in fields:
            val = obj.get(key)
            if val is None or (isinstance(val, str) and not val.strip()):
                bad_fields.append((fname, key, label))
    if bad_fields:
        print("!" * 64)
        print("!! 以下配置字段为空，请先填写：")
        for fname, key, label in bad_fields:
            print(f"!!   {fname} -> {key}（{label}）")
        print("!" * 64)
        return False

    # 3) 占位符扫描
    bad = []
    for fname, obj in raw.items():
        for field, snippet in _scan_placeholders(obj, fname):
            bad.append((fname, field, snippet))
    if bad:
        print("!" * 64)
        print("!! 检测到未替换的占位符 —— 发出的私信会带模板字样，已终止。")
        for fname, field, snippet in bad:
            print(f"!!   {fname} -> {field}: {snippet!r}")
        print("!! 请打开对应 config 文件，把占位内容替换成你自己的真实信息。")
        print("!" * 64)
        return False

    return True
