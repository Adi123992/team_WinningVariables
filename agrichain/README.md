# 🌾 AgriChain — Farm-to-Market Intelligence Platform

AI-powered advisory for Indian farmers: optimal harvest timing, best mandi to sell at, 
post-harvest spoilage risk, and plain-language explanations — all from a single API call.

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone / unzip the project
cd agrichain

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the API
uvicorn main:app --reload --port 8000

# 4. Open the frontend
open frontend.html          # macOS
# or just double-click frontend.html in your file explorer

# 5. API docs
open http://localhost:8000/docs
```

---

## 📁 Project Structure

```
agrichain/
├── main.py                        ← FastAPI app + CORS + lifespan
├── requirements.txt
├── .env.example                   ← Copy to .env for config
├── frontend.html                  ← Complete frontend (calls /analyze)
│
├── models/
│   └── schemas.py                 ← All Pydantic request/response models
│
├── routers/
│   ├── analyze.py                 ← POST /analyze (main endpoint)
│   └── health.py                  ← GET /health, GET /
│
├── services/
│   ├── weather_service.py         ← Mock weather + OpenWeatherMap hook
│   ├── price_service.py           ← Real CSV price data + market ranking
│   ├── ml_service.py              ← ML placeholder models (harvest/spoilage/price)
│   └── explain_service.py         ← Explainability + confidence scoring
│
└── data/
    ├── commodity_price.csv        ← AGMARKNET mandi price data (2,700+ rows)
    └── crop_yield.csv             ← Historical crop yield dataset (50,000+ rows)
```

---

## 📡 API Reference

### POST /analyze

```json
// Request
{
  "crop_type":     "tomato",
  "state":         "maharashtra",
  "district":      "nashik",
  "harvest_stage": "15days",     // 15days | 7days | ready | overdue
  "storage_type":  "none",       // none | warehouse | cold | home
  "land_size":     2.5           // acres
}

// Response (abbreviated)
{
  "harvest_date_val":  "Mar 8–11",
  "harvest_days_val":  "In 10–13 days — optimal window",
  "spoilage_val":      "34%",
  "profit_val":        "₹18,400",

  "harvest_window": {
    "display_label": "Mar 8–11",
    "recommendation": "Harvest between Mar 8–11",
    "recommendation_sub": "...",
    "factors": [{"type": "good", "text": "No rainfall forecast..."}]
  },

  "markets": [
    {"name": "Nashik APMC", "is_best": true, "price_display": "₹28.5",
     "net_profit_display": "₹18,400", "trend": "+12% recent trend", ...}
  ],

  "spoilage_risk": {
    "risk_pct": 34, "risk_level": "Medium", "description": "...",
    "gauge_offset": 157.6, "factors": [...]
  },

  "preservation_actions": [
    {"rank": 1, "title": "Harvest early morning", "cost_display": "FREE", "effectiveness": 4}
  ],

  "explanation": {
    "weather_reason": "...",
    "price_reason":   "...",
    "soil_reason":    "...",
    "spoilage_reason": "..."
  },

  "reasoning_steps": [{"step_num": "01", "icon": "🌦️", "title": "Weather Analysis", "desc": "..."}],

  "confidence": {"score": 82, "label": "82% confident", "variance": "±8%"}
}
```

---

## 🧠 ML Placeholder Functions

Each function in `services/ml_service.py` is designed for drop-in real model replacement:

| Function | Current | Replace With |
|---|---|---|
| `predict_harvest_window()` | Rule-based (crop maturity + weather) | GradientBoosting / LightGBM on crop_yield.csv |
| `predict_price()` | Seasonal multiplier | Prophet / LSTM on commodity_price.csv |
| `predict_spoilage()` | Logistic additive risk | Random Forest on post-harvest survey data |

---

## 🌤️ Real Weather API

To enable live weather from OpenWeatherMap:

```bash
# In .env
USE_REAL_WEATHER=true
OWM_API_KEY=your_key_here
```

The `_fetch_openweather()` stub in `services/weather_service.py` shows exactly where to wire it.

---

## 🌐 Supported Crops & States

**Crops:** tomato, wheat, rice, onion, potato, soybean, cotton, maize, chickpea

**States:** maharashtra, punjab, uttar_pradesh, madhya_pradesh, rajasthan, 
           karnataka, gujarat, haryana, andhra_pradesh, telangana, odisha

---

## 📊 Data Sources

- `commodity_price.csv` — AGMARKNET (National Agriculture Market) mandi price data
- `crop_yield.csv` — Historical crop yield with soil/weather parameters
- Weather — IMD mock (7-day deterministic simulation) or OpenWeatherMap

---

## 🏗️ Scaling Roadmap

1. **Real ML models** — train on crop_yield.csv using scikit-learn / LightGBM
2. **Live weather** — swap in OWM API key
3. **More mandis** — extend `DISTRICT_MANDI_DISTANCE` dict
4. **Hindi NLP** — translate `explanation` object via IndicTrans2
5. **Database** — replace CSV with PostgreSQL + TimescaleDB for price time series
6. **Auth** — add farmer profiles (phone number → JWT) for personalisation
