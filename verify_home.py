#!/usr/bin/env python3
"""验证美团风格新首页 + 沿途服务区端点"""
import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8123"


def req(path):
    if "?" in path:
        b, q = path.split("?", 1)
        q = urllib.parse.quote(q, safe="=&")
        path = b + "?" + q
    return json.loads(urllib.request.urlopen(BASE + path).read())


def main():
    ok = 0
    def check(name, cond):
        nonlocal ok
        print(("  ✓ " if cond else "  ✗ ") + name)
        ok += 1 if cond else 0

    # 首页
    html = urllib.request.urlopen(BASE + "/index.html").read().decode()
    check("新首页可访问", "高速服务区" in html)
    check("美团橙配色", "#ff6b35" in html)
    check("分类宫格", 'id="cats"' in html and "餐饮" in html and "充电" in html)
    check("位置/行程输入", 'id="cur"' in html and 'id="origin"' in html and 'id="dest"' in html)
    check("沿途端点调用", "/route/areas" in html)

    # 沿途服务区（上海->北京）
    route = req("/route/areas?cur_lat=31.23&cur_lng=121.47&dest_lat=39.90&dest_lng=116.40")
    check("沿途返回服务区", len(route) >= 5)
    check("按距离升序", all(route[i]["distance_km"] <= route[i+1]["distance_km"]
                           for i in range(len(route)-1)))
    print("  沿途序列:", [f"{a['name']}({a['distance_km']}km)" for a in route[:5]])

    # 服务区总数
    areas = req("/service-areas")
    check("服务区共9个", len(areas) == 9)

    print(f"\n结果: {ok} 通过, {8-ok} 失败")


if __name__ == "__main__":
    main()
