"""ORM 数据模型：服务区、商户、业态、点评、用户"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """车主用户"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String(64), nullable=False)
    avatar = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    reviews = relationship("Review", back_populates="user")


class ServiceArea(Base):
    """高速公路服务区"""
    __tablename__ = "service_areas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, unique=True)
    highway = Column(String(128), nullable=False)       # 所属高速
    mile_marker = Column(String(32), nullable=True)     # 里程桩号
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    merchants = relationship("Merchant", back_populates="service_area")


class Merchant(Base):
    """服务区内的商户（餐饮/便利店/加油站/充电等）"""
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    service_area_id = Column(Integer, ForeignKey("service_areas.id"), nullable=False)
    name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)       # 业态：餐饮/便利店/加油/充电/维修/住宿...
    avg_price = Column(Float, nullable=True)            # 人均价（元）
    open_hours = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    rating = Column(Float, default=0.0)                 # 综合评分（冗余字段）
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    service_area = relationship("ServiceArea", back_populates="merchants")
    reviews = relationship("Review", back_populates="merchant")


class Review(Base):
    """点评"""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)            # 1-5 星
    content = Column(Text, nullable=True)
    tags = Column(String(255), nullable=True)           # 逗号分隔标签，如 "干净,排队久"
    is_approved = Column(Boolean, default=False)        # 审核状态
    created_at = Column(DateTime, default=datetime.utcnow)

    merchant = relationship("Merchant", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
