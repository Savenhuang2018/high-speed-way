"""Pydantic 请求/响应模型"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------- 用户 ----------
class UserCreate(BaseModel):
    nickname: str = Field(..., max_length=64)
    phone: Optional[str] = None


class UserOut(BaseModel):
    id: int
    nickname: str
    phone: Optional[str]

    class Config:
        from_attributes = True


# ---------- 服务区 ----------
class ServiceAreaBase(BaseModel):
    name: str
    highway: str
    mile_marker: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None


class ServiceAreaCreate(ServiceAreaBase):
    pass


class ServiceAreaOut(ServiceAreaBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- 商户 ----------
class MerchantBase(BaseModel):
    service_area_id: int
    name: str
    category: str
    avg_price: Optional[float] = None
    open_hours: Optional[str] = None
    description: Optional[str] = None


class MerchantCreate(MerchantBase):
    pass


class MerchantOut(MerchantBase):
    id: int
    rating: float
    is_active: bool
    created_at: datetime
    review_count: int = 0

    class Config:
        from_attributes = True


# ---------- 点评 ----------
class ReviewCreate(BaseModel):
    merchant_id: int
    user_id: int
    rating: int = Field(..., ge=1, le=5)
    content: Optional[str] = None
    tags: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    merchant_id: int
    user_id: int
    rating: int
    content: Optional[str]
    tags: Optional[str]
    is_approved: bool
    created_at: datetime
    user_nickname: Optional[str] = None

    class Config:
        from_attributes = True
