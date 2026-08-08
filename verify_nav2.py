#!/usr/bin/env python3
"""验证收藏接口（用全新用户，避免幂等切换干扰）"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8123"

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

ok = 0
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok += 1 if cond else 0

# 用新用户避免残留
uid = req("POST", "/users", {"nickname":"测试收藏用户"})[1]["id"]

st, r = req("POST", "/favorites/toggle", {"user_id":uid, "area_id":1})
check("新用户收藏服务区1", st == 200 and r["favorited"] is True)
st, r2 = req("POST", "/favorites/toggle", {"user_id":uid, "area_id":2})
check("新用户收藏服务区2", st == 200 and r2["favorited"] is True)
st, mine = req("GET", f"/favorites?user_id={uid}")
check(f"我的收藏2个(uid={uid})", st == 200 and len(mine) == 2)
st, r3 = req("POST", "/favorites/toggle", {"user_id":uid, "area_id":1})
check("再toggle取消", st == 200 and r3["favorited"] is False)
st, mine2 = req("GET", f"/favorites?user_id={uid}")
check("取消后剩1个", st == 200 and len(mine2) == 1)

print(f"\n结果: {ok} 通过, {5-ok} 失败")
