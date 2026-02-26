"""
AgriChain — Price Service
──────────────────────────
Loads the real commodity_price.csv (from data.gov.in / AGMARKNET) and
provides price lookups, market ranking, and trend analysis.

CSV columns:
  State, District, Market, Commodity, Variety, Grade,
  Arrival_Date, Min_x0020_Price, Max_x0020_Price, Modal_x0020_Price
"""

import os
import math
import logging
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from typing import List, Optional

import pandas as pd

from models.schemas import MarketOption

logger = logging.getLogger("agrichain.price")

DATA_PATH = Path(__file__).parent.parent / "data" / "commodity_price.csv"

# Crop name normalisation: frontend name → AGMARKNET commodity substring
CROP_COMMODITY_MAP: dict[str, list[str]] = {
    "tomato":   ["Tomato"],
    "wheat":    ["Wheat"],
    "rice":     ["Paddy", "Rice"],
    "onion":    ["Onion"],
    "potato":   ["Potato"],
    "soybean":  ["Soyabean", "Soybean"],
    "cotton":   ["Cotton"],
    "maize":    ["Maize"],
    "chickpea": ["Bengal Gram", "Chickpea"],
}

# Transport cost (₹/quintal) per distance band — used as fallback
TRANSPORT_RATE_PER_KM = 0.15   # ₹ per kg per 100 km  →  0.15 * dist / 100

# Approximate inter-district distances in km (from district to major mandis)
# Extend this lookup for production; right now it covers demo districts
DISTRICT_MANDI_DISTANCE: dict[str, dict[str, float]] = {
    "nashik":     {"Nashik": 15,   "Pune": 210,  "Mumbai": 170, "Aurangabad": 240},
    "pune":       {"Pune": 10,     "Nashik": 210, "Mumbai": 160, "Solapur": 240},
    "nagpur":     {"Nagpur": 12,   "Amravati": 150, "Wardha": 75},
    "amravati":   {"Amravati": 10, "Nagpur": 150, "Akola": 110},
    "kolhapur":   {"Kolhapur": 8,  "Pune": 230,  "Sangli": 50},
    "aurangabad": {"Aurangabad": 10,"Nashik": 240, "Latur": 200},
    "indore":     {"Indore": 12,   "Bhopal": 195, "Ujjain": 55},
    "bhopal":     {"Bhopal": 10,   "Indore": 195, "Sagar": 180},
    "default":    {"Local APMC": 20, "Nearest City APMC": 100, "District HQ APMC": 60},
}

YIELD_KG_PER_ACRE: dict[str, float] = {
    "tomato":   8000,
    "wheat":    1500,
    "rice":     1800,
    "onion":    10000,
    "potato":   12000,
    "soybean":  900,
    "cotton":   500,
    "maize":    2000,
    "chickpea": 800,
    "default":  2000,
}


