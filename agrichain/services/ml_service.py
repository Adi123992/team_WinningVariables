"""
AgriChain — ML Prediction Service
────────────────────────────────────
Contains three ML placeholder functions designed for drop-in real model integration.

Current implementation:
  - predict_harvest_window() → rule-based logic using crop maturity + weather
  - predict_price()          → weighted moving average on CSV price data
  - predict_spoilage()       → logistic-style risk model using storage + weather params

Each function is annotated with exactly what a real ML model would replace.
"""

import math
import logging
from datetime import date, timedelta
from typing import Optional

from models.schemas import (
    WeatherForecast, HarvestWindow, SpoilageRisk, PreservationAction
)

logger = logging.getLogger("agrichain.ml")

# ─── CROP KNOWLEDGE BASE ──────────────────────────────────────────────────────

CROP_PROFILE: dict[str, dict] = {
    "tomato": {
        "maturity_days":       {"15days": 15, "7days": 7, "ready": 0, "overdue": -3},
        "ideal_temp_range":    (18, 28),
        "humidity_tolerance":  65,           # % max for good storage
        "ideal_soil_moisture": 60,
        "harvest_window_days": 4,
        "perishability":       "high",       # high | medium | low
        "delay_penalty_days":  4,            # days after which quality degrades fast
        "curing_days":         0,
    },
    "wheat": {
        "maturity_days":       {"15days": 35, "7days": 28, "ready": 0, "overdue": -5},
        "ideal_temp_range":    (15, 25),
        "humidity_tolerance":  14,           # grain moisture % threshold
        "ideal_soil_moisture": 40,
        "harvest_window_days": 5,
        "perishability":       "low",
        "delay_penalty_days":  7,
        "curing_days":         0,
    },
    "rice": {
        "maturity_days":       {"15days": 20, "7days": 10, "ready": 0, "overdue": -5},
        "ideal_temp_range":    (20, 32),
        "humidity_tolerance":  75,
        "ideal_soil_moisture": 70,
        "harvest_window_days": 5,
        "perishability":       "low",
        "delay_penalty_days":  6,
        "curing_days":         2,
    },
    "onion": {
        "maturity_days":       {"15days": 10, "7days": 5, "ready": 0, "overdue": -4},
        "ideal_temp_range":    (20, 30),
        "humidity_tolerance":  60,
        "ideal_soil_moisture": 50,
        "harvest_window_days": 5,
        "perishability":       "medium",
        "delay_penalty_days":  6,
        "curing_days":         10,
    },
    "potato": {
        "maturity_days":       {"15days": 15, "7days": 8, "ready": 0, "overdue": -3},
        "ideal_temp_range":    (15, 22),
        "humidity_tolerance":  70,
        "ideal_soil_moisture": 55,
        "harvest_window_days": 6,
        "perishability":       "medium",
        "delay_penalty_days":  5,
        "curing_days":         3,
    },
    "soybean": {
        "maturity_days":       {"15days": 20, "7days": 12, "ready": 0, "overdue": -5},
        "ideal_temp_range":    (20, 30),
        "humidity_tolerance":  50,
        "ideal_soil_moisture": 45,
        "harvest_window_days": 5,
        "perishability":       "low",
        "delay_penalty_days":  8,
        "curing_days":         0,
    },
    "cotton": {
        "maturity_days":       {"15days": 20, "7days": 10, "ready": 0, "overdue": -7},
        "ideal_temp_range":    (25, 35),
        "humidity_tolerance":  55,
        "ideal_soil_moisture": 40,
        "harvest_window_days": 7,
        "perishability":       "low",
        "delay_penalty_days":  10,
        "curing_days":         0,
    },
    "maize": {
        "maturity_days":       {"15days": 18, "7days": 9, "ready": 0, "overdue": -4},
        "ideal_temp_range":    (18, 30),
        "humidity_tolerance":  60,
        "ideal_soil_moisture": 55,
        "harvest_window_days": 5,
        "perishability":       "medium",
        "delay_penalty_days":  5,
        "curing_days":         2,
    },
}

