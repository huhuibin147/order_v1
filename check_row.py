#!/usr/bin/env python3
"""检查6月23日Row 22的内容"""
import xlrd

FILE = "/Users/huhuibin/code/aiproj/order_v1/testfile/2026年6月23日减脂餐订餐统计表.xls"

wb = xlrd.open_workbook(FILE)
for sheet_name in wb.sheet_names():
    if sheet_name == '菜单':
        continue
    ws = wb.sheet_by_index(wb.sheet_names().index(sheet_name))
    if ws.nrows < 3:
        continue
    
    # 检测格式
    headers = [str(ws.cell_value(1, j) or '').strip() for j in range(ws.ncols)]
    is_v2 = len(headers) >= 7 and '主食' in str(headers[4]) if len(headers) > 4 else False
    
    for r in range(2, ws.nrows):
        if is_v2:
            seq = ws.cell_value(r, 0)
            if not seq:
                continue
            user = str(ws.cell_value(r, 2) or '').strip()
            if user == '刘洋':
                print(f"\nSheet: {sheet_name}, Row {r}")
                print(f"  序号: {seq}")
                print(f"  部门: {ws.cell_value(r, 1)}")
                print(f"  姓名: {user}")
                print(f"  菜品: {ws.cell_value(r, 3)}")
                print(f"  主食: {ws.cell_value(r, 4)}")
                print(f"  酱料: {ws.cell_value(r, 5)}")
                print(f"  园区: {ws.cell_value(r, 6) if ws.ncols > 6 else ''}")
