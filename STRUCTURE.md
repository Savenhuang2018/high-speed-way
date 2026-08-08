# 高速公路服务区「车主服务 + 大众点评」MVP
# 技术栈：FastAPI + SQLAlchemy + SQLite

app/
  __init__.py
  main.py            # FastAPI 应用入口
  database.py        # 数据库连接与 Session
  models.py          # ORM 模型
  schemas.py         # Pydantic 请求/响应模型
  crud.py            # 数据访问层
  api/
    __init__.py
    service_areas.py # 服务区相关接口
    merchants.py     # 商户相关接口
    reviews.py       # 点评相关接口
    users.py         # 用户相关接口
  seed.py            # 种子数据
tests/
  test_api.py
requirements.txt
README.md
