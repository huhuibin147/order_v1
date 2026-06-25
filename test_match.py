#!/usr/bin/env python3
"""测试菜品匹配逻辑"""
import json
import sys
from pathlib import Path

# 加载菜单数据
BASE_DIR = Path(__file__).parent
MENU_PATH = BASE_DIR / "data" / "menu.json"
with MENU_PATH.open("r", encoding="utf-8") as f:
    MENU = json.load(f)

# 导入匹配函数（需要先设置 Flask app 上下文）
sys.path.insert(0, str(BASE_DIR))

# 模拟 app.py 中的关键函数
def _char_overlap(a: str, b: str) -> float:
    if not a or not b:
        return 0
    overlap = sum(1 for c in a if c in b)
    return overlap / max(len(a), len(b))

_DISH_SYNONYM_GROUPS = [
    ["杂粮饭", "杂粮碗", "谷物碗", "谷物饭"],
    ["杂粮", "谷物"],
]

_DISH_ABBREVIATIONS = {
    "藤椒三明治": "藤椒鸡腿肉全麦三明治",
    "黑椒三明治": "黑椒鸡胸肉全麦三明治",
}

def _dish_variants(name: str) -> list[str]:
    variants = {name}
    if name in _DISH_ABBREVIATIONS:
        variants.add(_DISH_ABBREVIATIONS[name])
    for group in _DISH_SYNONYM_GROUPS:
        for word in group:
            if word in name:
                for alt in group:
                    if alt != word:
                        variants.add(name.replace(word, alt))
    return list(variants)

def _match_dish(name: str):
    variants = _dish_variants(name)
    # 1. 精确匹配
    for d in MENU["dishes"]:
        if d["name"] == name or d["name"] in variants:
            return d
    # 2. 品类匹配
    categories = ["三明治", "双拼碗", "谷物碗", "沙拉", "意面", "荞麦面"]
    for cat in categories:
        if cat in name:
            cat_dishes = [d for d in MENU["dishes"] if cat in d["name"]]
            if len(cat_dishes) == 1:
                return cat_dishes[0]
            # 三明治品类用关键词区分
            if cat == "三明治":
                keywords = ["藤椒", "黑椒", "鸡腿肉", "鸡胸肉"]
                input_kws = [kw for kw in keywords if kw in name]
                if input_kws:
                    scored = []
                    for d in cat_dishes:
                        match_count = sum(1 for kw in input_kws if kw in d["name"])
                        scored.append((match_count, d))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    if scored[0][0] > 0:
                        return scored[0][1]
            # 用字符重叠率选最佳
            best, best_score = None, 0
            for d in cat_dishes:
                score = max(_char_overlap(v, d["name"]) for v in variants)
                if score > best_score:
                    best_score = score
                    best = d
            if best:
                return best
    # 3. 子串匹配
    for d in MENU["dishes"]:
        for v in variants:
            if d["name"] in v or v in d["name"]:
                return d
    # 4. 字符重叠兜底
    best, best_score = None, 0
    for d in MENU["dishes"]:
        score = max(_char_overlap(v, d["name"]) for v in variants)
        if score > best_score:
            best_score = score
            best = d
    if best_score >= 0.6:
        return best
    return None

def _match_sauce(name: str):
    if not name:
        return None
    name = name.strip()
    for s in MENU["sauces"]:
        if s["name"] == name:
            return s["id"]
    for s in MENU["sauces"]:
        if name in s["name"] or s["name"] in name:
            return s["id"]
    return None

def _parse_dish_base(cell: str):
    import re
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
            # 允许 dish_part 为空（单元格只有酱料名称）
            return dish_part, "", sauce_name
    # 3. 分隔符格式
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
        return part_a, part_b, ""
    return cell, "", ""

