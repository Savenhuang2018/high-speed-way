"""数据访问层：封装数据库操作"""
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models, schemas


# ---------- 用户 ----------
def create_user(db: Session, data: schemas.UserCreate) -> models.User:
    user = models.User(nickname=data.nickname, phone=data.phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


# ---------- 服务区 ----------
def list_service_areas(db: Session) -> List[models.ServiceArea]:
    return db.query(models.ServiceArea).order_by(models.ServiceArea.id).all()


def get_service_area(db: Session, area_id: int) -> Optional[models.ServiceArea]:
    return db.query(models.ServiceArea).filter(models.ServiceArea.id == area_id).first()


def create_service_area(db: Session, data: schemas.ServiceAreaCreate) -> models.ServiceArea:
    area = models.ServiceArea(**data.model_dump())
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


# ---------- 商户 ----------
def list_merchants(
    db: Session,
    service_area_id: Optional[int] = None,
    category: Optional[str] = None,
    min_rating: Optional[float] = None,
) -> List[models.Merchant]:
    query = db.query(models.Merchant)
    if service_area_id is not None:
        query = query.filter(models.Merchant.service_area_id == service_area_id)
    if category:
        query = query.filter(models.Merchant.category == category)
    if min_rating is not None:
        query = query.filter(models.Merchant.rating >= min_rating)
    return query.order_by(models.Merchant.rating.desc()).all()


def get_merchant(db: Session, merchant_id: int) -> Optional[models.Merchant]:
    return db.query(models.Merchant).filter(models.Merchant.id == merchant_id).first()


def create_merchant(db: Session, data: schemas.MerchantCreate) -> models.Merchant:
    merchant = models.Merchant(**data.model_dump())
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


# ---------- 点评 ----------
def create_review(db: Session, data: schemas.ReviewCreate) -> models.Review:
    review = models.Review(
        merchant_id=data.merchant_id,
        user_id=data.user_id,
        rating=data.rating,
        content=data.content,
        tags=data.tags,
        is_approved=False,  # 默认待审核
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    _recompute_merchant_rating(db, data.merchant_id)
    return review


def list_reviews(db: Session, merchant_id: int) -> List[models.Review]:
    return (
        db.query(models.Review)
        .filter(models.Review.merchant_id == merchant_id, models.Review.is_approved == True)  # noqa: E712
        .order_by(models.Review.created_at.desc())
        .all()
    )


def approve_review(db: Session, review_id: int, approved: bool = True) -> Optional[models.Review]:
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        return None
    review.is_approved = approved
    db.commit()
    db.refresh(review)
    if approved:
        _recompute_merchant_rating(db, review.merchant_id)
    return review


def _recompute_merchant_rating(db: Session, merchant_id: int) -> None:
    """重算商户综合评分（已通过审核点评的平均分）"""
    avg = (
        db.query(func.avg(models.Review.rating))
        .filter(
            models.Review.merchant_id == merchant_id,
            models.Review.is_approved == True,  # noqa: E712
        )
        .scalar()
    )
    merchant = db.query(models.Merchant).filter(models.Merchant.id == merchant_id).first()
    if merchant:
        merchant.rating = round(avg, 2) if avg is not None else 0.0
        db.commit()
