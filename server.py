#!/usr/bin/env python3
"""
高速公路服务区「车主服务 + 点评」MVP —— 零依赖实现
==================================================
纯 Python 标准库：sqlite3 + http.server，无需 pip 安装任何第三方包。

功能：
  GET  /health                      健康检查
  GET  /service-areas               服务区列表
  POST /service-areas               新建服务区 {name, highway, ...}
  GET  /merchants?service_area_id=&category=&min_rating=  商户列表
  GET  /merchants/{id}              商户详情（含评分、点评数）
  POST /merchants                   新建商户
  GET  /reviews?merchant_id={id}    查看某商户已审核点评
  POST /reviews                     发表点评 {merchant_id,user_id,rating,content,tags}
  POST /reviews/{id}/approve        审核通过点评
  GET  /users/{id}                  用户详情
  POST /users                       创建用户

运行：  python3 server.py [port]   （默认 8000）
测试：  python3 test_stdlib.py
"""
import json
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get("SERVICE_AREA_DB", "service_area.db")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


# ---------------------------------------------------------------------------
# 数据库层
# ---------------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT NOT NULL,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS service_areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            highway TEXT NOT NULL,
            mile_marker TEXT,
            latitude REAL,
            longitude REAL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS merchants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_area_id INTEGER NOT NULL REFERENCES service_areas(id),
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            avg_price REAL,
            open_hours TEXT,
            description TEXT,
            rating REAL DEFAULT 0.0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL REFERENCES merchants(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            rating INTEGER NOT NULL,
            content TEXT,
            tags TEXT,
            is_approved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL REFERENCES merchants(id),
            title TEXT NOT NULL,
            discount REAL,
            amount REAL,
            quota INTEGER DEFAULT 0,
            claimed INTEGER DEFAULT 0,
            start_at TEXT,
            end_at TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS user_coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            coupon_id INTEGER NOT NULL REFERENCES coupons(id),
            used INTEGER DEFAULT 0,
            claimed_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()


def seed_data():
    """写入演示数据"""
    conn = get_conn()
    c = conn.cursor()
    # 已存在数据则不重复写入
    if c.execute("SELECT COUNT(*) FROM service_areas").fetchone()[0] > 0:
        conn.close()
        return

    c.execute("INSERT INTO users (nickname, phone) VALUES (?,?)", ("自驾老王", "13800000001"))
    c.execute("INSERT INTO users (nickname, phone) VALUES (?,?)", ("电车小妹", "13800000002"))
    c.execute("INSERT INTO users (nickname, phone) VALUES (?,?)", ("卡车司机", "13800000003"))

    c.execute(
        "INSERT INTO service_areas (name, highway, mile_marker, latitude, longitude, description) "
        "VALUES (?,?,?,?,?,?)",
        ("沪宁高速阳澄湖服务区", "G2京沪高速", "K1180", 31.42, 120.72,
         "以阳澄湖大闸蟹闻名的网红服务区，业态丰富。"),
    )
    c.execute(
        "INSERT INTO service_areas (name, highway, mile_marker, latitude, longitude, description) "
        "VALUES (?,?,?,?,?,?)",
        ("京港澳高速窦店服务区", "G4京港澳高速", "K37", 39.67, 116.08,
         "华北地区大型综合服务区，加油充电便利。"),
    )

    c.execute("INSERT INTO merchants (service_area_id, name, category, avg_price, open_hours, description) "
              "VALUES (1,?,?,?,?,?)", ("阳澄湖蟹味馆", "餐饮", 88, "06:00-22:00", "正宗阳澄湖大闸蟹，招牌蟹黄豆腐。"))
    c.execute("INSERT INTO merchants (service_area_id, name, category, avg_price, open_hours, description) "
              "VALUES (1,?,?,?,?,?)", ("老字号面馆", "餐饮", 32, "24小时", "苏州特色奥灶面，快速出餐。"))
    c.execute("INSERT INTO merchants (service_area_id, name, category, avg_price, open_hours, description) "
              "VALUES (1,?,?,?,?,?)", ("中石化加油站", "加油", None, "24小时", "92/95/98号汽油及柴油。"))
    c.execute("INSERT INTO merchants (service_area_id, name, category, avg_price, open_hours, description) "
              "VALUES (1,?,?,?,?,?)", ("特来电快充站", "充电", None, "24小时", "8 个 120kW 快充桩。"))
    c.execute("INSERT INTO merchants (service_area_id, name, category, avg_price, open_hours, description) "
              "VALUES (2,?,?,?,?,?)", ("庆丰包子铺", "餐饮", 25, "06:00-21:00", "经典北京小吃，猪肉大葱包子。"))
    c.execute("INSERT INTO merchants (service_area_id, name, category, avg_price, open_hours, description) "
              "VALUES (2,?,?,?,?,?)", ("国网充电站", "充电", None, "24小时", "16 个 60kW 直流快充桩。"))

    # 点评（含已审核与待审核）
    c.execute("INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
              "VALUES (1,1,5,?,?,1)", ("大闸蟹新鲜，环境干净，就是节假日人有点多。", "干净,味道好"))
    c.execute("INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
              "VALUES (1,2,4,?,?,1)", ("价格偏贵但值得一尝，蟹黄很足。", "价格偏贵"))
    c.execute("INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
              "VALUES (2,1,5,?,?,1)", ("奥灶面汤头一绝，24小时营业太贴心了。", "味道好,24小时"))
    c.execute("INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
              "VALUES (4,2,4,?,?,1)", ("充电速度快，但高峰期要排队。", "速度快,排队久"))
    c.execute("INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
              "VALUES (5,3,5,?,?,1)", ("包子馅大皮薄，性价比高。", "干净,性价比高"))
    c.execute("INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
              "VALUES (3,3,3,?,?,0)", ("加油站设备略旧，自助加油不方便。", "设备旧"))

    # 重算评分
    _recompute_all(c)

    # 示例优惠券（商家2 老字号面馆 -> 满20减5）
    c.execute("INSERT INTO coupons (merchant_id, title, amount, quota, claimed, is_active) "
              "VALUES (2,?,?,?,?,1)", ("老字号面馆 · 满20减5", 5, 100, 0))
    c.execute("INSERT INTO coupons (merchant_id, title, amount, quota, claimed, is_active) "
              "VALUES (5,?,?,?,?,1)", ("庆丰包子铺 · 满15减3", 3, 100, 0))

    conn.commit()
    conn.close()


def _recompute_all(c):
    """根据已审核点评重算所有商户评分"""
    c.execute("SELECT id FROM merchants")
    for (mid,) in c.fetchall():
        row = c.execute(
            "SELECT AVG(rating) FROM reviews WHERE merchant_id=? AND is_approved=1", (mid,)
        ).fetchone()
        rating = round(row[0], 2) if row and row[0] is not None else 0.0
        c.execute("UPDATE merchants SET rating=? WHERE id=?", (rating, mid))


def recompute_merchant_rating(conn, merchant_id):
    row = conn.execute(
        "SELECT AVG(rating) FROM reviews WHERE merchant_id=? AND is_approved=1", (merchant_id,)
    ).fetchone()
    rating = round(row[0], 2) if row and row[0] is not None else 0.0
    conn.execute("UPDATE merchants SET rating=? WHERE id=?", (rating, merchant_id))


def merchant_review_count(conn, merchant_id):
    return conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE merchant_id=? AND is_approved=1", (merchant_id,)
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# HTTP 处理
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _send_static(self, name, content_type):
        """提供静态文件（首页）"""
        path = os.path.join(STATIC_DIR, name)
        if not os.path.exists(path):
            return self._send(404, {"detail": "Not Found"})
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    # ---- 路由 ----
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = urllib.parse.parse_qs(parsed.query)

        try:
            if path in ("", "/index.html"):
                self._send_static("index.html", "text/html")
            elif path == "/health":
                self._send(200, {"status": "ok"})
            elif path == "/service-areas":
                self._handle_list_service_areas()
            elif path.startswith("/service-areas/"):
                self._handle_get_service_area(int(path.rsplit("/", 1)[1]))
            elif path == "/merchants":
                self._handle_list_merchants(params)
            elif path.startswith("/merchants/"):
                self._handle_get_merchant(int(path.rsplit("/", 1)[1]))
            elif path == "/reviews":
                self._handle_list_reviews(params)
            elif path == "/coupons":
                self._handle_list_coupons(params)
            elif path == "/users/me/coupons":
                self._handle_my_coupons(params)
            elif path == "/stats/dashboard":
                self._handle_dashboard()
            elif path.startswith("/users/"):
                self._handle_get_user(int(path.rsplit("/", 1)[1]))
            else:
                self._send(404, {"detail": "Not Found"})
        except ValueError:
            self._send(400, {"detail": "Invalid id"})
        except Exception as e:  # noqa
            self._send(500, {"detail": str(e)})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        try:
            if path == "/users":
                self._handle_create_user(self._read_body())
            elif path == "/service-areas":
                self._handle_create_service_area(self._read_body())
            elif path == "/merchants":
                self._handle_create_merchant(self._read_body())
            elif path == "/reviews":
                self._handle_create_review(self._read_body())
            elif path.startswith("/coupons/") and path.endswith("/claim"):
                cid, uid = int(path.split("/")[2]), self._read_body().get("user_id")
                self._handle_claim_coupon(cid, uid)
            elif path.startswith("/reviews/") and path.endswith("/approve"):
                rid = int(path.split("/")[2])
                self._handle_approve_review(rid)
            else:
                self._send(404, {"detail": "Not Found"})
        except ValueError:
            self._send(400, {"detail": "Invalid id"})
        except Exception as e:  # noqa
            self._send(500, {"detail": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ---- handlers ----
    def _handle_list_service_areas(self):
        conn = get_conn()
        rows = conn.execute("SELECT * FROM service_areas ORDER BY id").fetchall()
        conn.close()
        self._send(200, [dict(r) for r in rows])

    def _handle_get_service_area(self, area_id):
        conn = get_conn()
        row = conn.execute("SELECT * FROM service_areas WHERE id=?", (area_id,)).fetchone()
        conn.close()
        if not row:
            return self._send(404, {"detail": "服务区不存在"})
        self._send(200, dict(row))

    def _handle_list_merchants(self, params):
        conn = get_conn()
        sql = "SELECT * FROM merchants WHERE is_active=1"
        args = []
        if params.get("service_area_id"):
            sql += " AND service_area_id=?"
            args.append(int(params["service_area_id"][0]))
        if params.get("category"):
            sql += " AND category=?"
            args.append(params["category"][0])
        if params.get("min_rating"):
            sql += " AND rating>=?"
            args.append(float(params["min_rating"][0]))
        sql += " ORDER BY rating DESC"
        rows = conn.execute(sql, args).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["review_count"] = merchant_review_count(conn, r["id"])
            result.append(d)
        conn.close()
        self._send(200, result)

    def _handle_get_merchant(self, merchant_id):
        conn = get_conn()
        row = conn.execute("SELECT * FROM merchants WHERE id=?", (merchant_id,)).fetchone()
        if not row:
            conn.close()
            return self._send(404, {"detail": "商户不存在"})
        d = dict(row)
        d["review_count"] = merchant_review_count(conn, merchant_id)
        conn.close()
        self._send(200, d)

    def _handle_create_service_area(self, body):
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO service_areas (name, highway, mile_marker, latitude, longitude, description) "
            "VALUES (?,?,?,?,?,?)",
            (body.get("name"), body.get("highway"), body.get("mile_marker"),
             body.get("latitude"), body.get("longitude"), body.get("description")),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM service_areas WHERE id=?", (cur.lastrowid,)).fetchone()
        conn.close()
        self._send(201, dict(row))

    def _handle_create_merchant(self, body):
        conn = get_conn()
        area_id = body.get("service_area_id")
        if not conn.execute("SELECT id FROM service_areas WHERE id=?", (area_id,)).fetchone():
            conn.close()
            return self._send(404, {"detail": "服务区不存在"})
        cur = conn.execute(
            "INSERT INTO merchants (service_area_id, name, category, avg_price, open_hours, description) "
            "VALUES (?,?,?,?,?,?)",
            (area_id, body.get("name"), body.get("category"), body.get("avg_price"),
             body.get("open_hours"), body.get("description")),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM merchants WHERE id=?", (cur.lastrowid,)).fetchone()
        conn.close()
        self._send(201, dict(row))

    def _handle_create_user(self, body):
        conn = get_conn()
        cur = conn.execute("INSERT INTO users (nickname, phone) VALUES (?,?)",
                           (body.get("nickname"), body.get("phone")))
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
        conn.close()
        self._send(201, dict(row))

    def _handle_get_user(self, user_id):
        conn = get_conn()
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        if not row:
            return self._send(404, {"detail": "用户不存在"})
        self._send(200, dict(row))

    def _handle_list_reviews(self, params):
        merchant_id = int(params.get("merchant_id", [0])[0])
        conn = get_conn()
        rows = conn.execute(
            "SELECT r.*, u.nickname AS user_nickname FROM reviews r "
            "JOIN users u ON u.id = r.user_id "
            "WHERE r.merchant_id=? AND r.is_approved=1 ORDER BY r.created_at DESC",
            (merchant_id,),
        ).fetchall()
        conn.close()
        self._send(200, [dict(r) for r in rows])

    def _handle_create_review(self, body):
        merchant_id = body.get("merchant_id")
        user_id = body.get("user_id")
        rating = body.get("rating")
        if not isinstance(rating, int) or not (1 <= rating <= 5):
            return self._send(422, {"detail": "评分必须在 1-5 之间"})
        conn = get_conn()
        if not conn.execute("SELECT id FROM merchants WHERE id=?", (merchant_id,)).fetchone():
            conn.close()
            return self._send(404, {"detail": "商户不存在"})
        if not conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone():
            conn.close()
            return self._send(404, {"detail": "用户不存在"})
        cur = conn.execute(
            "INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
            "VALUES (?,?,?,?,?,0)",
            (merchant_id, user_id, rating, body.get("content"), body.get("tags")),
        )
        conn.commit()
        row = conn.execute(
            "SELECT r.*, u.nickname AS user_nickname FROM reviews r JOIN users u ON u.id=r.user_id "
            "WHERE r.id=?", (cur.lastrowid,)).fetchone()
        conn.close()
        self._send(201, dict(row))

    def _handle_approve_review(self, review_id):
        conn = get_conn()
        row = conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            conn.close()
            return self._send(404, {"detail": "点评不存在"})
        conn.execute("UPDATE reviews SET is_approved=1 WHERE id=?", (review_id,))
        recompute_merchant_rating(conn, row["merchant_id"])
        conn.commit()
        out = conn.execute(
            "SELECT r.*, u.nickname AS user_nickname FROM reviews r JOIN users u ON u.id=r.user_id "
            "WHERE r.id=?", (review_id,)).fetchone()
        conn.close()
        self._send(200, dict(out))

    # ---- 优惠券 ----
    def _handle_list_coupons(self, params):
        conn = get_conn()
        sql = ("SELECT c.*, m.name AS merchant_name, m.category AS merchant_category "
               "FROM coupons c JOIN merchants m ON m.id=c.merchant_id WHERE c.is_active=1")
        args = []
        if params.get("merchant_id"):
            sql += " AND c.merchant_id=?"
            args.append(int(params["merchant_id"][0]))
        rows = conn.execute(sql + " ORDER BY c.id", args).fetchall()
        conn.close()
        self._send(200, [dict(r) for r in rows])

    def _handle_my_coupons(self, params):
        """当前用户的优惠券"""
        uid = int(params.get("user_id", [0])[0])
        if not uid:
            return self._send(422, {"detail": "缺少 user_id 参数"})
        conn = get_conn()
        rows = conn.execute(
            "SELECT uc.id AS uc_id, uc.used, uc.claimed_at, c.id AS coupon_id, "
            "c.title, c.amount, c.quota, c.claimed, m.name AS merchant_name "
            "FROM user_coupons uc JOIN coupons c ON c.id=uc.coupon_id "
            "JOIN merchants m ON m.id=c.merchant_id "
            "WHERE uc.user_id=? ORDER BY uc.id DESC", (uid,)).fetchall()
        conn.close()
        self._send(200, [dict(r) for r in rows])

    def _handle_claim_coupon(self, coupon_id, user_id):
        if not user_id:
            return self._send(422, {"detail": "缺少 user_id"})
        conn = get_conn()
        coupon = conn.execute("SELECT * FROM coupons WHERE id=? AND is_active=1", (coupon_id,)).fetchone()
        if not coupon:
            conn.close()
            return self._send(404, {"detail": "优惠券不存在或已下架"})
        # 检查是否已领取
        dup = conn.execute(
            "SELECT id FROM user_coupons WHERE user_id=? AND coupon_id=?", (user_id, coupon_id)
        ).fetchone()
        if dup:
            conn.close()
            return self._send(409, {"detail": "该优惠券已领取"})
        # 检查库存
        if coupon["quota"] > 0 and coupon["claimed"] >= coupon["quota"]:
            conn.close()
            return self._send(409, {"detail": "优惠券已被领完"})
        cur = conn.execute(
            "INSERT INTO user_coupons (user_id, coupon_id) VALUES (?,?)", (user_id, coupon_id))
        conn.execute("UPDATE coupons SET claimed=claimed+1 WHERE id=?", (coupon_id,))
        conn.commit()
        row = conn.execute(
            "SELECT uc.id AS uc_id, uc.used, uc.claimed_at, c.id AS coupon_id, "
            "c.title, c.amount, c.quota, c.claimed, m.name AS merchant_name "
            "FROM user_coupons uc JOIN coupons c ON c.id=uc.coupon_id "
            "JOIN merchants m ON m.id=c.merchant_id WHERE uc.id=?",
            (cur.lastrowid,)).fetchone()
        conn.close()
        self._send(201, dict(row))

    # ---- 运营数据看板 ----
    def _handle_dashboard(self):
        conn = get_conn()
        area_count = conn.execute("SELECT COUNT(*) FROM service_areas").fetchone()[0]
        merchant_count = conn.execute("SELECT COUNT(*) FROM merchants WHERE is_active=1").fetchone()[0]
        review_total = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        review_approved = conn.execute("SELECT COUNT(*) FROM reviews WHERE is_approved=1").fetchone()[0]
        review_pending = review_total - review_approved
        avg_rating = conn.execute("SELECT AVG(rating) FROM merchants WHERE is_active=1").fetchone()[0]
        coupon_count = conn.execute("SELECT COUNT(*) FROM coupons WHERE is_active=1").fetchone()[0]
        # 业态分布
        cat_rows = conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM merchants WHERE is_active=1 "
            "GROUP BY category ORDER BY cnt DESC").fetchall()
        # 差评预警（评分 < 3 的商户）
        bad_merchants = conn.execute(
            "SELECT id, name, category, rating FROM merchants "
            "WHERE is_active=1 AND rating > 0 AND rating < 3 ORDER BY rating").fetchall()
        conn.close()
        self._send(200, {
            "service_areas": area_count,
            "merchants": merchant_count,
            "reviews": {"total": review_total, "approved": review_approved, "pending": review_pending},
            "avg_merchant_rating": round(avg_rating, 2) if avg_rating else 0.0,
            "active_coupons": coupon_count,
            "category_distribution": [dict(r) for r in cat_rows],
            "low_rating_merchants": [dict(r) for r in bad_merchants],
        })


def main():
    init_db()
    seed_data()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"服务区点评服务已启动: http://127.0.0.1:{port}")
    print(f"接口文档: GET /health, /service-areas, /merchants, /reviews?merchant_id=N, ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
