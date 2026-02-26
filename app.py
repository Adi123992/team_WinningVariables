"""
app.py
------
Main Flask application for AgriChain Smart Farm-to-Market Advisor.

Routes:
    GET  /        → Home page
    GET  /input   → Farmer input form
    POST /result  → Recommendation results page
"""

from flask import Flask, render_template, request, redirect, url_for
from price_model import get_price_recommendation
from spoilage_model import get_spoilage_risk
from explainability import generate_explanation

app = Flask(__name__)


# ─────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────

@app.route("/")
def home():
    """Home screen with big CTA button."""
    return render_template("home.html")


@app.route("/input")
def input_form():
    """Farmer input form (3 sections)."""
    return render_template("input_form.html")


@app.route("/result", methods=["POST"])
def result():
    """
    Collect form data, run models, render results page.
    Redirects to /input if required fields are missing.
    """
    # ── Collect & validate required fields ──────────────────
    crop_name    = request.form.get("crop_name", "").strip()
    location     = request.form.get("location", "").strip()
    harvest_date = request.form.get("harvest_date", "").strip()
    storage_type = request.form.get("storage_type", "").strip()
    transit_days = request.form.get("transit_days", "2").strip()

    if not all([crop_name, location, harvest_date, storage_type, transit_days]):
        return redirect(url_for("input_form"))

    # ── Parse optional fields ────────────────────────────────
    try:
        transit_days_int = int(transit_days)
    except ValueError:
        transit_days_int = 2

    yield_qty    = request.form.get("yield_qty", "").strip() or None
    soil_nitrogen = request.form.get("soil_nitrogen", "").strip() or None
    soil_moisture = request.form.get("soil_moisture", "Medium")

    # ── Build unified form_data dict ─────────────────────────
    form_data = {
        "crop":          crop_name,
        "location":      location,
        "harvest_date":  harvest_date,
        "yield_qty":     yield_qty,
        "storage_type":  storage_type,
        "transit_days":  transit_days_int,
        "soil_nitrogen": soil_nitrogen,
        "soil_moisture": soil_moisture,
    }

    # ── Run models ───────────────────────────────────────────
    price_data   = get_price_recommendation(form_data)
    spoilage_data = get_spoilage_risk(form_data)
    explanation  = generate_explanation(form_data, price_data, spoilage_data)

    # ── Compose results dict for template ────────────────────
    results = {
        # Meta
        "crop":     crop_name,
        "location": location,

        # Harvest
        "harvest_recommendation": price_data["harvest_recommendation"],
        "harvest_reason":         price_data["harvest_reason"],

        # Market
        "best_mandi":       price_data["best_mandi"],
        "best_price":       price_data["best_price"],
        "estimated_revenue": price_data.get("estimated_revenue"),
        "mandi_comparison":  price_data.get("mandi_comparison", []),

        # Price trend
        "price_trend_text":      price_data["price_trend_text"],
        "price_trend_direction": price_data["price_trend_direction"],

        # Spoilage
        "spoilage_risk_level":   spoilage_data["risk_level"],
        "spoilage_risk_percent": spoilage_data["risk_percent"],
        "spoilage_reason":       spoilage_data["reason"],

        # Tips
        "preservation_tips": spoilage_data["tips"],

        # Explanation
        "explanation": explanation,
    }

    return render_template("result.html", results=results)


# ─────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
