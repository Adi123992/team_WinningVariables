from flask import Flask, render_template, request
from price_model import predict_price
from spoilage_model import calculate_spoilage
from explainability import generate_explanation
import random

app = Flask(__name__)

def get_market_recommendations(crop, location):
    """Generate market recommendations based on crop and location"""
    markets = {
        'Nagpur': {'base_price': 5800, 'trend': 'increasing'},
        'Pune': {'base_price': 5400, 'trend': 'stable'},
        'Amravati': {'base_price': 5600, 'trend': 'increasing'},
        'Mumbai': {'base_price': 6200, 'trend': 'stable'},
        'Nashik': {'base_price': 5200, 'trend': 'decreasing'}
    }
    
    # Select best market (simplified logic)
    best_market = max(markets.items(), key=lambda x: x[1]['base_price'])
    return best_market[0], best_market[1]['base_price'], markets

def generate_harvest_recommendation(crop, harvest_date, location):
    """Generate harvest timing recommendation"""
    recommendations = [
        "Harvest within 2 days.",
        "Harvest within 5 days.",
        "Harvest within 1 week.",
        "Harvest now for best prices."
    ]
    
    reasons = [
        "Rainfall is expected in 3 days and current mandi prices are increasing.",
        "Market prices are at their peak this week.",
        "Weather conditions are optimal for harvesting.",
        "Demand is high in nearby markets."
    ]
    
    return random.choice(recommendations), random.choice(reasons)

def generate_price_trend():
    """Generate price trend information"""
    trends = [
        "Price is likely to increase by 4% in next 5 days.",
        "Price is expected to remain stable for the next week.",
        "Price may decrease by 2% in the next 3 days.",
        "Price is likely to increase by 6% in the next week."
    ]
    return random.choice(trends)

def generate_preservation_suggestions(storage, transit):
    """Generate preservation suggestions"""
    suggestions = []
    
    if storage != 'cold':
        suggestions.append("Use cold storage – reduces risk by 40%")
    
    if transit > 2:
        suggestions.append("Reduce transit time to 2 days – reduces risk by 15%")
    
    suggestions.append("Improve ventilation in storage")
    suggestions.append("Monitor humidity levels regularly")
    
    return suggestions[:3]  # Return max 3 suggestions

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/input')
def input_form():
    return render_template('input_form.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    # Get form data - basic crop information
    crop = request.form['crop']
    location = request.form['location']
    harvest_date = request.form.get('harvest_date', '')
    estimated_yield = request.form.get('yield', '')
    
    # Get new form fields
    storage_type = request.form.get('storage_type', 'open')
    transit_time = request.form.get('transit_time', '3')
    soil_nitrogen = request.form.get('soil_nitrogen', '')
    soil_moisture = request.form.get('soil_moisture', '')
    
    # Generate basic recommendations
    price = predict_price(crop)
    
    # Use actual storage and transit values from form
    storage = storage_type
    try:
        transit = int(transit_time) if transit_time else 3
    except:
        transit = 3
    
    spoilage = calculate_spoilage(storage, transit)
    explanation = generate_explanation(crop, price, spoilage)
    
    # Get market recommendations
    best_mandi, expected_price, all_markets = get_market_recommendations(crop, location)
    
    # Generate comparison text
    comparison_items = []
    for market, data in all_markets.items():
        if market != best_mandi:
            comparison_items.append(f"{market}: ₹{data['base_price']}")
    comparison = " | ".join(comparison_items)
    
    # Calculate estimated revenue
    try:
        yield_qty = float(estimated_yield) if estimated_yield else 50  # Default 50 quintals
    except:
        yield_qty = 50
    estimated_revenue = expected_price * yield_qty
    
    # Generate harvest recommendation
    harvest_recommendation, harvest_reason = generate_harvest_recommendation(crop, harvest_date, location)
    
    # Generate price trend
    price_trend = generate_price_trend()
    
    # Determine risk level for styling
    if spoilage < 30:
        risk_level = 'low'
        spoilage_text = f"Low ({spoilage}%)"
    elif spoilage < 60:
        risk_level = 'medium'
        spoilage_text = f"Medium ({spoilage}%)"
    else:
        risk_level = 'high'
        spoilage_text = f"High ({spoilage}%)"
    
    # Generate spoilage reason
    spoilage_reasons = [
        "High humidity and open storage increase risk after 3 days.",
        "Current weather conditions favor spoilage.",
        "Transit time is longer than recommended.",
        "Storage conditions need improvement."
    ]
    spoilage_reason = random.choice(spoilage_reasons)
    
    # Generate preservation suggestions
    preservation_suggestions = generate_preservation_suggestions(storage, transit)
    
    return render_template('result.html',
                           harvest_recommendation=harvest_recommendation,
                           harvest_reason=harvest_reason,
                           best_mandi=best_mandi,
                           expected_price=expected_price,
                           estimated_revenue=estimated_revenue,
                           comparison=comparison,
                           price_trend=price_trend,
                           spoilage_risk=spoilage_text,
                           risk_level=risk_level,
                           spoilage_reason=spoilage_reason,
                           preservation_suggestions=preservation_suggestions,
                           explanation=explanation)

if __name__ == '__main__':
    app.run(debug=True)
