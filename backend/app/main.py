"""Application entry point:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_secret_key, get_settings
from .controllers import (admin_controller, analysis_controller, auth_controller, email_controller,
                          models_controller, page_controller)
from .core.exceptions import AppError
from .database import SessionLocal, init_db
from .ml.registry import registry
from .services import model_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("phishlens")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_secret_key()                       # fail fast in production if SECRET_KEY is missing
    init_db()
    registry.load(settings.artifacts_dir)  # load trained models once
    with SessionLocal() as db:
        model_service.sync_models(db, registry)
    log.info("PhishLens ready. Trained models loaded: %s", registry.loaded_names or "none (rule-based fallback)")
    yield


app = FastAPI(
    title="PhishLens API",
    description="Phishing-email detector. Naive Bayes + Random Forest + LSTM + BERT ensemble.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS is only needed if the front end is hosted on a DIFFERENT origin. Never "*" with credentials.
if settings.cors_origin_list:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


# ---------- error format: {"detail": "...", "code": "...", "errors": {field: message}} ----------
@app.exception_handler(AppError)
async def app_error_handler(_req: Request, exc: AppError):
    return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_handler(_req: Request, exc: RequestValidationError):
    errors = {}
    for e in exc.errors():
        field = str(e["loc"][-1]) if e.get("loc") else "body"
        msg = str(e.get("msg", "Invalid value")).removeprefix("Value error, ")
        errors.setdefault(field, msg)
    first = next(iter(errors.values()), "Invalid input.")
    return JSONResponse({"detail": first, "code": "validation_error", "errors": errors}, status_code=422)


for module in (auth_controller, email_controller, analysis_controller, models_controller, admin_controller):
    app.include_router(module.router)
app.include_router(page_controller.router)

if (settings.frontend_dir / "static").is_dir():
    app.mount("/static", StaticFiles(directory=settings.frontend_dir / "static"), name="static")
