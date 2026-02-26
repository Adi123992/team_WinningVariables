from flask import Flask, render_template, request
from price_model import predict_price, get_market_recommendations
from spoilage_model import calculate_spoilage
from explainability import generate_dynamic_explanation
import random

app = Flask(__name__)

def harvest_decision(crop, harvest_date, location, weather_data, market_data):
    """Generate harvest decision based on weather and market conditions"""
    
    # Weather-based urgency
    if weather_data['rain_expected']:
        recommendation = "Harvest within 2 days"
        reason = "Rain is coming soon - protect your crop"
    elif weather_data['avg_humidity'] > 75:
        recommendation = "Harvest within 3 days"
        reason = "High humidity can damage crops in storage"
    else:
        recommendation = "Harvest within 5 days"
        reason = "Weather is good for harvesting"
    
    # Market consideration
    if market_data['trend_percentage'] > 2:
        reason += " and prices are rising"
    elif market_data['trend_percentage'] < -2:
        reason += " but prices are falling"
    
    return {
        'recommendation': recommendation,
        'reason': reason
    }

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
    # Get form data
    crop = request.form['crop']
    location = request.form['location']
    harvest_date = request.form.get('harvest_date', '')
    estimated_yield = request.form.get('yield', '')
    storage_type = request.form.get('storage_type', 'open')
    transit_time = request.form.get('transit_time', '3')
    
    # 1. Call price_model functions
    market_data = get_market_recommendations(crop)
    best_mandi = market_data['best_mandi']
    expected_price = market_data['latest_price']
    trend_percentage = market_data['trend_percentage']
    all_markets = market_data['comparison_dict']
    
    # 2. Call weather analysis function
    from spoilage_model import get_weather_analysis
    weather_data = get_weather_analysis(location)
    
    # 3. Call harvest_decision
    harvest_advice = harvest_decision(crop, harvest_date, location, weather_data, market_data)
    
    # 4. Call spoilage risk calculator
    spoilage_result = calculate_spoilage(storage_type, int(transit_time), location)
    
    # Generate comparison text
    comparison_items = []
    for market, data in all_markets.items():
        if market != best_mandi:
            comparison_items.append(f"{market}: ₹{data['price']}")
    comparison = " | ".join(comparison_items)
    
    # Calculate estimated revenue
    try:
        yield_qty = float(estimated_yield) if estimated_yield else 50
    except:
        yield_qty = 50
    estimated_revenue = expected_price * yield_qty
    
    # Generate preservation suggestions
    preservation_suggestions = generate_preservation_suggestions(storage_type, int(transit_time))
    
    # Generate dynamic explanation
    explanation = generate_dynamic_explanation(
        trend_percentage, 
        spoilage_result['category'], 
        weather_data['rain_expected'],
        len(all_markets)  # Supply indicator (number of markets)
    )
    
    return render_template('result.html',
                           harvest_recommendation=harvest_advice['recommendation'],
                           harvest_reason=harvest_advice['reason'],
                           best_mandi=best_mandi,
                           expected_price=expected_price,
                           estimated_revenue=estimated_revenue,
                           comparison=comparison,
                           price_trend=f"Price {'increasing' if trend_percentage > 0 else 'decreasing'} by {abs(trend_percentage)}% in next 5 days",
                           spoilage_risk=f"{spoilage_result['category']} ({spoilage_result['percentage']}%)",
                           risk_level=spoilage_result['category'].lower(),
                           spoilage_reason=spoilage_result['explanation'],
                           preservation_suggestions=preservation_suggestions,
                           explanation=explanation)

if __name__ == '__main__':
    app.run(debug=True)
