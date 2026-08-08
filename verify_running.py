#!/usr/bin/env python3
"""运行中服务的可视化验证脚本"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8123"


def get(path):
    if "?" in path:
        b, q = path.split("?", 1)
        q = urllib.parse.quote(q, safe="=&")
        path = b + "?" + q
    return json.loads(urllib.request.urlopen(BASE + path).read())


def main():
    print("health:", get("/health"))
    areas = get("/service-areas")
    print("服务区:", [a["name"] for a in areas])
    ms = get("/merchants?service_area_id=1&category=餐饮")
    print("阳澄湖全部商户:", [(m["name"], m["category"], m["rating"]) for m in get("/merchants?service_area_id=1")])
    print("阳澄湖餐饮商户:", [(m["name"], m["rating"], m["review_count"]) for m in ms])
    rev = get("/reviews?merchant_id=1")
    print(f"商户1已审核点评: {len(rev)} 条")
    html = urllib.request.urlopen(BASE + "/").read().decode()
    print("首页加载成功:", "车主服务与点评" in html)


if __name__ == "__main__":
    main()
