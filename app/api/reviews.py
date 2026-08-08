"""点评 API"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=List[schemas.ReviewOut])
def list_reviews(merchant_id: int, db: Session = Depends(get_db)):
    """查看某商户已审核通过的点评"""
    reviews = crud.list_reviews(db, merchant_id)
    result = []
    for r in reviews:
        out = schemas.ReviewOut.model_validate(r)
        out.user_nickname = r.user.nickname if r.user else None
        result.append(out)
    return result


@router.post("", response_model=schemas.ReviewOut, status_code=201)
def create_review(data: schemas.ReviewCreate, db: Session = Depends(get_db)):
    """发表点评（默认待审核）"""
    # 校验商户存在
    if not crud.get_merchant(db, data.merchant_id):
        raise HTTPException(status_code=404, detail="商户不存在")
    # 校验用户存在
    if not crud.get_user(db, data.user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    review = crud.create_review(db, data)
    out = schemas.ReviewOut.model_validate(review)
    out.user_nickname = review.user.nickname if review.user else None
    return out


@router.post("/{review_id}/approve", response_model=schemas.ReviewOut)
def approve_review(review_id: int, db: Session = Depends(get_db)):
    """审核通过点评（运营后台）"""
    review = crud.approve_review(db, review_id, approved=True)
    if not review:
        raise HTTPException(status_code=404, detail="点评不存在")
    out = schemas.ReviewOut.model_validate(review)
    out.user_nickname = review.user.nickname if review.user else None
    return out
