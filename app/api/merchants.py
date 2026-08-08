"""商户 API"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("", response_model=List[schemas.MerchantOut])
def list_merchants(
    service_area_id: Optional[int] = None,
    category: Optional[str] = None,
    min_rating: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """商户列表，支持按服务区/业态/最低评分筛选"""
    merchants = crud.list_merchants(db, service_area_id, category, min_rating)
    result = []
    for m in merchants:
        out = schemas.MerchantOut.model_validate(m)
        out.review_count = len([r for r in m.reviews if r.is_approved])
        result.append(out)
    return result


@router.get("/{merchant_id}", response_model=schemas.MerchantOut)
def get_merchant(merchant_id: int, db: Session = Depends(get_db)):
    """商户详情"""
    merchant = crud.get_merchant(db, merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="商户不存在")
    out = schemas.MerchantOut.model_validate(merchant)
    out.review_count = len([r for r in merchant.reviews if r.is_approved])
    return out


@router.post("", response_model=schemas.MerchantOut, status_code=201)
def create_merchant(data: schemas.MerchantCreate, db: Session = Depends(get_db)):
    """新建商户（运营后台）"""
    return crud.create_merchant(db, data)
