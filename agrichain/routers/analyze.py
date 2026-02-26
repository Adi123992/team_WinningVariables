"""
AgriChain — /analyze Router
─────────────────────────────
POST /analyze  →  Full farm-to-market intelligence response.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from models.schemas import AnalyzeRequest, AnalyzeResponse, ErrorResponse
from services import (
    get_weather_forecast,
    get_market_options,
    predict_harvest_window,
    predict_spoilage,
    get_preservation_actions,
    build_explanation,
    build_reasoning_steps,
    build_confidence,
)

logger = logging.getLogger("agrichain.router")
router = APIRouter(prefix="/analyze", tags=["Analysis"])

DATA_SOURCES = [
    "IMD Weather Forecast (7-day mock / OpenWeatherMap)",
    "AGMARKNET Commodity Price Data (commodity_price.csv)",
    "Custom Crops Yield Historical Dataset (crop_yield.csv)",
    "AgriChain Rule-Based ML Models v1.0",
]


@router.post(
    "",
    response_model=AnalyzeResponse,
    summary="Analyse crop and return full farm-to-market recommendations",
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Main endpoint. Accepts farm parameters and returns:
    - Optimal harvest window
    - Ranked market options with net profit
    - Post-harvest spoilage risk
    - Preservation actions (ranked by cost-effectiveness)
    - Plain-language explanations + confidence score
    """
    logger.info(
        "Analyze request: crop=%s, state=%s, district=%s, stage=%s, storage=%s, land=%.1f",
        req.crop_type, req.state, req.district, req.harvest_stage.value,
        req.storage_type.value, req.land_size,
    )

    try:
        # ── 1. Fetch weather ──────────────────────────────────────────────────
        weather = await get_weather_forecast(req.district)

        # ── 2. Harvest window prediction ─────────────────────────────────────
        harvest_window = predict_harvest_window(
            crop=req.crop_type,
            harvest_stage=req.harvest_stage.value,
            weather=weather,
            district=req.district,
        )

        # ── 3. Market options from real price data ────────────────────────────
        markets = get_market_options(
            crop=req.crop_type,
            state=req.state,
            district=req.district,
            land_size=req.land_size,
        )

        if not markets:
            raise ValueError("No market data could be computed for this crop/state combination.")

        best_market = markets[0]

        # ── 4. Spoilage risk ──────────────────────────────────────────────────
        transit_hours = best_market.distance_km / 40.0   # assume avg 40 km/h
        spoilage = predict_spoilage(
            crop=req.crop_type,
            storage_type=req.storage_type.value,
            weather=weather,
            transit_hours=transit_hours,
        )

        # ── 5. Preservation actions ───────────────────────────────────────────
        actions = get_preservation_actions(
            crop=req.crop_type,
            storage_type=req.storage_type.value,
            spoilage_risk=spoilage.risk_pct,
        )

        # ── 6. Explainability ─────────────────────────────────────────────────
        explanation = build_explanation(
            crop=req.crop_type,
            district=req.district,
            weather=weather,
            harvest_window=harvest_window,
            best_market=best_market,
            spoilage=spoilage,
        )

        reasoning_steps = build_reasoning_steps(
            crop=req.crop_type,
            district=req.district,
            weather=weather,
            harvest_window=harvest_window,
            best_market=best_market,
            spoilage=spoilage,
            land_size=req.land_size,
        )

        confidence = build_confidence(
            weather=weather,
            markets=markets,
            crop=req.crop_type,
            district=req.district,
        )

        # ── 7. Assemble response ──────────────────────────────────────────────
        return AnalyzeResponse(
            # KPI card values
            harvest_date_val=harvest_window.display_label,
            harvest_days_val=harvest_window.days_from_today,
            spoilage_val=f"{spoilage.risk_pct}%",
            spoilage_desc_val=spoilage.description,
            profit_val=best_market.net_profit_display,
            profit_desc_val=f"Best market: {best_market.name}",

            # Modules
            weather=weather,
            harvest_window=harvest_window,
            markets=markets,
            spoilage_risk=spoilage,
            preservation_actions=actions,

            # Explainability
            explanation=explanation,
            reasoning_steps=reasoning_steps,
            confidence=confidence,

            # Meta
            data_sources=DATA_SOURCES,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    except ValueError as e:
        logger.warning("Value error in analyze: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Unexpected error in analyze")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )
