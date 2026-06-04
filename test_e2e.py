"""端到端 smoke test：起本地服务，跑全流程。"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:35001"


def http(method, path, body=None, expect=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req) as r:
            status, body = r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        status, body = e.code, json.loads(e.read().decode())
    if expect is not None and status != expect:
        print(f"FAIL {method} {path}: expected {expect}, got {status} {body}")
        sys.exit(1)
    return status, body


def assert_eq(a, b, msg):
    if a != b:
        print(f"FAIL {msg}: expected {b!r}, got {a!r}")
        sys.exit(1)
    print(f"  ok  {msg}: {a}")


# ---- 1. menu ----
code, menu = http("GET", "/api/menu")
assert_eq(code, 200, "GET /api/menu")
assert_eq(len(menu["sauces"]), 8, "menu sauces count (8)")
assert_eq(len(menu["addons"]), 0, "menu addons count (0)")
assert_eq(len(menu["dishes"]), 22, "menu dishes count (22)")
# 全部菜品都该是 single_required
all_single = all(d.get("sauce_mode") == "single_required" for d in menu["dishes"])
assert_eq(all_single, True, "all dishes are sauce_mode=single_required")

# ---- 2. create session ----
code, sess = http("POST", "/api/session", {"title": "E2E 测试"})
assert_eq(code, 200, "create session")
sid = sess["id"]
assert_eq(len(sid), 6, "session id length")

# ---- 3. 下单 ----
# 3.1 小王 牛排大虾双拼碗（杂粮饭） + 黑胡椒汁 = 21
code, o1 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小王", "dish_id": "d_steak_shrimp_grain",
    "sauce_ids": ["s_black_pepper"], "addon_ids": [], "note": "少辣",
}, expect=201)
assert_eq(o1["unit_price"], 21, "order1 unit price (21, sauce free)")
assert_eq(o1["user_no"], 1, "order1 user_no (first user)")

# 3.2 小李 炙烤原切牛排意面 + 牛肉辣酱 = 18
code, o2 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小李", "dish_id": "d_steak_pasta",
    "sauce_ids": ["s_beef_chili"], "addon_ids": [],
}, expect=201)
assert_eq(o2["unit_price"], 18, "order2 unit price (18)")
assert_eq(o2["user_no"], 2, "order2 user_no (second user)")

# 3.3 小王 再点 香薰鸡肉荞麦面 + 油醋汁 = 16（user_no 应保持 1）
code, o3 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小王", "dish_id": "d_chicken_buck",
    "sauce_ids": ["s_vinaigrette"], "addon_ids": [],
}, expect=201)
assert_eq(o3["user_no"], 1, "order3 user_no (same user, keeps 1)")

# 3.4 小张 黑椒牛肉杂粮拌饭 + 黑椒牛肉虾滑双拼碗 × 黑胡椒汁 = 18
code, o4 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小张", "dish_id": "d_pepper_beef_grain",
    "sauce_ids": ["s_black_pepper"], "addon_ids": [],
}, expect=201)
assert_eq(o4["user_no"], 3, "order4 user_no (third new user)")

# 3.5 同样的菜再来一份（测试汇总合并）
code, o5 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小李", "dish_id": "d_steak_pasta",
    "sauce_ids": ["s_beef_chili"], "addon_ids": [],
}, expect=201)
assert_eq(o5["user_no"], 2, "order5 user_no (小李, still 2)")

# user_names 顺序
code, view = http("GET", f"/api/session/{sid}")
assert_eq(view["user_names"], ["小王", "小李", "小张"], "user_names order")

# ---- 4. 必选酱料校验 ----
# 4.1 不传 sauce_ids
code, err = http("POST", f"/api/session/{sid}/order", {
    "user_name": "test", "dish_id": "d_steak_pasta", "sauce_ids": [], "addon_ids": []
}, expect=400)
assert_eq(err["error"], "sauce required (pick exactly 1)", "reject empty sauce_ids (single_required)")

# 4.2 传 2 个 sauce_ids
code, err = http("POST", f"/api/session/{sid}/order", {
    "user_name": "test", "dish_id": "d_steak_pasta",
    "sauce_ids": ["s_beef_chili", "s_garlic_chili"], "addon_ids": []
}, expect=400)
assert_eq(err["error"], "sauce required (pick exactly 1)", "reject multi sauce_ids (single_required)")

# 4.3 未知 dish
code, _ = http("POST", f"/api/session/{sid}/order", {
    "user_name": "x", "dish_id": "nope", "sauce_ids": ["s_beef_chili"], "addon_ids": []
}, expect=400)
print("  ok  reject unknown dish: 400")

# 4.4 空 user_name
code, _ = http("POST", f"/api/session/{sid}/order", {
    "user_name": "", "dish_id": "d_steak_pasta", "sauce_ids": ["s_beef_chili"], "addon_ids": []
}, expect=400)
print("  ok  reject empty user_name: 400")

# ---- 5. session 状态 ----
code, view = http("GET", f"/api/session/{sid}")
assert_eq(code, 200, "get session")
assert_eq(len(view["orders"]), 5, "session order count")

# ---- 6. 删除订单 ----
code, _ = http("DELETE", f"/api/order/{o3['id']}")
assert_eq(code, 200, "delete order")
code, view = http("GET", f"/api/session/{sid}")
assert_eq(len(view["orders"]), 4, "session order count after delete")

# ---- 7. 页面路由 ----
for path in ["/", f"/menu/{sid}", f"/summary/{sid}", f"/admin/{sid}"]:
    req = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(req) as r:
        assert_eq(r.status, 200, f"page {path}")

print("\nALL PASS")
