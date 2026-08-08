#!/usr/bin/env python3
"""验证运行中服务的新功能：智能审核 + 商户回复"""
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

    # 高分无敏感词 -> 自动通过
    st, r = req("POST", "/reviews", {"merchant_id": 1, "user_id": 1, "rating": 4, "content": "蟹黄豆腐很好吃"})
    check("高分点评自动通过", st == 201 and r["is_approved"] == 1)
    rid = r["id"]

    # 敏感词 -> 转人工
    st, r2 = req("POST", "/reviews", {"merchant_id": 1, "user_id": 1, "rating": 1, "content": "这家店太坑人了"})
    check("敏感词点评转人工", st == 201 and r2["is_approved"] == 0)

    # 低分差评 -> 转人工
    st, r3 = req("POST", "/reviews", {"merchant_id": 1, "user_id": 1, "rating": 2, "content": "不太行"})
    check("低分差评转人工", st == 201 and r3["is_approved"] == 0)

    # 商户回复自动通过的点评
    st, rep = req("POST", f"/reviews/{rid}/reply", {"reply": "感谢支持，欢迎再来！"})
    check("商户回复成功", st == 200 and rep["merchant_reply"] == "感谢支持，欢迎再来！")

    # 查看点评列表应包含商户回复
    st, reviews = req("GET", "/reviews?merchant_id=1")
    check("点评列表含商户回复", st == 200 and any(x.get("merchant_reply") for x in reviews))

    print(f"\n结果: {ok} 通过, {5-ok} 失败")


if __name__ == "__main__":
    main()