STORAGE_SPOILAGE_FACTOR: dict[str, float] = {
    "cold":      0.4,   # cold storage halves base risk
    "warehouse": 0.7,
    "home":      1.0,
    "none":      1.3,   # worse than baseline
}

PERISHABILITY_BASE_RISK: dict[str, int] = {
    "high":   35,
    "medium": 20,
    "low":    10,
}

SPOILAGE_CIRCUMFERENCE = 238.76   # 2π × 38 (SVG circle r=38)


# ─── HARVEST WINDOW PREDICTION ───────────────────────────────────────────────

def predict_harvest_window(
    crop: str,
    harvest_stage: str,
    weather: WeatherForecast,
    district: str,
) -> HarvestWindow:
    """
    Predict the optimal harvest window for a given crop + weather.

    ── Current implementation ──
    Rule-based: crop maturity days + dry-weather window search.

    ── To replace with ML ──
    A trained GradientBoostingRegressor (or LightGBM) using features:
      - crop, district, month, soil_moisture, N/P/K, GDD (growing degree days)
      - 7-day temp/humidity forecast array
    Target: days_to_optimal_harvest (integer)
    Training data: crop_yield.csv + historical mandi data
    """
    profile   = CROP_PROFILE.get(crop.lower(), CROP_PROFILE.get("tomato"))
    days_left = profile["maturity_days"].get(harvest_stage, 7)
    today     = date.today()

    # Find best consecutive dry-weather window in the 7-day forecast
    best_window_start = today + timedelta(days=max(0, days_left))
    best_score = -999.0

    for start_offset in range(max(0, days_left - 2), min(days_left + 5, 6)):
        window_days = weather.days[start_offset: start_offset + profile["harvest_window_days"]]
        if not window_days:
            continue

        rain_penalty = sum(d.rainfall_mm for d in window_days) * 2
        temp_penalty = sum(
            max(0, d.temp_max_c - profile["ideal_temp_range"][1])
            for d in window_days
        ) * 3
        hum_penalty = sum(
            max(0, d.humidity_pct - profile["humidity_tolerance"])
            for d in window_days
        ) * 0.5
        score = 100 - rain_penalty - temp_penalty - hum_penalty

        if score > best_score:
            best_score = score
            best_window_start = today + timedelta(days=start_offset)

    window_end   = best_window_start + timedelta(days=profile["harvest_window_days"] - 1)
    days_to_start = (best_window_start - today).days
    days_to_end   = (window_end - today).days

    # Build urgency
    if days_to_start <= 3:
        urgency = "urgent"
    elif days_to_start <= 10:
        urgency = "normal"
    else:
        urgency = "plan_ahead"

    # Human-readable label
    def fmt(d: date) -> str:
        return d.strftime("%b") + " " + str(d.day)

    display_label = f"{fmt(best_window_start)}–{fmt(window_end)}"

    if urgency == "urgent":
        days_display = f"In {days_to_start}–{days_to_end} days — act soon!"
    elif urgency == "normal":
        days_display = f"In {days_to_start}–{days_to_end} days — optimal window"
    else:
        days_display = f"In {days_to_start}–{days_to_end} days — plan ahead"

    # Build weather factor explanations
    rain_days_in_window = sum(
        1 for d in weather.days[max(0, days_to_start): days_to_end + 1]
        if d.rainfall_mm > 0
    )
    avg_max_in_window = (
        sum(d.temp_max_c for d in weather.days[max(0, days_to_start): days_to_end + 1])
        / max(1, days_to_end - days_to_start + 1)
    )

    factors = []
    if rain_days_in_window == 0:
        factors.append({"type": "good", "text": f"No rainfall forecast for {display_label}"})
    else:
        factors.append({"type": "warn", "text": f"{rain_days_in_window} rain day(s) expected — monitor closely"})

    if avg_max_in_window <= profile["ideal_temp_range"][1]:
        factors.append({"type": "good", "text": f"Avg max temp {avg_max_in_window:.0f}°C — within ideal range"})
    else:
        factors.append({"type": "warn", "text": f"High temps {avg_max_in_window:.0f}°C — harvest early in the day"})

    if weather.avg_humidity <= profile["humidity_tolerance"]:
        factors.append({"type": "good", "text": f"Humidity at {weather.avg_humidity:.0f}% — favourable for harvest"})
    else:
        factors.append({"type": "warn", "text": f"High humidity {weather.avg_humidity:.0f}% — increases fungal risk"})

    delay_date = window_end + timedelta(days=profile["delay_penalty_days"])
    factors.append({
        "type": "bad",
        "text": f"Delaying past {fmt(delay_date)} risks 15–20% yield quality loss",
    })

    recommendation = f"Harvest between {display_label}"
    recommendation_sub = (
        f"This {profile['harvest_window_days']}-day window offers the best combination of "
        f"dry weather, favourable temperatures, and peak mandi demand. "
        f"{'Waiting beyond ' + fmt(delay_date) + ' risks quality loss and price drop.' if urgency != 'plan_ahead' else 'Mark your calendar and prepare equipment.'}"
    )

    return HarvestWindow(
        start_date=best_window_start.isoformat(),
        end_date=window_end.isoformat(),
        display_label=display_label,
        days_from_today=days_display,
        recommendation=recommendation,
        recommendation_sub=recommendation_sub,
        urgency=urgency,
        factors=factors,
    )


