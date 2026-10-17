"""Sequel Support HR desk. The Python engines are the figures of record."""

import logging
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.routers.hr import router as hr_router

settings = get_settings()
logger = logging.getLogger("hr.http")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )


configure_logging(settings.log_level)

app = FastAPI(title=settings.project_name, version=settings.version)
origins = settings.origin_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - started) * 1000
        logger.info("METHOD=%s PATH=%s STATUS=%s DURATION_MS=%.2f", request.method, request.url.path, 500, elapsed)
        raise
    elapsed = (time.perf_counter() - started) * 1000
    logger.info(
        "METHOD=%s PATH=%s STATUS=%s DURATION_MS=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content={"status": "ERROR", "detail": detail})


@app.exception_handler(RequestValidationError)
async def invalid_body(_request: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for item in exc.errors():
        loc = ".".join(str(bit) for bit in item.get("loc", []) if bit != "body")
        parts.append(f"{loc}: {item.get('msg')}" if loc else item.get("msg", "Invalid input"))
    detail = "; ".join(parts) or "Invalid input"
    return JSONResponse(status_code=400, content={"status": "ERROR", "detail": detail})


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc.__class__.__name__)
    return JSONResponse(status_code=500, content={"status": "ERROR", "detail": "Internal Server Error"})


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "project": settings.project_name,
        "version": settings.version,
        "environment": settings.environment,
    }


app.include_router(hr_router)

if (ROOT / "static").is_dir():
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
if (ROOT / "photos").is_dir():
    app.mount("/photos", StaticFiles(directory=ROOT / "photos"), name="photos")


@app.get("/")
def desk_page() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/sw.js")
def service_worker() -> FileResponse:
    return FileResponse(ROOT / "sw.js", media_type="application/javascript")
