#!/usr/bin/env python3
"""分析所有 Excel 文件，测试匹配逻辑"""
import json
import sys
from pathlib import Path
import xlrd

BASE_DIR = Path(__file__).parent
MENU_PATH = BASE_DIR / "data" / "menu.json"
TESTFILE_DIR = BASE_DIR / "testfile"

with MENU_PATH.open("r", encoding="utf-8") as f:
    MENU = json.load(f)

# 匹配函数
def _char_overlap(a, b):
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

def _dish_variants(name):
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

def _match_dish(name):
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
    # 3. 去掉通用后缀
    suffixes = ["沙拉汁", "芝麻酱", "沙拉酱", "甜辣酱", "辣酱", "酱", "汁"]
    core = name
    for suf in suffixes:
        if core.endswith(suf) and len(core) > len(suf):
            core = core[:-len(suf)]
            break
    if len(core) >= 2:
        for i in range(len(core) - 1):
            seg = core[i:i+2]
            for s in MENU["sauces"]:
                if seg in s["name"]:
                    return s["id"]
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

def _parse_dish_base(cell):
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

def analyze_file(filepath):
    print(f"\n{'='*60}")
    print(f"文件: {filepath.name}")
    print('='*60)
    
    wb = xlrd.open_workbook(str(filepath))
    issues = []
    
    for sheet_name in wb.sheet_names():
        if sheet_name == '菜单':
            continue
        ws = wb.sheet_by_index(wb.sheet_names().index(sheet_name))
        if ws.nrows < 3:
            continue
            
        print(f"\n--- Sheet: {sheet_name} ---")
        
        # 检测格式
        headers = [str(ws.cell_value(1, j) or '').strip() for j in range(ws.ncols)]
        is_v2 = len(headers) >= 7 and '主食' in str(headers[4]) if len(headers) > 4 else False
        
        for r in range(2, ws.nrows):
            if is_v2:
                # v2 格式：序号, 部门, 姓名, 菜品, 主食, 酱料, 园区
                seq = ws.cell_value(r, 0)
                if not seq:
                    continue
                user = str(ws.cell_value(r, 2) or '').strip()
                dish_cell = str(ws.cell_value(r, 3) or '').strip()
                base_cell = str(ws.cell_value(r, 4) or '').strip()
                sauce_cell = str(ws.cell_value(r, 5) or '').strip()
            else:
                # v1 格式：序号, 部门, 姓名, 菜品, 酱料
                seq = ws.cell_value(r, 0)
                if not seq:
                    continue
                user = str(ws.cell_value(r, 2) or '').strip()
                dish_cell = str(ws.cell_value(r, 3) or '').strip()
                base_cell = ""
                sauce_cell = str(ws.cell_value(r, 4) or '').strip()
            
            if not user or not dish_cell:
                continue
            
            # 解析菜品
            dish_name, parsed_base, parsed_sauce = _parse_dish_base(dish_cell)
            
            # 检查 base_cell 是否是酱料
            if base_cell and not parsed_sauce:
                sauce_id = _match_sauce(base_cell)
                if sauce_id:
                    parsed_sauce = base_cell
                    base_cell = ""
            
            final_sauce = parsed_sauce or sauce_cell
            final_base = parsed_base or base_cell
            
            # 匹配菜品
            dish = _match_dish(dish_name)
            dish_matched = dish["name"] if dish else None
            
            # 匹配酱料
            sauce_id = _match_sauce(final_sauce) if final_sauce else None
            sauce_matched = next((s["name"] for s in MENU["sauces"] if s["id"] == sauce_id), None) if sauce_id else None
            
            # 检查问题
            has_issue = False
            if not dish:
                issues.append(f"  ✗ Row {int(seq)} {user}: 菜品未匹配 '{dish_name}'")
                has_issue = True
            elif dish_matched != dish_name:
                # 检查是否是合理的匹配
                pass
            
            if final_sauce and not sauce_id:
                issues.append(f"  ✗ Row {int(seq)} {user}: 酱料未匹配 '{final_sauce}'")
                has_issue = True
            
            # 检查三明治是否有 base（不应该有）
            if dish and '三明治' in dish["name"] and final_base:
                issues.append(f"  ✗ Row {int(seq)} {user}: 三明治不应该有 base '{final_base}'")
                has_issue = True
    
    if issues:
        print(f"\n发现 {len(issues)} 个问题:")
        for issue in issues:
            print(issue)
    else:
        print("\n✓ 所有匹配正确")

# 分析所有文件
for filepath in sorted(TESTFILE_DIR.glob("*.xls")):
    analyze_file(filepath)