# ─── PRICE PREDICTION ────────────────────────────────────────────────────────

def predict_price(
    crop: str,
    market: str,
    current_price: float,
    harvest_days: int,
) -> float:
    """
    Predict price at a future harvest date for a given market.

    ── Current implementation ──
    Applies a simple seasonal multiplier based on crop + month + harvest lag.

    ── To replace with ML ──
    A time-series model (Prophet / LSTM) trained on:
      - commodity_price.csv (modal price by market + date)
      - Seasonal dummy variables, festival calendar, supply surplus indicators
    Target: modal_price at date T+harvest_days
    """
    from datetime import date as _date
    target_month = (_date.today() + timedelta(days=harvest_days)).month

    SEASONAL_MULTIPLIERS: dict[str, dict[int, float]] = {
        "tomato": {1: 1.1, 2: 1.0, 3: 1.15, 4: 0.90, 5: 0.85, 6: 0.95,
                   7: 1.05, 8: 1.0,  9: 0.95, 10: 1.0, 11: 1.1, 12: 1.2},
        "onion":  {1: 1.2, 2: 1.0, 3: 0.90, 4: 0.85, 5: 1.10, 6: 1.40,
                   7: 1.50, 8: 1.3, 9: 1.20, 10: 1.1, 11: 1.0, 12: 1.1},
        "wheat":  {1: 0.9, 2: 0.9, 3: 0.95, 4: 1.05, 5: 1.10, 6: 1.05,
                   7: 1.0, 8: 1.0,  9: 1.00, 10: 1.0, 11: 1.0, 12: 0.95},
    }

    multipliers = SEASONAL_MULTIPLIERS.get(crop.lower(), {m: 1.0 for m in range(1, 13)})
    multiplier  = multipliers.get(target_month, 1.0)
    return round(current_price * multiplier, 2)


# ─── SPOILAGE PREDICTION ─────────────────────────────────────────────────────

