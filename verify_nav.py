#!/usr/bin/env python3
"""验证运行中服务：收藏功能 + 底部导航 + 我的页"""
import json
import urllib.error
import urllib.parse
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

# 收藏
st, r = req("POST", "/favorites/toggle", {"user_id":1, "area_id":1})
check("收藏服务区1", st == 200 and r["favorited"] is True)
st, r2 = req("POST", "/favorites/toggle", {"user_id":1, "area_id":2})
check("收藏服务区2", st == 200 and r2["favorited"] is True)
st, mine = req("GET", "/favorites?user_id=1")
check("我的收藏2个", st == 200 and len(mine) == 2)

# 前端结构
html = urllib.request.urlopen(BASE + "/index.html").read().decode()
check("底部导航栏", 'class="bottom-nav"' in html and "data-nav=" in html)
check("收藏页视图", 'id="view-favorites"' in html and 'id="fav-list"' in html)
check("我的页视图", 'id="view-mine"' in html and 'id="profile-name"' in html)
check("收藏JS", "function toggleFavorite" in html and "function loadFavorites" in html and "function switchNav" in html)
check("详情页收藏按钮", "detail-fav-btn" in html)

print(f"\n结果: {ok} 通过, {9-ok} 失败")
