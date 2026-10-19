from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import analysis as s
from ..services import analysis_service

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=s.AnalyzeOut)
def analyze(payload: s.AnalyzeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_service.analyze_single(db, user, payload)


@router.post("/analyze/batch", response_model=s.BatchOut)
async def analyze_batch(file: UploadFile = File(...), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    raw = await file.read()            # no file-size limit
    return analysis_service.analyze_batch(db, user, raw)


@router.get("/history", response_model=list[s.HistoryItemOut])
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_service.history(db, user)


@router.delete("/history", status_code=204)
def clear_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    analysis_service.clear_history(db, user)
    return Response(status_code=204)
