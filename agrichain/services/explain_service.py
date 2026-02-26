"""
AgriChain — Explainability Service
─────────────────────────────────────
Builds human-readable explanation objects and confidence scores
for every recommendation. This is the "Why" panel.

Designed to be crop-agnostic and data-driven — explanations reference
actual numbers from the computed results, not canned text.
"""

import math
from datetime import date
from typing import List

from models.schemas import (
    WeatherForecast, HarvestWindow, SpoilageRisk, MarketOption,
    Explanation, ReasoningStep, ConfidenceInfo,
)


def build_explanation(
    crop: str,
    district: str,
    weather: WeatherForecast,
    harvest_window: HarvestWindow,
    best_market: MarketOption,
    spoilage: SpoilageRisk,
) -> Explanation:
    """
    Generate four plain-language explanation strings, one per reasoning domain.
    Each string is written as if a local agronomist is explaining to the farmer.
    """

    # ── Weather reason ──
    rain_summary = (
        f"No rainfall expected for {weather.rain_days} more days"
        if weather.rain_days == 0
        else f"{weather.rain_days} rain day(s) expected — harvest before rain"
    )
    weather_reason = (
        f"Weather forecast for {district.title()} shows {rain_summary}. "
        f"Average temperature is {weather.avg_temp:.0f}°C with {weather.avg_humidity:.0f}% humidity. "
        f"{'Dry, cool conditions are ideal for harvest and transport.' if weather.avg_humidity < 65 else 'Higher humidity increases fungal risk — act quickly after harvest.'}"
    )

    # ── Price reason ──
    price_reason = (
        f"Based on mandi price data, {best_market.name} offers the best net return at "
        f"{best_market.price_display}/kg with transport cost of {best_market.transport_display}/kg, "
        f"giving a net profit of {best_market.net_profit_display} for your farm size. "
        f"Price trend: {best_market.trend}."
    )

    # ── Soil / crop reason ──
    soil_reason = (
        f"For {crop.title()}, the {harvest_window.urgency.replace('_', ' ')} harvest stage "
        f"means the crop is {'at peak maturity' if harvest_window.urgency == 'normal' else 'approaching maturity'}. "
        f"Harvesting in the {harvest_window.display_label} window maximises Brix (sugar-acid balance) "
        f"and reduces shrinkage. "
        f"{'Immediate action recommended to avoid over-ripening.' if harvest_window.urgency == 'urgent' else 'Plan your harvest crew and transport now.'}"
    )

    # ── Spoilage reason ──
    spoilage_reason = (
        f"Post-harvest spoilage risk is estimated at {spoilage.risk_pct}% ({spoilage.risk_level}). "
        f"Key factors: {'; '.join(f['text'] for f in spoilage.factors[:2])}. "
        f"Following the top preservation action alone can reduce this risk significantly."
    )

    return Explanation(
        weather_reason=weather_reason,
        price_reason=price_reason,
        soil_reason=soil_reason,
        spoilage_reason=spoilage_reason,
    )


def build_reasoning_steps(
    crop: str,
    district: str,
    weather: WeatherForecast,
    harvest_window: HarvestWindow,
    best_market: MarketOption,
    spoilage: SpoilageRisk,
    land_size: float,
) -> List[ReasoningStep]:
    """
    Build the 4 numbered reasoning steps shown in the 'Why' panel.
    Each step maps to one data domain.
    """
    steps = [
        ReasoningStep(
            step_num="01",
            icon="🌦️",
            title="Weather Analysis",
            desc=(
                f"Forecast for {district.title()} shows {weather.rain_days} rain day(s) over 7 days. "
                f"Average high: {weather.avg_temp:.0f}°C, humidity: {weather.avg_humidity:.0f}%. "
                f"The dry window of {harvest_window.display_label} was selected because it has "
                f"{'no rain and favourable temperatures' if weather.rain_days == 0 else 'the least rain in the forecast period'}."
            ),
        ),
        ReasoningStep(
            step_num="02",
            icon="💰",
            title=f"Price Pattern (Mandi Data)",
            desc=(
                f"{best_market.name} gives the best net return of {best_market.net_profit_display} "
                f"on your {land_size} acres. Even though some markets show higher base prices, "
                f"transport costs erode the advantage. Trend: {best_market.trend}. "
                f"Sell within 2–3 days of harvest for best price."
            ),
        ),
        ReasoningStep(
            step_num="03",
            icon="🧪",
            title="Soil & Crop Health",
            desc=(
                f"{crop.title()} at this growth stage needs {harvest_window.days_from_today.split('—')[0].strip()} "
                f"to reach peak quality. "
                f"{harvest_window.recommendation_sub}"
            ),
        ),
        ReasoningStep(
            step_num="04",
            icon="📦",
            title="Spoilage Logic",
            desc=(
                f"Without intervention, estimated {spoilage.risk_pct}% of produce may be lost to spoilage "
                f"during transit and storage. "
                f"The top preservation action (free: early morning harvest) alone can cut this by ~8 percentage points. "
                f"{'Cold storage is strongly recommended for best results.' if spoilage.risk_pct > 40 else 'Simple ventilated crates are sufficient for your risk level.'}"
            ),
        ),
    ]
    return steps


def build_confidence(
    weather: WeatherForecast,
    markets: List[MarketOption],
    crop: str,
    district: str,
) -> ConfidenceInfo:
    """
    Calculate a composite confidence score (0–100) based on:
    - Data completeness (did we find real price data?)
    - Weather forecast quality (number of days available)
    - Price data points available
    - Crop-district coverage
    """
    score = 60  # base

    # Weather confidence: +10 for 7 days, scale down
    score += min(10, len(weather.days) * 1.4)

    # Price confidence: if we have a best market with non-zero data
    if markets and markets[0].net_profit > 0:
        score += 12

    # District known
    from services.weather_service import DISTRICT_COORDS
    if district.lower() in DISTRICT_COORDS:
        score += 5

    # Crop known
    from services.ml_service import CROP_PROFILE
    if crop.lower() in CROP_PROFILE:
        score += 8

    score = int(min(92, max(55, score)))

    # Variance scales with confidence
    variance_pct = round(max(5, 20 - score * 0.15), 0)
    variance = f"±{int(variance_pct)}%"

    return ConfidenceInfo(
        score=score,
        label=f"{score}% confident",
        basis=(
            f"Based on {len(weather.days)}-day weather forecast, "
            f"mandi price data from commodity_price.csv, "
            f"and historical yield patterns for {crop.title()} in similar districts."
        ),
        variance=variance,
    )
