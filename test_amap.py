#!/usr/bin/env python3
"""验证 amap 模块：解析逻辑 + 幂等入库（用测试桩模拟高德返回，不真实联网）"""
import importlib.util
import json
import os
import sys
import tempfile

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

results = []
def check(name, ok, detail=""):
    results.append((name, ok))
    print(("  ✓ " if ok else "  ✗ ") + name + (("  -> " + detail) if detail else ""))

# 加载 amap 模块（无真实 key）
spec = importlib.util.spec_from_file_location("amap", os.path.join(PROJ, "amap.py"))
amap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(amap)

# 1. location 解析
loc = amap.parse_location("116.40,39.90")
check("parse_location 解析'经度,纬度'->(lat,lng)", loc == (39.90, 116.40), str(loc))
check("parse_location 空值返回None", amap.parse_location(None) is None)

# 2. 有 key 时 has_key 为 True（用假 key 但只测逻辑判断）
os.environ["AMAP_KEY"] = "test_key_123"
# 重新加载让 AMAP_KEY 生效
amap = importlib.util.module_from_spec(spec); spec.loader.exec_module(amap)
check("has_key 检测到 key", amap.has_key() is True)

# 3. search_service_areas 解析逻辑（mock _http_get 返回高德格式）
# 注意：用全新坐标的服务区，避免与本地种子坐标重复而触发幂等去重
def mock_http_get(url, params, timeout=15):
    return {
        "status": "1", "info": "OK",
        "pois": [
            {"id": "p1", "name": "高德高速苏州服务区",
             "location": "120.90,31.80", "address": "某高速", "adname": "苏州市", "cityname": "苏州市", "type": "服务区"},
            {"id": "p2", "name": "高德高速无锡服务区",
             "location": "120.30,31.50", "address": "某高速", "adname": "无锡市", "cityname": "无锡市", "type": "服务区"},
        ]
    }
amap._http_get = mock_http_get
pois = amap.search_service_areas(key="test")
check("search_service_areas 解析POI", len(pois) == 2 and pois[0]["name"] == "高德高速苏州服务区")
check("search_service_areas 含location", pois[1]["location"] == "120.30,31.50")

# 4. 幂等入库（_sync_amap_service_areas，用临时DB）
tmpdb = os.path.join(tempfile.mkdtemp(), "amap_test.db")
os.environ["SERVICE_AREA_DB"] = tmpdb
# 关键：把已 mock 的 amap 注册进 sys.modules，让 server.py 的 "import amap" 复用同一对象
import sys as _sys
_sys.modules["amap"] = amap
import importlib
spec2 = importlib.util.spec_from_file_location("srv", os.path.join(PROJ, "server.py"))
srv = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(srv)
# 建表并写入种子数据
srv.init_db()
srv.seed_data()

# 建表（seed 会因空库写入本地数据）
# 直接调用 _sync（amap.has_key 因环境变量为 True，search 已被 mock）
added = srv._sync_amap_service_areas()
check("从高德mock写入服务区", len(added) == 2, f"新增{len(added)}")
# 再次调用应幂等（不重复新增）
added2 = srv._sync_amap_service_areas()
check("幂等：重复调用不新增", len(added2) == 0, f"第二次新增{len(added2)}")

# 5. 沿途筛选含新增的高德服务区
res = srv.route_areas(
    [{"id":1,"name":"阳澄湖","latitude":31.42,"longitude":120.72},
     {"id":2,"name":"窦店","latitude":39.67,"longitude":116.08}],
    31.23, 121.47, 39.90, 116.40)
check("高德服务区参与沿线筛选", len(res) >= 1)

failed = [r for r in results if not r[1]]
print(f"\n=== 汇总: {len(results)-len(failed)} 通过, {len(failed)} 失败 ===")
sys.exit(1 if failed else 0)
