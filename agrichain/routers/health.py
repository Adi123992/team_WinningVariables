"""
AgriChain — Health & Info Router
"""

from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
async def health():
    return {
        "status": "ok",
        "service": "AgriChain API",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/", summary="API info")
async def root():
    return {
        "name": "AgriChain — Farm-to-Market Intelligence API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "POST /analyze": "Full farm advisory (harvest + market + spoilage + explanations)",
            "GET  /health":  "Service health check",
        },
        "supported_crops": [
            "tomato", "wheat", "rice", "onion", "potato",
            "soybean", "cotton", "maize", "chickpea",
        ],
        "supported_states": [
            "maharashtra", "punjab", "uttar_pradesh", "madhya_pradesh",
            "rajasthan", "karnataka", "gujarat", "haryana",
            "andhra_pradesh", "telangana", "odisha",
        ],
    }
