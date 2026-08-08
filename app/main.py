"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .api import service_areas, merchants, reviews, users

# 创建数据表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="高速公路服务区车主服务与点评 API",
    description="车主服务 + 大众点评，MVP 后端",
    version="0.1.0",
)

# CORS（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(service_areas.router)
app.include_router(merchants.router)
app.include_router(reviews.router)
app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok"}
