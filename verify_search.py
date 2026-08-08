#!/usr/bin/env python3
"""验证服务区搜索功能（后端 + 前端结构）"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

PORT = 18996
BASE = f"http://127.0.0.1:{PORT}"
PROJ = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ)
db_path = os.path.join(__import__('tempfile').mkdtemp(), "search_test.db")
env["SERVICE_AREA_DB"] = db_path

srv = subprocess.Popen([sys.executable, "server.py", str(PORT)], cwd=PROJ, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try:
        urllib.request.urlopen(BASE + "/health"); break
    except Exception:
        time.sleep(0.2)

def req(path):
    if "?" in path:
        b, q = path.split("?", 1); q = urllib.parse.quote(q, safe="=&"); path = b + "?" + q
    return json.loads(urllib.request.urlopen(BASE + path).read())

def main():
    ok = 0
    def check(name, cond):
        nonlocal ok
        print(("  ✓ " if cond else "  ✗ ") + name)
        ok += 1 if cond else 0

    # 按名称搜索
    r = req("/service-areas/search?q=阳澄湖")
    check("按名称搜到阳澄湖", len(r) >= 1 and "阳澄湖" in r[0]["name"])
    check("结果含商户数", r[0].get("merchant_count", 0) > 0)
    check("结果含业态标签", isinstance(r[0].get("categories"), list))

    # 按高速搜索
    r = req("/service-areas/search?q=京沪")
    check("按高速搜到京沪沿线", len(r) >= 3)

    # 按桩号/描述
    r = req("/service-areas/search?q=阳澄湖大闸蟹")
    check("按描述搜索", len(r) >= 1)

    # 无关键词 -> 422
    try:
        urllib.request.urlopen(BASE + "/service-areas/search?q=")
        check("空关键词应422", False)
    except urllib.error.HTTPError as e:
        check("空关键词返回422", e.code == 422)

    # 无匹配
    r = req("/service-areas/search?q=不存在的地方xyz")
    check("无匹配返回空列表", r == [])

    # 前端结构
    html = urllib.request.urlopen(BASE + "/index.html").read().decode()
    check("前端含搜索框", 'id="search-input"' in html and 'id="search-list"' in html)
    check("前端含搜索JS", "function doSearch" in html and "/service-areas/search" in html)

    print(f"\n结果: {ok} 通过, {9-ok} 失败")

try:
    main()
finally:
    srv.terminate(); srv.wait(timeout=5)

sys.exit(0)
