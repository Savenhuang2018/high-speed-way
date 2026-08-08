#!/usr/bin/env python3
"""验证运行中服务的搜索功能"""
import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8123"

def req(path):
    b, q = path.split("?", 1)
    q = urllib.parse.quote(q, safe="=&")
    return json.loads(urllib.request.urlopen(BASE + b + "?" + q).read())

ok = 0
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok += 1 if cond else 0

r = req("/service-areas/search?q=阳澄湖")
check("搜索阳澄湖", len(r) >= 1 and "阳澄湖" in r[0]["name"])
if r:
    check("含商户数/评分/业态", "merchant_count" in r[0] and "avg_rating" in r[0] and "categories" in r[0])
    print("  结果:", [(a["name"], a["merchant_count"], a["avg_rating"], a["categories"]) for a in r])

r2 = req("/service-areas/search?q=京沪")
check("搜索京沪多结果", len(r2) >= 3)

html = urllib.request.urlopen(BASE + "/index.html").read().decode()
check("前端搜索框已加载", 'id="search-input"' in html)

print(f"\n结果: {ok} 通过, {4-ok} 失败")