# 测试用例
def test_parse_dish_base():
    print("\n=== 测试 _parse_dish_base ===")
    test_cases = [
        # (输入, 期望的 dish_name, 期望的 base, 期望的 sauce)
        ("鸡胸肉牛肉双拼碗（荞麦面）", "鸡胸肉牛肉双拼碗", "荞麦面", ""),
        ("黑椒鸡胸肉全麦三明治+紫薯酸奶杯", "黑椒鸡胸肉全麦三明治", "", "紫薯酸奶杯"),
        ("藤椒鸡腿肉全麦三明治➕紫薯酸奶杯", "藤椒鸡腿肉全麦三明治", "", "紫薯酸奶杯"),
        ("藤椒鸡腿肉全麦三明治加芋泥酸奶杯", "藤椒鸡腿肉全麦三明治", "", "芋泥酸奶杯"),
        ("藤椒鸡腿肉全麦三明治紫薯酸奶杯", "藤椒鸡腿肉全麦三明治", "", "紫薯酸奶杯"),
        ("黑椒鸡胸肉全麦三明治（紫薯酸奶杯）", "黑椒鸡胸肉全麦三明治", "", "紫薯酸奶杯"),
        ("黑椒鸡胸肉全麦三明治（三明治）", "黑椒鸡胸肉全麦三明治（三明治）", "", ""),  # 括号内容无效
        ("黑椒牛肉意面", "黑椒牛肉意面", "", ""),
        ("紫薯酸奶杯", "", "", "紫薯酸奶杯"),  # 只有酱料，没有菜品
        ("芋泥酸奶杯", "", "", "芋泥酸奶杯"),  # 只有酱料，没有菜品
    ]
    
    passed = 0
    for cell, exp_dish, exp_base, exp_sauce in test_cases:
        dish, base, sauce = _parse_dish_base(cell)
        ok = (dish == exp_dish and base == exp_base and sauce == exp_sauce)
        status = "✓" if ok else "✗"
        print(f"  {status} '{cell}' → dish='{dish}', base='{base}', sauce='{sauce}'")
        if not ok:
            print(f"      期望: dish='{exp_dish}', base='{exp_base}', sauce='{exp_sauce}'")
        else:
            passed += 1
    print(f"  通过: {passed}/{len(test_cases)}")

def test_match_dish():
    print("\n=== 测试 _match_dish ===")
    test_cases = [
        ("黑椒牛肉意面", "黑椒牛肉意面"),
        ("炙烤原切牛排意面", "炙烤原切牛排意面"),
        ("嫩烤巴沙鱼荞麦面", "嫩烤巴沙鱼荞麦面"),
        ("蒜蓉开背大虾炒意面", "蒜蓉开背大虾炒意面"),
        ("低卡虾仁荞麦面", "低卡虾仁荞麦面"),
        ("原味烤肠咖喱杂粮饭", "原味烤肠咖喱杂粮饭"),
        ("香熏鸡肉荞麦面", "香薰鸡肉荞麦面"),  # 熏 vs 薰
        ("藤椒鸡腿肉全麦三明治", "藤椒鸡腿肉全麦三明治"),
        ("黑椒鸡胸肉全麦三明治", "黑椒鸡胸肉全麦三明治"),
        ("黑椒鸡腿肉全麦三明治", "黑椒鸡胸肉全麦三明治"),  # 黑椒优先级高
    ]
    
    passed = 0
    for input_name, exp_name in test_cases:
        dish = _match_dish(input_name)
        actual = dish["name"] if dish else None
        ok = (actual == exp_name)
        status = "✓" if ok else "✗"
        print(f"  {status} '{input_name}' → '{actual}'")
        if not ok:
            print(f"      期望: '{exp_name}'")
        else:
            passed += 1
    print(f"  通过: {passed}/{len(test_cases)}")

def test_match_sauce():
    print("\n=== 测试 _match_sauce ===")
    test_cases = [
        ("紫薯酸奶杯", "s_purple_yogurt"),
        ("芋泥酸奶杯", "s_taro_yogurt"),
        ("牛肉辣酱", "s_beef_chili"),
        ("黑胡椒汁", "s_black_pepper"),
    ]
    
    passed = 0
    for name, exp_id in test_cases:
        sauce_id = _match_sauce(name)
        ok = (sauce_id == exp_id)
        status = "✓" if ok else "✗"
        print(f"  {status} '{name}' → '{sauce_id}'")
        if not ok:
            print(f"      期望: '{exp_id}'")
        else:
            passed += 1
    print(f"  通过: {passed}/{len(test_cases)}")

if __name__ == "__main__":
    test_parse_dish_base()
    test_match_dish()
    test_match_sauce()
    print("\n测试完成!")
