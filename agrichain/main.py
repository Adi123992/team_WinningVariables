"""
AgriChain — FastAPI Application
─────────────────────────────────
Entry point. Run with:
    uvicorn main:app --reload --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import analyze_router, health_router

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("agrichain")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AgriChain API starting up...")
    # Pre-load the price dataframe once at startup to avoid first-request lag
    try:
        from services.price_service import _load_price_df
        df = _load_price_df()
        logger.info("Price dataset loaded: %d rows", len(df))
    except Exception as e:
        logger.warning("Could not pre-load price data: %s", e)
    yield
    logger.info("AgriChain API shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AgriChain — Farm-to-Market Intelligence API",
    description=(
        "AI-powered advisory for Indian farmers. "
        "Returns optimal harvest window, best mandi to sell at, "
        "post-harvest spoilage risk, and plain-language explanations."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tighten to specific frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc), "code": 500},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(analyze_router)


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
