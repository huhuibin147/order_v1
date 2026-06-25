#!/usr/bin/env python3
"""测试酱料匹配"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
MENU_PATH = BASE_DIR / "data" / "menu.json"
with MENU_PATH.open("r", encoding="utf-8") as f:
    MENU = json.load(f)

def _char_overlap(a, b):
    if not a or not b:
        return 0
    overlap = sum(1 for c in a if c in b)
    return overlap / max(len(a), len(b))

def _match_sauce(name):
    if not name:
        return None
    name = name.strip()
    # 1. 精确匹配
    for s in MENU["sauces"]:
        if s["name"] == name:
            return s["id"]
    # 2. 子串匹配
    for s in MENU["sauces"]:
        if name in s["name"] or s["name"] in name:
            return s["id"]
    # 3. 去掉通用后缀，用关键词子串匹配
    suffixes = ["沙拉汁", "芝麻酱", "沙拉酱", "甜辣酱", "辣酱", "酱", "汁"]
    core = name
    for suf in suffixes:
        if core.endswith(suf) and len(core) > len(suf):
            core = core[:-len(suf)]
            break
    # 先试 2 字子串
    if len(core) >= 2:
        for i in range(len(core) - 1):
            seg = core[i:i+2]
            for s in MENU["sauces"]:
                if seg in s["name"]:
                    return s["id"]
    # 再试逐字匹配
    for c in core:
        for s in MENU["sauces"]:
            if c in s["name"]:
                return s["id"]
    # 4. 字符重叠兜底
    best_id, best_score = None, 0
    for s in MENU["sauces"]:
        score = _char_overlap(name, s["name"])
        if score > best_score:
            best_score = score
            best_id = s["id"]
    if best_score >= 0.6:
        return best_id
    return None

# 测试
test_cases = [
    ("芋泥酸奶杯", "s_taro_yogurt"),
    ("芋泥酸奶", "s_taro_yogurt"),
    ("紫薯酸奶杯", "s_purple_yogurt"),
    ("紫薯酸奶", "s_purple_yogurt"),
    ("牛肉酱", None),  # 不确定是哪个
    ("牛肉辣酱", "s_beef_chili"),
]

for name, expected in test_cases:
    result = _match_sauce(name)
    status = "✓" if result == expected else "✗"
    print(f"{status} '{name}' → '{result}' (expected: '{expected}')")
