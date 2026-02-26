"""
AgriChain — Pydantic Models
All request/response shapes are defined here.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum


# ─── ENUMS ───────────────────────────────────────────────────────────────────

class HarvestStage(str, Enum):
    FIFTEEN_DAYS = "15days"
    SEVEN_DAYS   = "7days"
    READY        = "ready"
    OVERDUE      = "overdue"


class StorageType(str, Enum):
    NONE      = "none"
    WAREHOUSE = "warehouse"
    COLD      = "cold"
    HOME      = "home"


# ─── REQUEST ─────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    crop_type:      str            = Field(..., example="tomato",       description="Crop name (lowercase)")
    state:          str            = Field(..., example="maharashtra",   description="Indian state (lowercase_underscore)")
    district:       str            = Field(..., example="nashik",        description="District / mandi area")
    harvest_stage:  HarvestStage   = Field(..., example="15days",        description="How close to harvest")
    storage_type:   StorageType    = Field(..., example="none",          description="Available storage facility")
    land_size:      float          = Field(..., gt=0, le=1000, example=2.5, description="Farm size in acres")

    @validator("crop_type", "state", "district", pre=True)
    def lowercase_strip(cls, v):
        return v.strip().lower()


# ─── SUB-MODELS ──────────────────────────────────────────────────────────────

class WeatherDay(BaseModel):
    date:        str
    temp_max_c:  float
    temp_min_c:  float
    humidity_pct: float
    rainfall_mm: float
    condition:   str   # "sunny" | "cloudy" | "rain"


class WeatherForecast(BaseModel):
    location:     str
    days:         List[WeatherDay]
    avg_temp:     float
    avg_humidity: float
    rain_days:    int


class HarvestWindow(BaseModel):
    start_date:       str    = Field(..., description="ISO date string YYYY-MM-DD")
    end_date:         str
    display_label:    str    = Field(..., example="Mar 8–11")
    days_from_today:  str    = Field(..., example="In 10–13 days — optimal window")
    recommendation:   str    = Field(..., description="One plain-language sentence")
    recommendation_sub: str  = Field(..., description="2-3 sentence detail explanation")
    urgency:          str    = Field(..., example="normal")   # "urgent" | "normal" | "plan_ahead"
    factors: List[dict]      = Field(..., description="List of {type, text} factor explanations")


class MarketOption(BaseModel):
    name:          str
    is_best:       bool
    price_per_kg:  float
    price_display: str    = Field(..., example="₹28.5")
    transport_cost: float
    transport_display: str
    net_profit:    float
    net_profit_display: str
    bar_width:     int    = Field(..., ge=0, le=100, description="Relative bar width 0-100 for UI")
    profit_color:  str    = Field(..., example="var(--leaf)")
    distance_km:   float
    trend:         str    = Field(..., example="+12% in 10 days")


class SpoilageRisk(BaseModel):
    risk_pct:       int    = Field(..., ge=0, le=100)
    risk_level:     str    = Field(..., example="Medium")   # Low | Medium | High
    risk_color:     str    = Field(..., example="var(--warn)")
    description:    str
    factors:        List[dict]
    gauge_offset:   float  = Field(..., description="SVG stroke-dashoffset for 90px-r38 circle (circumference 238.76)")


class PreservationAction(BaseModel):
    rank:           int
    rank_class:     str    = Field(..., example="r1")
    title:          str
    detail:         str
    cost_display:   str    = Field(..., example="FREE")
    cost_value:     float  = Field(..., description="Numeric lower bound in INR (0 = free)")
    effectiveness:  int    = Field(..., ge=1, le=5, description="1-5 star rating")
    spoilage_after: Optional[int] = Field(None, description="Residual spoilage % after this action")


class Explanation(BaseModel):
    weather_reason:  str
    price_reason:    str
    soil_reason:     str
    spoilage_reason: str


class ReasoningStep(BaseModel):
    step_num:  str   = Field(..., example="01")
    icon:      str   = Field(..., example="🌦️")
    title:     str
    desc:      str


class ConfidenceInfo(BaseModel):
    score:        int    = Field(..., ge=0, le=100)
    label:        str    = Field(..., example="82% confident")
    basis:        str    = Field(..., description="Plain-language basis for confidence")
    variance:     str    = Field(..., example="±8%")


# ─── RESPONSE ────────────────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    # Summary (top KPI cards)
    harvest_date_val:   str   = Field(..., example="Mar 8–11")
    harvest_days_val:   str   = Field(..., example="In 10–13 days — optimal window")
    spoilage_val:       str   = Field(..., example="34%")
    spoilage_desc_val:  str
    profit_val:         str   = Field(..., example="₹18,400")
    profit_desc_val:    str

    # Detailed modules
    weather:            WeatherForecast
    harvest_window:     HarvestWindow
    markets:            List[MarketOption]
    spoilage_risk:      SpoilageRisk
    preservation_actions: List[PreservationAction]

    # Explainability
    explanation:        Explanation
    reasoning_steps:    List[ReasoningStep]
    confidence:         ConfidenceInfo

    # Meta
    data_sources:       List[str]
    generated_at:       str


class ErrorResponse(BaseModel):
    error:   str
    detail:  Optional[str] = None
    code:    int
