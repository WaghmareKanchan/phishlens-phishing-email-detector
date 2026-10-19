from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.deps import require_admin
from ..database import get_db
from ..ml.registry import registry
from ..models import User
from ..schemas import admin as s
from ..services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=s.AdminStatsOut)
def stats(db: Session = Depends(get_db), _a: User = Depends(require_admin)):
    return admin_service.stats(db)


@router.get("/users", response_model=list[s.AdminUserOut])
def users(db: Session = Depends(get_db), _a: User = Depends(require_admin)):
    return admin_service.users(db)


@router.get("/activity", response_model=list[s.AdminActivityOut])
def activity(db: Session = Depends(get_db), _a: User = Depends(require_admin)):
    return admin_service.activity(db)


@router.post("/models/reload", response_model=s.ReloadOut)
def reload_models(db: Session = Depends(get_db), _a: User = Depends(require_admin)):
    return admin_service.reload_models(db, registry)