def predict_spoilage(
    crop: str,
    storage_type: str,
    weather: WeatherForecast,
    transit_hours: float = 4.0,
) -> SpoilageRisk:
    """
    Predict spoilage risk (0–100%) given storage and weather conditions.

    ── Current implementation ──
    Logistic-style additive risk model:
      base_risk (perishability) × storage_factor + temperature_penalty + humidity_penalty

    ── To replace with ML ──
    A Random Forest Classifier trained on:
      - Crop type, storage type, transit time, avg temperature, humidity
      - Historical spoilage observations from post-harvest loss surveys
    Target: spoilage_probability (float 0–1)
    """
    profile   = CROP_PROFILE.get(crop.lower(), CROP_PROFILE.get("tomato"))
    base_risk = PERISHABILITY_BASE_RISK[profile["perishability"]]

    storage_factor = STORAGE_SPOILAGE_FACTOR.get(storage_type.lower(), 1.0)

    # Temperature penalty: > 30°C adds risk for perishables
    temp_penalty = 0.0
    if profile["perishability"] in ("high", "medium"):
        excess_heat = max(0, weather.avg_temp - 30)
        temp_penalty = excess_heat * 1.5

    # Humidity penalty
    hum_penalty = max(0, weather.avg_humidity - profile["humidity_tolerance"]) * 0.3

    # Transit penalty
    transit_penalty = max(0, (transit_hours - 3) * 2) if profile["perishability"] == "high" else 0

    raw_risk = base_risk * storage_factor + temp_penalty + hum_penalty + transit_penalty
    risk_pct = int(min(95, max(5, round(raw_risk))))

    # Level thresholds
    if risk_pct < 20:
        level = "Low";    color = "var(--success)"
    elif risk_pct < 45:
        level = "Medium"; color = "var(--warn)"
    else:
        level = "High";   color = "var(--rust)"

    # SVG gauge: stroke-dashoffset for a 238.76-circumference circle
    fill_ratio   = risk_pct / 100.0
    gauge_offset = round(SPOILAGE_CIRCUMFERENCE * (1 - fill_ratio), 2)

    # Factor explanations
    factors = []
    if storage_type == "none":
        factors.append({"type": "warn", "text": f"No cold storage: +{int(base_risk*(storage_factor-0.7))}% spoilage risk"})
    elif storage_type == "cold":
        factors.append({"type": "good", "text": "Cold storage significantly reduces spoilage risk"})
    else:
        factors.append({"type": "warn", "text": f"{storage_type.title()} storage: moderate risk — ventilate well"})

    if transit_penalty > 0:
        factors.append({"type": "warn", "text": f"Transit time {transit_hours:.0f}+ hrs in afternoon heat: +{int(transit_penalty)}% risk"})
    else:
        factors.append({"type": "good", "text": "Short transit time keeps spoilage low"})

    if weather.rain_days == 0:
        factors.append({"type": "good", "text": "Dry harvest conditions reduce fungal risk"})
    else:
        factors.append({"type": "bad", "text": f"{weather.rain_days} rain days forecast — harvest carefully to avoid moisture damage"})

    descriptions = {
        "Low":    f"Low risk ({risk_pct}%) — standard care during transit is sufficient.",
        "Medium": f"Medium risk ({risk_pct}%) — take preservation actions to protect your harvest.",
        "High":   f"High risk ({risk_pct}%) — urgent action required before and during transit.",
    }

    return SpoilageRisk(
        risk_pct=risk_pct,
        risk_level=level,
        risk_color=color,
        description=descriptions[level],
        factors=factors,
        gauge_offset=gauge_offset,
    )


# ─── PRESERVATION ACTIONS ────────────────────────────────────────────────────

