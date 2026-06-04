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
assert_eq(len(menu["dishes"]), 16, "menu dishes count (16)")
# 3 个双拼碗有 base_options
base_dishes = [d for d in menu["dishes"] if d.get("base_options")]
assert_eq(len(base_dishes), 3, "dishes with base_options (3)")
# 其余 13 个菜没有 base_options
non_base = [d for d in menu["dishes"] if not d.get("base_options")]
assert_eq(len(non_base), 13, "dishes without base_options (13)")
# 全部菜品都该是 single_required
all_single = all(d.get("sauce_mode") == "single_required" for d in menu["dishes"])
assert_eq(all_single, True, "all dishes are sauce_mode=single_required")

# ---- 2. create session ----
code, sess = http("POST", "/api/session", {"title": "E2E 测试"})
assert_eq(code, 200, "create session")
sid = sess["id"]
assert_eq(len(sid), 6, "session id length")

# ---- 3. 下单 ----
# 3.1 小王 鸡胸肉牛肉双拼碗（杂粮饭） + 黑胡椒汁 = 19
code, o1 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小王", "dish_id": "d_chicken_beef",
    "base": "杂粮饭",
    "sauce_ids": ["s_black_pepper"], "addon_ids": [], "note": "少辣",
}, expect=201)
assert_eq(o1["unit_price"], 19, "order1 unit price (19, sauce free)")
assert_eq(o1["user_no"], 1, "order1 user_no (first user)")
assert_eq(o1["base"], "杂粮饭", "order1 base saved")

# 3.2 小李 炙烤原切牛排意面 + 牛肉辣酱 = 18（无 base 字段）
code, o2 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小李", "dish_id": "d_steak_pasta",
    "sauce_ids": ["s_beef_chili"], "addon_ids": [],
}, expect=201)
assert_eq(o2["unit_price"], 18, "order2 unit price (18)")
assert_eq(o2["user_no"], 2, "order2 user_no (second user)")
assert_eq(o2["base"], "", "order2 base empty (no base_options)")

# 3.3 小王 再点 鸡胸肉牛肉双拼碗（意面） + 油醋汁 = 19（user_no 应保持 1）
code, o3 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小王", "dish_id": "d_chicken_beef",
    "base": "意面",
    "sauce_ids": ["s_vinaigrette"], "addon_ids": [],
}, expect=201)
assert_eq(o3["user_no"], 1, "order3 user_no (same user, keeps 1)")
assert_eq(o3["base"], "意面", "order3 base is 意面")

# 3.4 小张 黑椒牛肉杂粮拌饭 + 黑胡椒汁 = 18（无 base）
code, o4 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小张", "dish_id": "d_pepper_beef_grain",
    "sauce_ids": ["s_black_pepper"], "addon_ids": [],
}, expect=201)
assert_eq(o4["user_no"], 3, "order4 user_no (third new user)")

# 3.5 同菜同底再来一份（测试汇总合并）
code, o5 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小李", "dish_id": "d_chicken_beef",
    "base": "杂粮饭",
    "sauce_ids": ["s_black_pepper"], "addon_ids": [],
}, expect=201)
assert_eq(o5["user_no"], 2, "order5 user_no (小李, still 2)")

# user_names 顺序
code, view = http("GET", f"/api/session/{sid}")
assert_eq(view["user_names"], ["小王", "小李", "小张"], "user_names order")

# ---- 4. 校验 ----
# 4.1 双拼碗不传 base → 400
code, err = http("POST", f"/api/session/{sid}/order", {
    "user_name": "test", "dish_id": "d_chicken_beef",
    "sauce_ids": ["s_beef_chili"], "addon_ids": []
}, expect=400)
assert_eq(err["error"], "base required (pick 1 from base_options)", "reject missing base for 双拼碗")

# 4.2 双拼碗 base 不在 options 中 → 400
code, err = http("POST", f"/api/session/{sid}/order", {
    "user_name": "test", "dish_id": "d_chicken_beef", "base": "米饭",
    "sauce_ids": ["s_beef_chili"], "addon_ids": []
}, expect=400)
assert_eq(err["error"], "base required (pick 1 from base_options)", "reject invalid base")

# 4.3 双拼碗缺 sauce → 400
code, err = http("POST", f"/api/session/{sid}/order", {
    "user_name": "test", "dish_id": "d_chicken_beef", "base": "杂粮饭",
    "sauce_ids": [], "addon_ids": []
}, expect=400)
assert_eq(err["error"], "sauce required (pick exactly 1)", "reject missing sauce")

# 4.4 沙拉带 base → 应忽略（沙拉没 base_options），但我们的校验只在 base_options 存在时检查
# 所以下面这条应该 OK（服务端不要求 base）
code, _ = http("POST", f"/api/session/{sid}/order", {
    "user_name": "test", "dish_id": "d_tuna_salad", "base": "",
    "sauce_ids": ["s_caesar"], "addon_ids": []
}, expect=201)
print("  ok  salad without base_options accepts empty base: 201")

# 4.5 未知 dish
code, _ = http("POST", f"/api/session/{sid}/order", {
    "user_name": "x", "dish_id": "nope", "base": "杂粮饭",
    "sauce_ids": ["s_beef_chili"], "addon_ids": []
}, expect=400)
print("  ok  reject unknown dish: 400")

# 4.6 空 user_name
code, _ = http("POST", f"/api/session/{sid}/order", {
    "user_name": "", "dish_id": "d_steak_pasta",
    "sauce_ids": ["s_beef_chili"], "addon_ids": []
}, expect=400)
print("  ok  reject empty user_name: 400")

# ---- 5. session 状态 ----
code, view = http("GET", f"/api/session/{sid}")
assert_eq(code, 200, "get session")
# 之前是 5 个 + 后补 1 个沙拉 = 6 个
assert_eq(len(view["orders"]), 6, "session order count")

# ---- 6. 删除订单 ----
code, _ = http("DELETE", f"/api/order/{o3['id']}")
assert_eq(code, 200, "delete order")
code, view = http("GET", f"/api/session/{sid}")
assert_eq(len(view["orders"]), 5, "session order count after delete")

# ---- 7. 页面路由 ----
for path in ["/", f"/menu/{sid}", f"/summary/{sid}", f"/admin/{sid}"]:
    req = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(req) as r:
        assert_eq(r.status, 200, f"page {path}")

print("\nALL PASS")
