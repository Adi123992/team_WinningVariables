def generate_explanation(crop, price, spoilage):
    return f"The selected mandi shows strong price trend for {crop}. Current storage condition results in {spoilage} spoilage risk."

def generate_dynamic_explanation(price_trend, spoilage_risk, rain_forecast, supply_status):
    """
    Generate dynamic explanation using real data
    
    Args:
    - price_trend: Price trend percentage
    - spoilage_risk: Risk level (Low/Medium/High)
    - rain_forecast: Boolean if rain expected
    - supply_status: Number of markets (supply indicator)
    """
    
    # Price trend explanation
    if price_trend > 3:
        price_msg = "Prices are rising fast in markets"
    elif price_trend > 0:
        price_msg = "Prices are slowly going up"
    elif price_trend < -3:
        price_msg = "Prices are falling quickly"
    else:
        price_msg = "Prices are steady now"
    
    # Spoilage risk explanation
    if spoilage_risk == "High":
        risk_msg = "be careful with storage"
    elif spoilage_risk == "Medium":
        risk_msg = "watch your crops closely"
    else:
        risk_msg = "storage conditions are good"
    
    # Weather explanation
    if rain_forecast:
        weather_msg = "Rain may damage crops"
    else:
        weather_msg = "Weather looks fine"
    
    # Supply explanation
    if supply_status > 4:
        supply_msg = "many markets available"
    else:
        supply_msg = "limited market options"
    
    # Combine into simple explanation
    explanations = [
        f"{price_msg}, so {risk_msg}. {weather_msg} and {supply_status} {supply_msg}.",
        f"{weather_msg} and {price_msg}. {risk_msg} with {supply_msg}.",
        f"{price_msg} but {weather_msg}. {risk_msg} for your crops."
    ]
    
    # Return shortest, simplest explanation
    return f"{price_msg}. {weather_msg}. {risk_msg}."
