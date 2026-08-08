#!/usr/bin/env python3
"""
零依赖集成测试：启动临时服务实例，用 urllib 验证核心 API 闭环。
用法： python3 test_stdlib.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PORT = 18734
BASE = f"http://127.0.0.1:{PORT}"


def request(method, path, body=None):
    # 对查询串做百分号编码，支持中文参数
    if "?" in path:
        base, query = path.split("?", 1)
        query = urllib.parse.quote(query, safe="=&")
        path = base + "?" + query
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def main():
    # 使用隔离的临时数据库目录，避免污染 / 与运行中服务共库
    workdir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(workdir, "test_runtime.db")
    env = dict(os.environ)
    env["SERVICE_AREA_DB"] = db_path
    if os.path.exists(db_path):
        os.remove(db_path)

    proc = subprocess.Popen(
        [sys.executable, "server.py", str(PORT)],
        cwd=workdir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    # 等待服务就绪
    for _ in range(50):
        try:
            code, _ = request("GET", "/health")
            if code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        print("FAIL: 服务未能启动")
        return 1

    passed = 0
    failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}")

    try:
        # 1. 健康检查
        code, body = request("GET", "/health")
        check("健康检查", code == 200 and body["status"] == "ok")

        # 2. 服务区列表（种子数据 2 个）
        code, areas = request("GET", "/service-areas")
        check("服务区列表返回2个", code == 200 and len(areas) == 2)

        # 3. 按服务区筛选商户（阳澄湖 id=1，餐饮）
        code, merchants = request("GET", "/merchants?service_area_id=1")
        check("按服务区筛商户", code == 200 and len(merchants) == 4)

        code, cats = request("GET", "/merchants?service_area_id=1&category=餐饮")
        check("按业态筛餐饮", code == 200 and len(cats) == 2)

        # 4. 商户详情含评分和点评数
        code, m = request("GET", "/merchants/1")
        check("商户详情评分>0", code == 200 and m["rating"] > 0)
        check("商户点评数=2", code == 200 and m["review_count"] == 2)

        # 5. 智能审核：高分无敏感词点评自动通过并立即可见
        code, rev = request("POST", "/reviews",
                            {"merchant_id": 1, "user_id": 1, "rating": 4, "content": "测试点评"})
        check("发表点评201", code == 201)
        check("高分点评自动通过", rev["is_approved"] == 1)
        rid = rev["id"]
        code, reviews = request("GET", "/reviews?merchant_id=1")
        check("自动通过后立即可见(3条)", code == 200 and len(reviews) == 3)
        code, m = request("GET", "/merchants/1")
        check("评分已重算(点评数3)", code == 200 and m["review_count"] == 3)

        # 5b. 敏感词点评转人工审核（不自动通过）
        code, rev2 = request("POST", "/reviews",
                             {"merchant_id": 1, "user_id": 1, "rating": 1, "content": "这家店太坑人了"})
        check("敏感词点评转人工", code == 201 and rev2["is_approved"] == 0)
        code, reviews = request("GET", "/reviews?merchant_id=1")
        check("敏感词点评不可见(仍3条)", code == 200 and len(reviews) == 3)
        # 人工审核通过后可见
        code, rev3 = request("POST", f"/reviews/{rev2['id']}/approve")
        check("人工审核通过", code == 200 and rev3["is_approved"] == 1)
        code, reviews = request("GET", "/reviews?merchant_id=1")
        check("人工通过后可见(4条)", code == 200 and len(reviews) == 4)

        # 5c. 低分差评(<=2)即使无敏感词也转人工
        code, rev4 = request("POST", "/reviews",
                             {"merchant_id": 1, "user_id": 1, "rating": 2, "content": "一般般"})
        check("低分差评转人工", code == 201 and rev4["is_approved"] == 0)

        # 5d. 商户回复点评
        code, rep = request("POST", f"/reviews/{rid}/reply", {"reply": "感谢支持，欢迎再来！"})
        check("商户回复成功", code == 200 and rep["merchant_reply"] == "感谢支持，欢迎再来！")
        code, _ = request("POST", f"/reviews/{rid}/reply", {"reply": ""})
        check("空回复被拒(422)", code == 422)

        # 6. 校验：评分为6应被拒
        code, _ = request("POST", "/reviews", {"merchant_id": 1, "user_id": 1, "rating": 6})
        check("非法评分被拒(422)", code == 422)

        # 7. 新建服务区 & 用户
        code, _ = request("POST", "/service-areas", {"name": "新服务区", "highway": "G42"})
        check("新建服务区201", code == 201)
        code, u = request("POST", "/users", {"nickname": "新用户", "phone": "13900000000"})
        check("新建用户201", code == 201 and u["nickname"] == "新用户")
        new_uid = u["id"]

        # 8. 优惠券
        code, coupons = request("GET", "/coupons")
        check("优惠券列表含种子2张", code == 200 and len(coupons) == 2)
        cid = coupons[0]["id"]
        code, claimed = request("POST", f"/coupons/{cid}/claim", {"user_id": 1})
        check("领取优惠券201", code == 201 and claimed["used"] == 0)
        code, dup = request("POST", f"/coupons/{cid}/claim", {"user_id": 1})
        check("重复领取被拒(409)", code == 409)
        code, mine = request("GET", f"/users/me/coupons?user_id=1")
        check("我的优惠券含1张", code == 200 and len(mine) == 1 and mine[0]["coupon_id"] == cid)

        # 9. 运营数据看板
        code, dash = request("GET", "/stats/dashboard")
        check("看板返回200", code == 200)
        check("看板点评总数统计", code == 200 and dash["reviews"]["total"] >= 3)
        check("看板业态分布", code == 200 and isinstance(dash["category_distribution"], list))
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        if os.path.exists(db_path):
            os.remove(db_path)

    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
