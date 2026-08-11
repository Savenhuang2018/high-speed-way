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

import amap

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
            merchant_reply TEXT,
            replied_at TEXT,
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
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            area_id INTEGER NOT NULL REFERENCES service_areas(id),
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, area_id)
        );
        """
    )
    conn.commit()
    _migrate(conn)
    conn.close()


def _migrate(conn):
    """轻量迁移：为已存在的旧表补充新增列（幂等）"""
    def add_col(table, col, ddl):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

    add_col("reviews", "merchant_reply", "TEXT")
    add_col("reviews", "replied_at", "TEXT")
    conn.commit()


# ---------------------------------------------------------------------------
# 地理计算：沿途服务区筛选
# ---------------------------------------------------------------------------
import math


def haversine_km(lat1, lng1, lat2, lng2):
    """两点球面距离（公里）"""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _local_xy(lat, lng, ref_lat, ref_lng):
    """以参考点为原点的局部平面坐标（公里，近似）"""
    x = haversine_km(ref_lat, ref_lng, ref_lat, lng) * (1 if lng >= ref_lng else -1)
    y = haversine_km(ref_lat, ref_lng, lat, ref_lng) * (1 if lat >= ref_lat else -1)
    return x, y


def route_projection_km(cur_lat, cur_lng, dest_lat, dest_lng, area_lat, area_lng):
    """计算服务区相对「当前位置->目的地」路径的位置。
    返回 (off_path_km, along_km)：
      - off_path_km: 服务区到路径直线的垂直距离（公里），越小越在路线旁
      - along_km: 沿路径方向从当前位置到服务区的投影距离（公里）。
                  正值 = 在前方（接下来会到）；负值 = 已越过。
    用当前->目的地方向为局部坐标 X 轴做平面近似。
    """
    # 以当前位置为原点
    ox, oy = _local_xy(cur_lat, cur_lng, cur_lat, cur_lng)  # = (0,0)
    dx, dy = _local_xy(dest_lat, dest_lng, cur_lat, cur_lng)
    ax, ay = _local_xy(area_lat, area_lng, cur_lat, cur_lng)

    seg_len = math.hypot(dx, dy)
    if seg_len < 1e-6:
        return math.hypot(ax, ay), 0.0

    # 单位方向向量 u = (ux, uy)
    ux, uy = dx / seg_len, dy / seg_len
    # 服务区向量 A 在路径方向上的投影（沿程距离）
    along = ax * ux + ay * uy
    # 垂直分量（偏离路径的距离）
    perp_x, perp_y = ax - along * ux, ay - along * uy
    off = math.hypot(perp_x, perp_y)
    return off, along


def route_areas(areas, cur_lat, cur_lng, dest_lat, dest_lng,
                max_off_km=100.0, past_km=0.0):
    """筛选「当前位置到目的地」沿途的服务区。
    判定：服务区到路径直线的垂直距离 <= max_off_km（在高速沿线），
    且沿程投影 > past_km（默认>0，即在当前位置前方，排除已过的）。
    返回按沿程距离升序（最近的在前面）的服务区列表（含 distance_km 字段）。
    """
    result = []
    for a in areas:
        if a["latitude"] is None or a["longitude"] is None:
            continue
        off, along = route_projection_km(
            cur_lat, cur_lng, dest_lat, dest_lng, a["latitude"], a["longitude"])
        if off <= max_off_km and along > past_km:
            item = dict(a)
            item["off_path_km"] = round(off, 1)
            item["distance_km"] = round(along, 1)  # 距当前沿程距离
            result.append(item)
    result.sort(key=lambda x: x["distance_km"])
    return result


def _sync_amap_service_areas():
    """从高德拉取沿途服务区 POI 并写入本地表（幂等：已存在则更新坐标）。
    返回本次新增/更新的服务区 ID 列表。无 key 或失败时返回空（静默回退）。
    """
    if not amap.has_key():
        return []
    try:
        pois = amap.search_service_areas()
    except Exception:
        return []
    conn = get_conn()
    added = []
    for p in pois:
        loc = amap.parse_location(p.get("location"))
        if not loc:
            continue
        lat, lng = loc
        name = (p.get("name") or "").strip() or "高德服务区"
        # 名称/经纬度做幂等匹配：已有同名则跳过
        exists = conn.execute(
            "SELECT id FROM service_areas WHERE name=? OR "
            "(ABS(latitude-?)<0.01 AND ABS(longitude-?)<0.01)",
            (name, lat, lng)).fetchone()
        if exists:
            continue
        cur = conn.execute(
            "INSERT INTO service_areas (name, highway, mile_marker, latitude, longitude, description) "
            "VALUES (?,?,?,?,?,?)",
            (name, "高德数据", None, lat, lng,
             f"来源：高德地图。{(p.get('address') or '')} {(p.get('adname') or '')}"))
        added.append(cur.lastrowid)
    conn.commit()
    conn.close()
    return added


def _handle_route_areas(self, params):
    """GET /route/areas?cur_lat=&cur_lng=&dest_lat=&dest_lng=&max_off_km=
    返回当前位置到目的地方向沿途的服务区（按沿程距离升序）。
    数据源：优先高德 API（若配置 key）补充，再结合本地库，用几何算法沿线筛选。
    """
    try:
        cur_lat = float(params["cur_lat"][0])
        cur_lng = float(params["cur_lng"][0])
        dest_lat = float(params["dest_lat"][0])
        dest_lng = float(params["dest_lng"][0])
    except (KeyError, ValueError):
        return self._send(422, {"detail": "需要 cur_lat/cur_lng/dest_lat/dest_lng 参数"})
    max_off = float(params["max_off_km"][0]) if params.get("max_off_km") else 100.0

    # 有高德 key 时先补充数据源
    source = "local"
    if amap.has_key():
        _sync_amap_service_areas()
        source = "amap"

    conn = get_conn()
    areas = [dict(r) for r in conn.execute("SELECT * FROM service_areas").fetchall()]
    conn.close()
    result = route_areas(areas, cur_lat, cur_lng, dest_lat, dest_lng, max_off)
    # 标注数据来源
    for r in result:
        r["data_source"] = source
    self._send(200, result)


# 敏感词表（用于点评自动审核，命中则转人工）
SENSITIVE_WORDS = ["脏话", "垃圾服务", "坑人", "骗子", "难吃到爆炸"]


def review_needs_manual_review(content, tags):
    """点评是否需要人工审核：
    - 命中敏感词 -> 人工审核
    - 评分为低分（<=2）由调用方另行判断
    返回 (needs_review, matched_word)
    """
    if not content and not tags:
        return True, None  # 空内容交给人工
    text = f"{content or ''} {tags or ''}"
    for w in SENSITIVE_WORDS:
        if w in text:
            return True, w
    return False, None


def auto_approve_policy(rating, content, tags):
    """智能审核策略：
    返回 (is_approved, matched_word)
    命中敏感词或低分(<=2) -> 不自动通过（转人工）；否则自动通过
    """
    needs, word = review_needs_manual_review(content, tags)
    if needs:
        return False, word
    if rating <= 2:
        return False, None  # 低分差评，人工复核
    return True, None


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

    # G2 京沪高速「上海->北京」方向沿线服务区序列（用于沿途算法演示）
    g2_areas = [
        ("沪宁高速梅村服务区", "G2京沪高速", "K1090", 31.60, 120.42, "无锡段综合服务区，餐饮种类多。"),
        ("京沪高速高邮服务区", "G2京沪高速", "K935", 32.80, 119.45, "扬州北服务区，特产丰富。"),
        ("京沪高速沭阳服务区", "G2京沪高速", "K755", 34.11, 118.78, "苏北大型服务区，停车位充足。"),
        ("京沪高速郯城服务区", "G2京沪高速", "K615", 34.61, 118.35, "鲁南重要节点服务区。"),
        ("京沪高速新泰服务区", "G2京沪高速", "K505", 35.91, 117.77, "山东中段服务区。"),
        ("京沪高速德州服务区", "G2京沪高速", "K375", 37.43, 116.29, "鲁西北服务区，近冀鲁交界。"),
        ("京沪高速沧州服务区", "G2京沪高速", "K260", 38.30, 116.83, "河北段服务区。"),
    ]
    for name, hw, km, lat, lng, desc in g2_areas:
        c.execute(
            "INSERT INTO service_areas (name, highway, mile_marker, latitude, longitude, description) "
            "VALUES (?,?,?,?,?,?)", (name, hw, km, lat, lng, desc))

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
        """提供静态文件"""
        path = os.path.join(STATIC_DIR, name)
        if not os.path.exists(path):
            return self._send(404, {"detail": "Not Found"})
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        # 文本类型加 charset，二进制类型不加
        if content_type.startswith(("text/", "application/javascript", "application/manifest+json", "application/json")):
            self.send_header("Content-Type", content_type + "; charset=utf-8")
        else:
            self.send_header("Content-Type", content_type)
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
            elif path == "/admin":
                self._send_static("admin.html", "text/html")
            elif path == "/manifest.json":
                self._send_static("manifest.json", "application/manifest+json")
            elif path == "/sw.js":
                self._send_static("sw.js", "application/javascript")
            elif path == "/icon-192.png":
                self._send_static("icon-192.png", "image/png")
            elif path == "/icon-512.png":
                self._send_static("icon-512.png", "image/png")
            elif path == "/health":
                self._send(200, {"status": "ok"})
            elif path == "/service-areas":
                self._handle_list_service_areas()
            elif path == "/service-areas/search":
                self._handle_search_service_areas(params)
            elif path == "/route/areas":
                _handle_route_areas(self, params)
            elif path.startswith("/service-areas/"):
                self._handle_get_service_area(int(path.rsplit("/", 1)[1]))
            elif path == "/merchants":
                self._handle_list_merchants(params)
            elif path.startswith("/merchants/"):
                self._handle_get_merchant(int(path.rsplit("/", 1)[1]))
            elif path == "/reviews":
                self._handle_list_reviews(params)
            elif path == "/reviews/pending":
                self._handle_list_pending_reviews()
            elif path == "/reviews/all":
                self._handle_list_all_reviews()
            elif path == "/coupons":
                self._handle_list_coupons(params)
            elif path == "/users/me/coupons":
                self._handle_my_coupons(params)
            elif path == "/stats/dashboard":
                self._handle_dashboard()
            elif path == "/favorites":
                self._handle_list_favorites(params)
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
            elif path == "/favorites/toggle":
                self._handle_toggle_favorite(self._read_body())
            elif path.startswith("/coupons/") and path.endswith("/claim"):
                cid, uid = int(path.split("/")[2]), self._read_body().get("user_id")
                self._handle_claim_coupon(cid, uid)
            elif path.startswith("/reviews/") and path.endswith("/reply"):
                rid = int(path.split("/")[2])
                self._handle_merchant_reply(rid, self._read_body())
            elif path.startswith("/reviews/") and path.endswith("/approve"):
                rid = int(path.split("/")[2])
                self._handle_approve_review(rid)
            elif path.startswith("/reviews/") and path.endswith("/reject"):
                rid = int(path.split("/")[2])
                self._handle_reject_review(rid)
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

    def _handle_search_service_areas(self, params):
        """GET /service-areas/search?q=关键词
        按名称/高速/桩号/描述模糊搜索服务区，返回附带商户数、评分、业态标签。
        """
        q = (params.get("q", [""])[0] or "").strip()
        if not q:
            return self._send(422, {"detail": "缺少搜索关键词 q"})
        conn = get_conn()
        like = f"%{q}%"
        rows = conn.execute(
            "SELECT * FROM service_areas "
            "WHERE name LIKE ? OR highway LIKE ? OR mile_marker LIKE ? OR description LIKE ? "
            "ORDER BY id", (like, like, like, like)
        ).fetchall()
        result = []
        for a in rows:
            item = dict(a)
            area_id = a["id"]
            # 商户数
            mcnt = conn.execute(
                "SELECT COUNT(*) FROM merchants WHERE service_area_id=? AND is_active=1",
                (area_id,)).fetchone()[0]
            item["merchant_count"] = mcnt
            # 平均评分（有商户时）
            avg = conn.execute(
                "SELECT AVG(rating) FROM merchants WHERE service_area_id=? AND is_active=1",
                (area_id,)).fetchone()[0]
            item["avg_rating"] = round(avg, 2) if avg else 0.0
            # 业态标签
            cats = conn.execute(
                "SELECT DISTINCT category FROM merchants WHERE service_area_id=? AND is_active=1",
                (area_id,)).fetchall()
            item["categories"] = [c[0] for c in cats]
            result.append(item)
        conn.close()
        self._send(200, result)

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

    def _handle_list_pending_reviews(self):
        """后台：列出待审核点评"""
        conn = get_conn()
        rows = conn.execute(
            "SELECT r.*, u.nickname AS user_nickname FROM reviews r "
            "JOIN users u ON u.id = r.user_id "
            "WHERE r.is_approved=0 ORDER BY r.created_at DESC").fetchall()
        conn.close()
        self._send(200, [dict(r) for r in rows])

    def _handle_list_all_reviews(self):
        """后台：列出全部点评（含待审核）"""
        conn = get_conn()
        rows = conn.execute(
            "SELECT r.*, u.nickname AS user_nickname FROM reviews r "
            "JOIN users u ON u.id = r.user_id "
            "ORDER BY r.created_at DESC").fetchall()
        conn.close()
        self._send(200, [dict(r) for r in rows])

    def _handle_reject_review(self, review_id):
        """后台：驳回点评（删除）"""
        conn = get_conn()
        row = conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            conn.close()
            return self._send(404, {"detail": "点评不存在"})
        conn.execute("DELETE FROM reviews WHERE id=?", (review_id,))
        conn.commit()
        conn.close()
        self._send(200, {"detail": "点评已驳回", "id": review_id})

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
        # 智能审核：命中敏感词或低分(<=2) -> 转人工；否则自动通过
        is_approved, matched = auto_approve_policy(
            rating, body.get("content"), body.get("tags"))
        cur = conn.execute(
            "INSERT INTO reviews (merchant_id, user_id, rating, content, tags, is_approved) "
            "VALUES (?,?,?,?,?,?)",
            (merchant_id, user_id, rating, body.get("content"), body.get("tags"), int(is_approved)),
        )
        conn.commit()
        if is_approved:
            recompute_merchant_rating(conn, merchant_id)
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

    def _handle_merchant_reply(self, review_id, body):
        """商户回复点评"""
        reply = (body.get("reply") or "").strip()
        if not reply:
            return self._send(422, {"detail": "回复内容不能为空"})
        conn = get_conn()
        row = conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            conn.close()
            return self._send(404, {"detail": "点评不存在"})
        if not row["is_approved"]:
            conn.close()
            return self._send(409, {"detail": "点评尚未审核通过，无法回复"})
        conn.execute(
            "UPDATE reviews SET merchant_reply=?, replied_at=datetime('now') WHERE id=?",
            (reply, review_id))
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

    # ---- 收藏 ----
    def _handle_list_favorites(self, params):
        """GET /favorites?user_id=N 当前用户收藏的服务区列表"""
        try:
            uid = int(params.get("user_id", ["0"])[0])
        except ValueError:
            return self._send(422, {"detail": "user_id 无效"})
        if not uid:
            return self._send(422, {"detail": "缺少 user_id 参数"})
        conn = get_conn()
        rows = conn.execute(
            "SELECT sa.*, f.created_at AS fav_time FROM favorites f "
            "JOIN service_areas sa ON sa.id = f.area_id "
            "WHERE f.user_id=? ORDER BY f.created_at DESC", (uid,)).fetchall()
        result = []
        for a in rows:
            item = dict(a)
            area_id = a["id"]
            mcnt = conn.execute(
                "SELECT COUNT(*) FROM merchants WHERE service_area_id=? AND is_active=1",
                (area_id,)).fetchone()[0]
            item["merchant_count"] = mcnt
            result.append(item)
        conn.close()
        self._send(200, result)

    def _handle_toggle_favorite(self, body):
        """POST /favorites/toggle {user_id, area_id} 收藏/取消收藏（幂等切换）"""
        uid = body.get("user_id")
        aid = body.get("area_id")
        if not uid or not aid:
            return self._send(422, {"detail": "需要 user_id 和 area_id"})
        conn = get_conn()
        if not conn.execute("SELECT id FROM service_areas WHERE id=?", (aid,)).fetchone():
            conn.close()
            return self._send(404, {"detail": "服务区不存在"})
        existing = conn.execute(
            "SELECT id FROM favorites WHERE user_id=? AND area_id=?", (uid, aid)).fetchone()
        if existing:
            conn.execute("DELETE FROM favorites WHERE id=?", (existing["id"],))
            conn.commit()
            conn.close()
            return self._send(200, {"favorited": False, "area_id": aid})
        conn.execute("INSERT INTO favorites (user_id, area_id) VALUES (?,?)", (uid, aid))
        conn.commit()
        conn.close()
        return self._send(200, {"favorited": True, "area_id": aid})


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