def get_preservation_actions(
    crop: str,
    storage_type: str,
    spoilage_risk: int,
) -> list[PreservationAction]:
    """
    Return ranked preservation actions based on cost-effectiveness.
    Actions are ranked: highest effectiveness ÷ cost first.
    """

    ALL_ACTIONS: dict[str, list[dict]] = {
        "high_perishability": [
            {
                "title":   "Harvest in early morning (5–8 AM)",
                "detail":  "Cooler temps reduce field heat by 8–10°C. Zero cost, high impact.",
                "cost":    0,
                "cost_display": "FREE",
                "effectiveness": 4,
                "spoilage_reduction": 8,
            },
            {
                "title":   "Use ventilated crates (not gunny bags)",
                "detail":  "Reduces moisture buildup by 40%. Prevents crush damage.",
                "cost":    1000,
                "cost_display": "₹800–1,200",
                "effectiveness": 4,
                "spoilage_reduction": 12,
            },
            {
                "title":   "Pre-cooling at nearest cold store (4 hrs)",
                "detail":  "Drops core temperature before transit. Best for >5 hr journeys.",
                "cost":    2750,
                "cost_display": "₹2,500–3,000",
                "effectiveness": 5,
                "spoilage_reduction": 20,
            },
            {
                "title":   "Apply wax coating (tomato/onion/potato)",
                "detail":  "Reduces water loss and extends shelf life by 2–3 days.",
                "cost":    1500,
                "cost_display": "₹1,200–1,800",
                "effectiveness": 3,
                "spoilage_reduction": 10,
            },
        ],
        "low_perishability": [
            {
                "title":   "Dry grain to <14% moisture before storage",
                "detail":  "Prevents mould and insect infestation in storage.",
                "cost":    0,
                "cost_display": "FREE",
                "effectiveness": 5,
                "spoilage_reduction": 15,
            },
            {
                "title":   "Use HDPE / moisture-proof bags",
                "detail":  "Prevents re-absorption of humidity during transit.",
                "cost":    500,
                "cost_display": "₹400–600",
                "effectiveness": 4,
                "spoilage_reduction": 10,
            },
            {
                "title":   "Store away from direct sunlight & moisture",
                "detail":  "Simple warehouse discipline prevents 8–10% loss.",
                "cost":    0,
                "cost_display": "FREE",
                "effectiveness": 3,
                "spoilage_reduction": 8,
            },
        ],
        "medium_perishability": [
            {
                "title":   "Cure produce before storage (7–10 days in shade)",
                "detail":  "Heals surface wounds and hardens skin. Critical for onion/potato.",
                "cost":    0,
                "cost_display": "FREE",
                "effectiveness": 5,
                "spoilage_reduction": 18,
            },
            {
                "title":   "Use ventilated storage with airflow",
                "detail":  "Reduces internal temperature and ethylene buildup.",
                "cost":    800,
                "cost_display": "₹600–1,000",
                "effectiveness": 4,
                "spoilage_reduction": 12,
            },
            {
                "title":   "Sort & grade before packing",
                "detail":  "Remove damaged items to prevent spread of rot.",
                "cost":    0,
                "cost_display": "FREE",
                "effectiveness": 3,
                "spoilage_reduction": 8,
            },
        ],
    }

    profile     = CROP_PROFILE.get(crop.lower(), CROP_PROFILE.get("tomato"))
    perishability = profile["perishability"]

    if perishability == "high":
        pool = ALL_ACTIONS["high_perishability"]
    elif perishability == "low":
        pool = ALL_ACTIONS["low_perishability"]
    else:
        pool = ALL_ACTIONS["medium_perishability"]

    # Sort by effectiveness / (cost+1)  → free high-impact actions rank first
    pool_sorted = sorted(
        pool,
        key=lambda a: a["effectiveness"] * 10 / (a["cost"] + 1),
        reverse=True,
    )

    rank_classes = ["r1", "r2", "r3"]
    result = []
    running_spoilage = spoilage_risk

    for i, action in enumerate(pool_sorted[:3]):
        running_spoilage = max(5, running_spoilage - action["spoilage_reduction"])
        result.append(PreservationAction(
            rank=i + 1,
            rank_class=rank_classes[i],
            title=action["title"],
            detail=action["detail"],
            cost_display=action["cost_display"],
            cost_value=float(action["cost"]),
            effectiveness=action["effectiveness"],
            spoilage_after=running_spoilage,
        ))
    return result
