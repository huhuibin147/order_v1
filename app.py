"""
点单系统 v1 - Flask 单文件后端
对应设计文档：DESIGN.md
"""
import json
import re
import secrets
import string
import uuid
from datetime import datetime
from pathlib import Path

import openpyxl
from flask import Flask, abort, jsonify, render_template, request

BASE_DIR = Path(__file__).parent
MENU_PATH = BASE_DIR / "data" / "menu.json"

app = Flask(__name__)

# ---------- 数据加载 ----------
with MENU_PATH.open("r", encoding="utf-8") as f:
    MENU = json.load(f)

# 进程内存储，重启即清空
SESSIONS: dict[str, dict] = {}
ORDERS: dict[str, dict] = {}  # order_id -> order dict

# 会话码字符表（去掉易混淆的 0/O/1/I/L）
SESSION_CODE_ALPHABET = "".join(c for c in (string.ascii_uppercase + string.digits) if c not in "0O1IL")


# ---------- 工具函数 ----------
def gen_session_code() -> str:
    for _ in range(5):
        code = "".join(secrets.choice(SESSION_CODE_ALPHABET) for _ in range(6))
        if code not in SESSIONS:
            return code
    raise RuntimeError("无法生成唯一会话码")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_session_or_404(session_id: str) -> dict:
    s = SESSIONS.get(session_id)
    if not s:
        abort(404, description="session not found")
    return s


def calc_unit_price(dish: dict, sauce_ids: list[str], addon_ids: list[str]) -> float:
    sauces = {s["id"]: s for s in MENU["sauces"]}
    addons = {a["id"]: a for a in MENU["addons"]}
    total = dish["price"]
    for sid in sauce_ids:
        total += sauces.get(sid, {}).get("price", 0)
    for aid in addon_ids:
        total += addons.get(aid, {}).get("price", 0)
    return round(total, 2)


def get_order_or_404(order_id: str) -> dict:
    o = ORDERS.get(order_id)
    if not o:
        abort(404, description="order not found")
    return o


# ---------- 页面路由 ----------
@app.get("/")
def page_index():
    return render_template("index.html")


@app.get("/menu/<session_id>")
def page_menu(session_id: str):
    get_session_or_404(session_id)
    return render_template("menu.html", session_id=session_id)


@app.get("/summary/<session_id>")
def page_summary(session_id: str):
    get_session_or_404(session_id)
    return render_template("summary.html", session_id=session_id)


@app.get("/admin/<session_id>")
def page_admin(session_id: str):
    get_session_or_404(session_id)
    return render_template("admin.html", session_id=session_id)


@app.get("/admin/sessions")
def page_sessions():
    return render_template("sessions.html")


# ---------- API ----------
@app.get("/api/menu")
def api_menu():
    return jsonify(MENU)


@app.post("/api/session")
def api_create_session():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    sid = gen_session_code()
    SESSIONS[sid] = {
        "id": sid,
        "title": title or f"会话 {sid}",
        "created_at": now_iso(),
        "status": "active",
        "user_names": [],
        "order_ids": [],
    }
    return jsonify(SESSIONS[sid])


@app.get("/api/session/<session_id>")
def api_get_session(session_id: str):
    s = get_session_or_404(session_id)
    orders = [ORDERS[oid] for oid in s["order_ids"]]
    return jsonify({**s, "orders": orders})


@app.post("/api/session/<session_id>/order")
def api_add_order(session_id: str):
    s = get_session_or_404(session_id)
    if s["status"] != "active":
        return jsonify({"error": "session closed"}), 400
    body = request.get_json(silent=True) or {}
    user_name = (body.get("user_name") or "").strip()
    dish_id = body.get("dish_id")
    sauce_ids = body.get("sauce_ids") or []
    addon_ids = body.get("addon_ids") or []
    base = (body.get("base") or "").strip()
    note = (body.get("note") or "").strip()
    if not user_name:
        return jsonify({"error": "user_name required"}), 400
    dish = next((d for d in MENU["dishes"] if d["id"] == dish_id), None)
    if not dish:
        return jsonify({"error": "dish not found"}), 400
    if dish.get("sauce_mode") == "single_required":
        if not isinstance(sauce_ids, list) or len(sauce_ids) != 1:
            return jsonify({"error": "sauce required (pick exactly 1)"}), 400
    base_options = dish.get("base_options")
    if base_options:
        if not base or base not in base_options:
            return jsonify({"error": "base required (pick 1 from base_options)"}), 400
    unit_price = calc_unit_price(dish, sauce_ids, addon_ids)
    # 分配用户序号：按首次出现的昵称顺序
    if user_name not in s["user_names"]:
        s["user_names"].append(user_name)
    user_no = s["user_names"].index(user_name) + 1
    order = {
        "id": uuid.uuid4().hex[:12],
        "session_id": session_id,
        "user_name": user_name,
        "user_no": user_no,
        "dish_id": dish_id,
        "base": base,
        "sauce_ids": sauce_ids,
        "addon_ids": addon_ids,
        "note": note,
        "unit_price": unit_price,
        "created_at": now_iso(),
    }
    ORDERS[order["id"]] = order
    s["order_ids"].append(order["id"])
    return jsonify(order), 201


@app.delete("/api/order/<order_id>")
def api_delete_order(order_id: str):
    order = get_order_or_404(order_id)
    session = SESSIONS.get(order["session_id"])
    if session and order["id"] in session["order_ids"]:
        session["order_ids"].remove(order["id"])
    ORDERS.pop(order_id, None)
    return jsonify({"ok": True})


