#!/usr/bin/env python3
"""测试特定用例"""
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
MENU_PATH = BASE_DIR / "data" / "menu.json"

with MENU_PATH.open("r", encoding="utf-8") as f:
    MENU = json.load(f)

def _parse_dish_base(cell):
    cell = cell.strip()
    all_base_options = []
    all_sauce_names = [s["name"] for s in MENU["sauces"]]
    for d in MENU["dishes"]:
        all_base_options.extend(d.get("base_options", []))
    
    # 1. 括号格式
    m = re.match(r'^(.+?)[\(（](.+?)[\)）]$', cell)
    if m:
        part_in_bracket = m.group(2).strip()
        if part_in_bracket in all_base_options:
            return m.group(1).strip(), part_in_bracket, ""
        if part_in_bracket in all_sauce_names:
            return m.group(1).strip(), "", part_in_bracket
    
    # 2. 检查是否包含酱料名称
    for sauce_name in all_sauce_names:
        if sauce_name in cell:
            dish_part = cell.replace(sauce_name, "").strip()
            dish_part = re.sub(r'[\+➕加]+$', '', dish_part).strip()
            return dish_part, "", sauce_name
    
    # 3. 分隔符格式
    generic_names = ["三明治", "意面", "荞麦面", "杂粮饭", "谷物碗", "沙拉", "双拼碗"]
    m = re.match(r'^(.+?)[\+➕加](.+)$', cell)
    if m:
        part_a, part_b = m.group(1).strip(), m.group(2).strip()
        if part_a in all_base_options:
            return part_b, part_a, ""
        if part_b in all_base_options:
            return part_a, part_b, ""
        if part_a in all_sauce_names:
            return part_b, "", part_a
        if part_b in all_sauce_names:
            return part_a, "", part_b
        # 如果分隔出来的部分是通用名称，保留为菜品名
        if part_b in generic_names:
            return part_a + part_b, "", ""
        if part_a in generic_names:
            return part_a + part_b, "", ""
        return part_a, part_b, ""
    
    return cell, "", ""

# 测试用例
test_cases = [
    "黑椒鸡肉全麦加三明治",
    "黑椒鸡肉全麦三明治",
    "黑椒鸡胸肉全麦三明治",
]

for cell in test_cases:
    dish, base, sauce = _parse_dish_base(cell)
    print(f"'{cell}' → dish='{dish}', base='{base}', sauce='{sauce}'")
