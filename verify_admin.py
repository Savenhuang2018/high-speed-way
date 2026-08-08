#!/usr/bin/env python3
"""验证运营后台页面与新增端点"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8123"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    ok = 0
    def check(name, cond):
        nonlocal ok
        print(("  ✓ " if cond else "  ✗ ") + name)
        ok += 1 if cond else 0

    # 后台页面可访问
    html = urllib.request.urlopen(BASE + "/admin").read().decode()
    check("运营后台页面加载", "服务区运营后台" in html and "点评审核" in html)

    # 制造一条待审核点评（低分 -> 转人工）
    st, r = req("POST", "/reviews", {"merchant_id": 1, "user_id": 1, "rating": 1, "content": "这次体验很差"})
    check("制造低分待审核点评", st == 201 and r["is_approved"] == 0)
    rid = r["id"]

    # 待审核列表含它
    st, pending = req("GET", "/reviews/pending")
    check("待审核列表含低分点评", st == 200 and any(x["id"] == rid for x in pending))

    # 全部点评列表
    st, allr = req("GET", "/reviews/all")
    check("全部点评列表含待审核", st == 200 and any(x["id"] == rid for x in allr))

    # 驳回
    st, _ = req("POST", f"/reviews/{rid}/reject")
    check("驳回点评成功", st == 200)
    st, allr = req("GET", "/reviews/all")
    check("驳回后从列表移除", st == 200 and not any(x["id"] == rid for x in allr))

    print(f"\n结果: {ok} 通过, {6-ok} 失败")


if __name__ == "__main__":
    main()