@lru_cache(maxsize=1)
def _load_price_df() -> pd.DataFrame:
    """Load and clean the commodity price CSV (cached after first call)."""
    df = pd.read_csv(DATA_PATH)

    # Normalise column names
    df.columns = [c.strip().replace(" ", "_") for c in df.columns]
    df.rename(columns={
        "Min_x0020_Price":   "min_price",
        "Max_x0020_Price":   "max_price",
        "Modal_x0020_Price": "modal_price",
    }, inplace=True)

    # Parse dates
    df["Arrival_Date"] = pd.to_datetime(df["Arrival_Date"], dayfirst=True, errors="coerce")

    # Clean numeric
    for col in ["min_price", "max_price", "modal_price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(subset=["modal_price"], inplace=True)
    df["Commodity_lower"] = df["Commodity"].str.lower().str.strip()
    df["State_lower"]     = df["State"].str.lower().str.strip()

    logger.info("Price dataframe loaded: %d rows", len(df))
    return df


def _commodity_keywords(crop: str) -> List[str]:
    """Return AGMARKNET commodity keywords for a crop name."""
    keywords = CROP_COMMODITY_MAP.get(crop.lower(), [crop.title()])
    return [k.lower() for k in keywords]


def _filter_by_crop(df: pd.DataFrame, crop: str) -> pd.DataFrame:
    """Filter dataframe rows matching the given crop."""
    keywords = _commodity_keywords(crop)
    mask = df["Commodity_lower"].str.contains("|".join(keywords), regex=True, na=False)
    return df[mask]


def _get_transport_cost(district: str, market: str, price_per_kg: float) -> float:
    """
    Compute transport cost per kg.
    Uses lookup table → falls back to distance-based estimate.
    """
    dist_map = DISTRICT_MANDI_DISTANCE.get(
        district.lower(), DISTRICT_MANDI_DISTANCE["default"]
    )
    # Try to match market name against lookup
    for mandi_key, km in dist_map.items():
        if mandi_key.lower() in market.lower() or market.lower() in mandi_key.lower():
            return round(TRANSPORT_RATE_PER_KM * km / 100, 2)
    # Fallback: use median distance
    km = sorted(dist_map.values())[len(dist_map) // 2]
    return round(TRANSPORT_RATE_PER_KM * km / 100, 2)


def _price_trend(df_crop: pd.DataFrame, market: str) -> str:
    """Compute a simple price trend string for the given market."""
    sub = df_crop[df_crop["Market"].str.lower().str.contains(market.lower()[:6], na=False)]
    if len(sub) < 2:
        return "Insufficient data for trend"
    sub = sub.sort_values("Arrival_Date")
    recent = sub.tail(5)["modal_price"].mean()
    older  = sub.head(max(1, len(sub) - 5))["modal_price"].mean()
    if older == 0:
        return "Stable"
    change_pct = ((recent - older) / older) * 100
    sign = "+" if change_pct > 0 else ""
    return f"{sign}{change_pct:.1f}% recent trend"


def get_market_options(
    crop: str,
    state: str,
    district: str,
    land_size: float,
) -> List[MarketOption]:
    """
    Build ranked MarketOption list from real price data.
    Falls back to mock data if the dataset has no matching rows.
    """
    df = _load_price_df()
    df_crop = _filter_by_crop(df, crop)

    yield_kg = land_size * YIELD_KG_PER_ACRE.get(crop.lower(), YIELD_KG_PER_ACRE["default"])

    # Try to filter by state
    state_clean = state.lower().replace("_", " ")
    df_state = df_crop[df_crop["State_lower"].str.contains(state_clean[:6], na=False)]

    # If no rows for this state, use all available rows
    working_df = df_state if len(df_state) >= 2 else df_crop

    options: List[MarketOption] = []

    if len(working_df) == 0:
        logger.warning("No price data found for crop=%s — using fallback mock", crop)
        return _mock_market_options(crop, district, land_size, yield_kg)

    # Group by market, take average modal price
    mkt_agg = (
        working_df.groupby("Market")["modal_price"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "avg_price", "count": "data_points"})
    )

    # Keep top 5 by price for selection
    mkt_agg = mkt_agg.nlargest(5, "avg_price").reset_index(drop=True)

    for _, row in mkt_agg.iterrows():
        market_name   = row["Market"]
        price_per_kg  = round(row["avg_price"] / 100, 2)   # CSV is in ₹/quintal; convert to ₹/kg
        if price_per_kg < 0.5:
            price_per_kg = round(row["avg_price"], 2)        # already per kg

        transport = _get_transport_cost(district, market_name, price_per_kg)
        net_per_kg = max(0.0, price_per_kg - transport)
        net_profit = round(net_per_kg * yield_kg, 0)
        trend_str  = _price_trend(df_crop, market_name)

        options.append({
            "market": market_name,
            "price_per_kg": price_per_kg,
            "transport": transport,
            "net_profit": net_profit,
            "trend": trend_str,
        })

    # Sort by net profit desc
    options.sort(key=lambda x: x["net_profit"], reverse=True)

    if not options:
        return _mock_market_options(crop, district, land_size, yield_kg)

    best_profit = options[0]["net_profit"] if options[0]["net_profit"] > 0 else 1

    result: List[MarketOption] = []
    for i, o in enumerate(options[:3]):
        bar_w = int(min(100, (o["net_profit"] / best_profit) * 80 + 20)) if best_profit > 0 else 40
        is_best = (i == 0)
        profit_color = "var(--leaf)" if is_best else ("var(--warn)" if i == 1 else "var(--muted)")
        dist_map = DISTRICT_MANDI_DISTANCE.get(district.lower(), DISTRICT_MANDI_DISTANCE["default"])
        dist_km  = dist_map.get(o["market"], 80.0)

        result.append(MarketOption(
            name=o["market"],
            is_best=is_best,
            price_per_kg=o["price_per_kg"],
            price_display=f"₹{o['price_per_kg']:.1f}",
            transport_cost=o["transport"],
            transport_display=f"₹{o['transport']:.1f}",
            net_profit=o["net_profit"],
            net_profit_display=f"₹{int(o['net_profit']):,}",
            bar_width=bar_w,
            profit_color=profit_color,
            distance_km=dist_km,
            trend=o["trend"],
        ))
    return result


def _mock_market_options(crop: str, district: str, land_size: float, yield_kg: float) -> List[MarketOption]:
    """
    Deterministic fallback mock when CSV has no matching rows.
    Prices are derived from known Indian mandi benchmarks per crop.
    """
    MOCK_BASE_PRICES: dict[str, list] = {
        "tomato":   [("Nashik APMC", 28.5, 2.1), ("Pune APMC", 31.0, 5.8),   ("Aurangabad APMC", 24.0, 3.2)],
        "wheat":    [("Indore APMC", 21.5, 1.2), ("Bhopal APMC", 20.8, 0.95),("Local Dealer", 19.8, 0.0)],
        "rice":     [("Nagpur APMC", 22.0, 1.8), ("Amravati APMC", 20.5, 1.2),("Wardha APMC", 19.0, 0.8)],
        "onion":    [("Lasalgaon APMC", 18.5, 1.8), ("Nashik APMC", 16.0, 2.1), ("Mumbai Vashi", 20.0, 6.5)],
        "potato":   [("Agra APMC", 14.0, 2.0),  ("Kanpur APMC", 13.5, 1.6),  ("Local Market", 11.0, 0.3)],
        "soybean":  [("Indore APMC", 42.0, 1.5), ("Bhopal APMC", 41.5, 1.2), ("Dewas APMC", 40.0, 0.8)],
        "cotton":   [("Akola APMC", 65.0, 1.8),  ("Amravati APMC", 63.0, 1.5), ("Nagpur APMC", 61.0, 2.2)],
        "maize":    [("Davangere APMC", 18.0, 1.4), ("Hubli APMC", 17.5, 1.8), ("Dharwad APMC", 17.0, 1.2)],
        "default":  [("Local APMC", 20.0, 1.5),  ("District APMC", 19.0, 1.2), ("City Market", 18.0, 2.0)],
    }

    entries = MOCK_BASE_PRICES.get(crop.lower(), MOCK_BASE_PRICES["default"])
    result = []
    best_profit = None

    for i, (mkt, price, transport) in enumerate(entries):
        net_per_kg = price - transport
        net_profit = round(net_per_kg * yield_kg, 0)
        if best_profit is None:
            best_profit = net_profit
        bar_w = int(min(100, (net_profit / best_profit) * 80 + 20))
        profit_color = "var(--leaf)" if i == 0 else ("var(--warn)" if i == 1 else "var(--muted)")

        result.append(MarketOption(
            name=mkt,
            is_best=(i == 0),
            price_per_kg=price,
            price_display=f"₹{price}",
            transport_cost=transport,
            transport_display=f"₹{transport}",
            net_profit=net_profit,
            net_profit_display=f"₹{int(net_profit):,}",
            bar_width=bar_w,
            profit_color=profit_color,
            distance_km=transport / TRANSPORT_RATE_PER_KM * 100,
            trend="Seasonal demand rising" if i == 0 else "Stable",
        ))
    return result