@app.get("/api/sessions")
def api_list_sessions():
    sessions = sorted(SESSIONS.values(), key=lambda s: s["created_at"], reverse=True)
    result = []
    for s in sessions:
        orders = [ORDERS[oid] for oid in s["order_ids"] if oid in ORDERS]
        result.append({**s, "order_count": len(orders)})
    return jsonify(result)


# ---------- Excel 导入 ----------
def _char_overlap(a: str, b: str) -> float:
    """计算两个字符串的字符重叠率"""
    if not a or not b:
        return 0
    overlap = sum(1 for c in a if c in b)
    return overlap / max(len(a), len(b))


def _match_dish(name: str) -> dict | None:
    """模糊匹配菜品名称，返回 menu 中的 dish dict"""
    # 1. 精确匹配
    for d in MENU["dishes"]:
        if d["name"] == name:
            return d
    # 2. 子串匹配
    for d in MENU["dishes"]:
        if d["name"] in name or name in d["name"]:
            return d
    # 3. 去掉常见品类后缀再匹配
    suffixes = ["碗", "面", "饭", "沙拉", "意面"]
    for d in MENU["dishes"]:
        for suf in suffixes:
            if name.endswith(suf) and d["name"] == name[: -len(suf)]:
                return d
            if d["name"].endswith(suf) and name == d["name"][: -len(suf)]:
                return d
    # 4. 字符重叠兜底
    best, best_score = None, 0
    for d in MENU["dishes"]:
        score = _char_overlap(name, d["name"])
        if score > best_score:
            best_score = score
            best = d
    if best_score >= 0.6:
        return best
    return None


def _match_sauce(name: str) -> str | None:
    """模糊匹配酱汁名称，返回 sauce id"""
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
            core = core[: -len(suf)]
            break
    # 先试 2 字子串
    if len(core) >= 2:
        for i in range(len(core) - 1):
            seg = core[i : i + 2]
            for s in MENU["sauces"]:
                if seg in s["name"]:
                    return s["id"]
    # 再试逐字匹配（core 本身就短或者 2 字子串都没命中时）
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


def _parse_dish_base(cell: str) -> tuple[str, str]:
    """从 '鸡胸肉牛肉双拼碗（荞麦面）' 解析出 (dish_name, base)"""
    m = re.match(r'^(.+?)[\(（](.+?)[\)）]$', cell.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return cell.strip(), ""


@app.post("/api/import")
def api_import_excel():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "请上传 Excel 文件"}), 400

    try:
        wb = openpyxl.load_workbook(file, data_only=True)
    except Exception:
        return jsonify({"error": "无法解析 Excel 文件"}), 400

    created = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(min_row=1, values_only=True))
        if len(rows) < 3:
            continue

        # Row 1: 标题 + sheet名 → 会话名称
        title = str(rows[0][0] or "").strip()
        if not title:
            title = sheet_name
        else:
            title = f"{title} - {sheet_name}"

        # 创建会话
        sid = gen_session_code()
        SESSIONS[sid] = {
            "id": sid,
            "title": title,
            "created_at": now_iso(),
            "status": "active",
            "user_names": [],
            "order_ids": [],
            "import_warnings": [],  # {type, original, matched}
        }
        warnings = SESSIONS[sid]["import_warnings"]

        # Row 3 开始解析数据行（跳过 Row2 表头）
        for row in rows[2:]:
            seq = row[0]  # 序号
            # 遇到非数字序号或空序号则停止（到达底部汇总行）
            if not seq or not str(seq).strip().isdigit():
                break

            user_name = str(row[2] or "").strip()
            dish_cell = str(row[3] or "").strip()
            sauce_cell = str(row[4] or "").strip()

            if not user_name or not dish_cell:
                continue

            dish_name, base = _parse_dish_base(dish_cell)
            dish = _match_dish(dish_name)
            if not dish:
                warnings.append({"type": "dish", "original": dish_cell, "matched": None})
                continue
            elif dish["name"] != dish_name:
                warnings.append({"type": "dish", "original": dish_cell, "matched": dish["name"]})

            sauce_id = _match_sauce(sauce_cell)
            if sauce_cell:
                if sauce_id:
                    sauce_name = next(s["name"] for s in MENU["sauces"] if s["id"] == sauce_id)
                    if sauce_name != sauce_cell:
                        warnings.append({"type": "sauce", "original": sauce_cell, "matched": sauce_name})
                else:
                    warnings.append({"type": "sauce", "original": sauce_cell, "matched": None})
            sauce_ids = [sauce_id] if sauce_id else []

            # 分配用户序号
            if user_name not in SESSIONS[sid]["user_names"]:
                SESSIONS[sid]["user_names"].append(user_name)
            user_no = SESSIONS[sid]["user_names"].index(user_name) + 1

            unit_price = calc_unit_price(dish, sauce_ids, [])
            order = {
                "id": uuid.uuid4().hex[:12],
                "session_id": sid,
                "user_name": user_name,
                "user_no": user_no,
                "dish_id": dish["id"],
                "base": base,
                "sauce_ids": sauce_ids,
                "addon_ids": [],
                "note": "",
                "unit_price": unit_price,
                "created_at": now_iso(),
            }
            ORDERS[order["id"]] = order
            SESSIONS[sid]["order_ids"].append(order["id"])

        created.append({"id": sid, "title": title, "warnings": len(warnings)})

    if not created:
        return jsonify({"error": "未解析到有效数据"}), 400

    return jsonify({"sessions": created}), 201


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e.description)}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=35001, debug=True)
