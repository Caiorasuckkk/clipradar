from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.api.analytics_api import router as analytics_router
from app.api.ops_api import router as ops_router
from app.api.posts_api import router as posts_router
from app.api.review_api import router as review_router
from app.api.generation_api import router as generation_router


app = FastAPI(title="ClipRadar Local API", version="0.5.21")


@app.middleware("http")
async def _require_api_token(request: Request, call_next):
    """When API_AUTH_TOKEN is set, reject requests that don't present it (header
    `X-API-Token` or `?token=`). Keeps a public tunnel/cloud URL from being abused.
    No-op when the token is unset (local dev). Media URLs can pass the token via
    the query param so video/audio playback keeps working."""
    token = config.API_AUTH_TOKEN
    if token and request.method != "OPTIONS" and request.url.path != "/":
        sent = request.headers.get("x-api-token") or request.query_params.get("token")
        if sent != token:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_origin_regex=r"http://(127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(review_router)
app.include_router(ops_router)
app.include_router(posts_router)
app.include_router(generation_router)
app.include_router(analytics_router)


@app.on_event("startup")
def _startup() -> None:
    # Start the SQLite-backed background job worker (render/voice/script jobs).
    from app.services import job_queue_service

    job_queue_service.bootstrap()


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "ClipRadar Local API", "version": "0.5.21"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
