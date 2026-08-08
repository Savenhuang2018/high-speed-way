"""服务区 API"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/service-areas", tags=["service-areas"])


@router.get("", response_model=List[schemas.ServiceAreaOut])
def list_areas(db: Session = Depends(get_db)):
    """获取全部服务区列表"""
    return crud.list_service_areas(db)


@router.get("/{area_id}", response_model=schemas.ServiceAreaOut)
def get_area(area_id: int, db: Session = Depends(get_db)):
    """获取单个服务区详情"""
    area = crud.get_service_area(db, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="服务区不存在")
    return area


@router.post("", response_model=schemas.ServiceAreaOut, status_code=201)
def create_area(data: schemas.ServiceAreaCreate, db: Session = Depends(get_db)):
    """新建服务区"""
    return crud.create_service_area(db, data)
