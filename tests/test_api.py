"""API 集成测试（使用临时测试数据库）

注意：必须在导入 app 之前设置 SQLALCHEMY_DATABASE_URL 环境变量，
这样 app/database.py 模块级代码会直接创建指向测试库的 engine。
"""
import os
import tempfile

_tmpdir = tempfile.mkdtemp()
os.environ["SQLALCHEMY_DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal, get_db
from app import models

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前重建表结构"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_basic():
    """写入最小基础数据，返回 (user_id, area_id, merchant_id)"""
    db = SessionLocal()
    u = models.User(nickname="测试用户")
    a = models.ServiceArea(name="测试服务区", highway="G1")
    db.add_all([u, a])
    db.commit()
    m = models.Merchant(service_area_id=a.id, name="测试餐馆", category="餐饮")
    db.add(m)
    db.commit()
    uid, aid, mid = u.id, a.id, m.id
    db.close()
    return uid, aid, mid


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_user_and_get():
    r = client.post("/users", json={"nickname": "老王", "phone": "13800000000"})
    assert r.status_code == 201
    uid = r.json()["id"]
    r2 = client.get(f"/users/{uid}")
    assert r2.status_code == 200
    assert r2.json()["nickname"] == "老王"


def test_service_area_list_and_create():
    r = client.get("/service-areas")
    assert r.status_code == 200
    before = len(r.json())
    r = client.post("/service-areas", json={"name": "新服务区", "highway": "G42"})
    assert r.status_code == 201
    r = client.get("/service-areas")
    assert len(r.json()) == before + 1


def test_merchant_list_filter():
    _, aid, mid = _seed_basic()
    r = client.get(f"/merchants?service_area_id={aid}")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["category"] == "餐饮"


def test_review_flow_pending_then_approve():
    uid, aid, mid = _seed_basic()
    # 提交点评 -> 待审核
    r = client.post("/reviews", json={"merchant_id": mid, "user_id": uid, "rating": 5, "content": "很好吃"})
    assert r.status_code == 201
    assert r.json()["is_approved"] is False
    rid = r.json()["id"]
    # 审核前列表为空
    r = client.get(f"/reviews?merchant_id={mid}")
    assert r.json() == []
    # 审核通过
    r = client.post(f"/reviews/{rid}/approve")
    assert r.status_code == 200
    assert r.json()["is_approved"] is True
    # 审核后可见
    r = client.get(f"/reviews?merchant_id={mid}")
    assert len(r.json()) == 1
    # 商户评分更新
    r = client.get(f"/merchants/{mid}")
    assert r.json()["rating"] == 5.0
    assert r.json()["review_count"] == 1


def test_review_rating_validation():
    uid, aid, mid = _seed_basic()
    r = client.post("/reviews", json={"merchant_id": mid, "user_id": uid, "rating": 6})
    assert r.status_code == 422  # 评分超出 1-5 范围
