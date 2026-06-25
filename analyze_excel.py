#!/usr/bin/env python3
"""分析 Excel 文件内容，查找三明治和酸奶杯"""
import xlrd

FILE = "/Users/huhuibin/code/aiproj/order_v1/testfile/2026年6月22日减脂餐订餐统计表.xls"

wb = xlrd.open_workbook(FILE)
for i, name in enumerate(wb.sheet_names()):
    if name == '菜单':
        continue
    ws = wb.sheet_by_index(i)
    print(f"\n=== Sheet: {name} ===")
    for r in range(2, ws.nrows):
        row = [str(ws.cell_value(r, j) or '').strip() for j in range(ws.ncols)]
        # 查找三明治或酸奶杯
        row_str = ' '.join(row)
        if '三明治' in row_str or '酸奶' in row_str:
            print(f"  Row {r}: {row}")
