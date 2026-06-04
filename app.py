"""
点单系统 v1 - Flask 单文件后端
对应设计文档：DESIGN.md
"""
import json
import secrets
import string
import uuid
from datetime import datetime
from pathlib import Path

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


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e.description)}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=35001, debug=True)
