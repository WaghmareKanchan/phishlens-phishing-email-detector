from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..ml.registry import registry
from ..schemas import model_info as s
from ..services import model_service

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=s.ModelsOut)
def list_models(db: Session = Depends(get_db)):
    """Metrics of the four models, whether each is trained/loaded, and a notice when the
    numbers are not from a real training run."""
    return model_service.list_models(db, registry)
