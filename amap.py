#!/usr/bin/env python3
"""
高德地图接入模块 —— 获取高速公路服务区信息
=============================================
零依赖（标准库 + urllib）。通过高德 Web 服务 API 获取沿途高速公路服务区。

设计：
- 优先使用真实高德 API（需 AMAP_KEY，见下方配置）
- 未配置 key 时回退到本地种子数据（保证功能可跑、可测试）

两种接口（Web 服务 API，需免费 key，申请: https://lbs.amap.com）：
  1. 驾车路径规划 GET /v3/direction/driving
     入参: origin=经度,纬度  destination=经度,纬度  key=...
     返回: route.paths[0].steps[].polyline（路线坐标串）
  2. 关键词搜索  GET /v3/place/text
     入参: keywords=高速公路服务区  key=...  city=...  offset=25
     返回: pois[]（服务区 POI，含 location "经度,纬度"、name、address）

配置（二选一）：
  - 环境变量 AMAP_KEY
  - ~/.hermes/.env 里加 AMAP_KEY=xxx  （Hermes 会加载）
"""
import json
import os
import urllib.parse
import urllib.request

AMAP_KEY = os.environ.get("AMAP_KEY", "").strip()
AMAP_PLACE_TEXT = "https://restapi.amap.com/v3/place/text"
AMAP_PLACE_AROUND = "https://restapi.amap.com/v3/place/around"
AMAP_DIRECTION = "https://restapi.amap.com/v3/direction/driving"

# 高德服务区关键词（POI 名称通常含"服务区"）
SERVICE_AREA_KEYWORDS = "高速公路服务区"
# 高德搜索默认城市：空 = 全国
DEFAULT_CITY = ""


def _http_get(url, params, timeout=15):
    """GET 请求，返回 JSON"""
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def has_key():
    """是否配置了高德 API key"""
    return bool(AMAP_KEY)


def search_service_areas(key=None, city=DEFAULT_CITY, keywords=SERVICE_AREA_KEYWORDS,
                         offset=30, page=1):
    """按关键词搜索高速公路服务区 POI。
    返回 list[dict]，每项含 name / location("经度,纬度") / address / adname / distance。
    """
    k = key or AMAP_KEY
    if not k:
        raise RuntimeError("未配置高德 API key（AMAP_KEY）")
    data = _http_get(AMAP_PLACE_TEXT, {
        "key": k, "keywords": keywords, "city": city,
        "offset": offset, "page": page, "extensions": "all",
    })
    if data.get("status") != "1":
        raise RuntimeError(f"高德搜索失败: {data.get('info', 'unknown')}")
    pois = data.get("pois", [])
    return [{
        "id": p.get("id"),
        "name": p.get("name"),
        "location": p.get("location"),          # "经度,纬度"
        "address": p.get("address"),
        "adname": p.get("adname"),
        "cityname": p.get("cityname"),
        "type": p.get("type"),
    } for p in pois]


def driving_route(origin, destination, key=None, strategy=0):
    """驾车路径规划。
    origin/destination: "经度,纬度"。
    返回路径坐标点 list[(lng, lat)]（按行进顺序）。
    """
    k = key or AMAP_KEY
    if not k:
        raise RuntimeError("未配置高德 API key（AMAP_KEY）")
    data = _http_get(AMAP_DIRECTION, {
        "key": k, "origin": origin, "destination": destination,
        "strategy": strategy, "extensions": "base",
    })
    if data.get("status") != "1":
        raise RuntimeError(f"高德路径规划失败: {data.get('info', 'unknown')}")
    paths = data.get("route", {}).get("paths", [])
    if not paths:
        return []
    # 提取所有 step 的 polyline，拼成完整坐标点序列
    points = []
    for step in paths[0].get("steps", []):
        for seg in step.get("polyline", "").split(";"):
            if seg:
                lng, lat = seg.split(",")
                points.append((float(lng), float(lat)))
    return points


def parse_location(loc):
    """解析高德 location "经度,纬度" -> (lat, lng)"""
    if not loc or "," not in loc:
        return None
    lng, lat = loc.split(",")
    return float(lat), float(lng)


def nearby_service_areas(center_lng, center_lat, key=None, radius=30000, keywords=SERVICE_AREA_KEYWORDS):
    """周边搜索：以某点为中心搜索附近服务区（半径米）。"""
    k = key or AMAP_KEY
    if not k:
        raise RuntimeError("未配置高德 API key（AMAP_KEY）")
    data = _http_get(AMAP_PLACE_AROUND, {
        "key": k, "location": f"{center_lng},{center_lat}",
        "radius": radius, "keywords": keywords, "offset": 25, "extensions": "all",
    })
    if data.get("status") != "1":
        raise RuntimeError(f"高德周边搜索失败: {data.get('info', 'unknown')}")
    pois = data.get("pois", [])
    return [{
        "id": p.get("id"), "name": p.get("name"),
        "location": p.get("location"), "address": p.get("address"),
        "adname": p.get("adname"), "distance": p.get("distance"),
    } for p in pois]


if __name__ == "__main__":
    # 自检/演示
    print("AMAP_KEY 已配置:", has_key())
    if has_key():
        # 例：北京某段高速周边服务区
        try:
            pois = search_service_areas(city="010")
            print("搜索到服务区 POI:", len(pois))
            for p in pois[:10]:
                print("  -", p["name"], p["location"], p.get("adname"))
        except Exception as e:
            print("调用失败:", e)
    else:
        print("未配置 key，无法真实调用。请设置环境变量 AMAP_KEY。")
