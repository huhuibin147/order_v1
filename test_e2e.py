"""端到端 smoke test：起本地服务，跑全流程。"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:35001"


def http(method, path, body=None, expect=200):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def assert_eq(a, b, msg):
    if a != b:
        print(f"FAIL {msg}: expected {b!r}, got {a!r}")
        sys.exit(1)
    print(f"  ok  {msg}: {a}")


# 1. menu
code, menu = http("GET", "/api/menu")
assert_eq(code, 200, "GET /api/menu")
assert_eq(len(menu["dishes"]), 10, "menu dishes count")

# 2. create session
code, sess = http("POST", "/api/session", {"title": "E2E 测试"})
assert_eq(code, 200, "create session")
sid = sess["id"]
assert_eq(len(sid), 6, "session id length")

# 3. add orders
code, o1 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小王", "dish_id": "d_noodle_beef",
    "sauce_ids": ["s_garlic", "s_chili"], "addon_ids": ["a_egg"], "note": "少辣",
})
assert_eq(code, 201, "add order1")
# 价格：28 + 0 + 0 + 2 = 30
assert_eq(o1["unit_price"], 30, "order1 unit price (28+0+0+2)")
assert_eq(o1["user_no"], 1, "order1 user_no (first user)")

code, o2 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小李", "dish_id": "d_fried_chicken",
    "sauce_ids": ["s_curry"], "addon_ids": [],
})
assert_eq(code, 201, "add order2")
# 25 + 2 = 27
assert_eq(o2["unit_price"], 27, "order2 unit price (25+2)")
assert_eq(o2["user_no"], 2, "order2 user_no (second user)")

code, o3 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小王", "dish_id": "d_cola",
    "sauce_ids": [], "addon_ids": [],
})
assert_eq(code, 201, "add order3")
assert_eq(o3["user_no"], 1, "order3 user_no (same user, should keep 1)")

# 新用户进来应该分到 3 号
code, o4 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小张", "dish_id": "d_noodle_pork",
    "sauce_ids": ["s_garlic"], "addon_ids": ["a_vege"],
})
assert_eq(code, 201, "add order4")
assert_eq(o4["user_no"], 3, "order4 user_no (third new user)")

# 同样的菜再来一份（测试同类汇总）
code, o5 = http("POST", f"/api/session/{sid}/order", {
    "user_name": "小李", "dish_id": "d_fried_chicken",
    "sauce_ids": ["s_curry"], "addon_ids": [],
})
assert_eq(code, 201, "add order5 (duplicate spec)")
assert_eq(o5["user_no"], 2, "order5 user_no (小李, still 2)")

# 验证 session 里的 user_names 顺序
code, view = http("GET", f"/api/session/{sid}")
assert_eq(view["user_names"], ["小王", "小李", "小张"], "user_names order")

# 4. missing user_name
code, err = http("POST", f"/api/session/{sid}/order", {
    "user_name": "", "dish_id": "d_cola", "sauce_ids": [], "addon_ids": [],
}, expect=400)
assert_eq(code, 400, "reject empty user_name")

# 5. unknown dish
code, err = http("POST", f"/api/session/{sid}/order", {
    "user_name": "x", "dish_id": "nope", "sauce_ids": [], "addon_ids": [],
}, expect=400)
assert_eq(code, 400, "reject unknown dish")

# 6. get session
code, view = http("GET", f"/api/session/{sid}")
assert_eq(code, 200, "get session")
assert_eq(len(view["orders"]), 5, "session order count")

# 7. delete order
code, _ = http("DELETE", f"/api/order/{o3['id']}")
assert_eq(code, 200, "delete order")

code, view = http("GET", f"/api/session/{sid}")
assert_eq(len(view["orders"]), 4, "session order count after delete")

# 8. page routes
for path in ["/", f"/menu/{sid}", f"/summary/{sid}", f"/admin/{sid}"]:
    req = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(req) as r:
        assert_eq(r.status, 200, f"page {path}")

print("\nALL PASS")
