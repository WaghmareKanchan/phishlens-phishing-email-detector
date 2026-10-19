from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import email as s
from ..services import email_service

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("", response_model=list[s.EmailOut])
def list_emails(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return email_service.list_emails(db, user)


@router.post("", response_model=s.EmailOut, status_code=201)
def save_email(payload: s.EmailIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return email_service.create_email(db, user, payload)


@router.post("/bulk", response_model=s.BulkEmailsOut, status_code=201)
def save_many(payload: s.BulkEmailsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return s.BulkEmailsOut(saved=email_service.bulk_create(db, user, payload.emails))


@router.put("/{email_id}", response_model=s.EmailOut)
def update_email(email_id: str, payload: s.EmailIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return email_service.update_email(db, user, email_id, payload)


@router.delete("/{email_id}", status_code=204)
def delete_email(email_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    email_service.delete_email(db, user, email_id)
    return Response(status_code=204)
