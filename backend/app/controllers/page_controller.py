"""Serves the HTML front end (the View) from the same server, so no CORS is needed."""
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from ..config import get_settings

router = APIRouter(include_in_schema=False)

CSP = ("default-src 'self'; "
       "script-src 'self'; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; "
       "img-src 'self' data:; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@router.get("/")
def index():
    page = get_settings().frontend_dir / "index.html"
    if not page.exists():
        return JSONResponse({"detail": "Front end not found. API docs are at /docs."}, status_code=404)
    return FileResponse(page, media_type="text/html", headers={
        "Content-Security-Policy": CSP, "Cache-Control": "no-cache"})


@router.get("/health")
def health():
    return {"status": "ok"}
