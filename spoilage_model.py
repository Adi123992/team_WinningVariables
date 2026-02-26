import pandas as pd
from datetime import datetime, timedelta

def get_weather_analysis(location):
    """
    Load weather dataset and analyze for selected location
    
    Returns:
    - rain_expected: Boolean if rainfall > 2mm detected
    - avg_humidity: Average humidity over recent days
    - weather_summary: Risk weather summary string
    """
    try:
        # Load weather dataset
        df = pd.read_csv('data/weather_sample.csv')
        
        # Filter by selected location (partial match)
        location_data = df[df['location'].str.contains(location, case=False, na=False)].copy()
        
        if location_data.empty:
            # Fallback if no location data found
            return get_fallback_weather()
        
        # Convert date column to datetime
        location_data['date'] = pd.to_datetime(location_data['date'], format='%Y')
        
        # Sort by date (descending to get latest)
        location_data = location_data.sort_values('date', ascending=False)
        
        # Take latest 3 records (days)
        recent_data = location_data.head(3)
        
        if recent_data.empty:
            return get_fallback_weather()
        
        # Analyze weather conditions
        rain_detected = (recent_data['rain'] > 2).any()
        avg_humidity = recent_data['humidity'].mean()
        max_temp = recent_data['temperature'].max()
        
        # Generate weather summary
        weather_factors = []
        if rain_detected:
            weather_factors.append("rainfall expected")
        if avg_humidity > 75:
            weather_factors.append("high humidity")
        if max_temp > 35:
            weather_factors.append("high temperature")
        
        if not weather_factors:
            weather_summary = "favorable weather conditions"
        else:
            weather_summary = ", ".join(weather_factors) + " detected"
        
        return {
            'rain_expected': rain_detected,
            'avg_humidity': round(avg_humidity, 1),
            'max_temp': max_temp,
            'weather_summary': weather_summary
        }
        
    except Exception as e:
        print(f"Error in weather analysis: {e}")
        return get_fallback_weather()

def get_fallback_weather():
    """Fallback weather data when actual data is not available"""
    return {
        'rain_expected': True,  # Conservative assumption
        'avg_humidity': 78.5,
        'max_temp': 32,
        'weather_summary': "rainfall expected, high humidity"
    }

def calculate_spoilage(storage, transit, location=None):
    """
    Calculate spoilage risk using specific formula
    
    Base risk:
    - Open = 40
    - Warehouse = 25
    - Cold Storage = 10
    
    Add:
    +10 if humidity > 75
    +10 if rainfall expected
    +5 if transit days > 3
    +5 if temperature > 35
    
    Returns:
    - risk_percentage: Calculated risk percentage
    - risk_category: Low/Medium/High
    - risk_explanation: Detailed explanation
    """
    # Base risk by storage type
    base_risk = {
        'open': 40,
        'warehouse': 25,
        'cold': 10
    }
    
    risk_percentage = base_risk.get(storage, 30)  # Default 30 if unknown
    risk_factors = []
    
    # Weather-related risk factors
    if location:
        weather = get_weather_analysis(location)
        
        if weather['avg_humidity'] > 75:
            risk_percentage += 10
            risk_factors.append(f"high humidity ({weather['avg_humidity']}%)")
        
        if weather['rain_expected']:
            risk_percentage += 10
            risk_factors.append("rainfall expected")
        
        if weather.get('max_temp', 0) > 35:
            risk_percentage += 5
            risk_factors.append("high temperature")
    
    # Transit time risk
    if transit > 3:
        risk_percentage += 5
        risk_factors.append(f"long transit time ({transit} days)")
    
    # Determine risk category
    if risk_percentage < 20:
        risk_category = 'Low'
    elif risk_percentage <= 40:
        risk_category = 'Medium'
    else:
        risk_category = 'High'
    
    # Generate risk explanation
    if not risk_factors:
        risk_explanation = f"Standard risk for {storage} storage"
    else:
        risk_explanation = f"Risk increased due to: {', '.join(risk_factors)}"
    
    # Cap at 95%
    risk_percentage = min(risk_percentage, 95)
    
    return {
        'percentage': risk_percentage,
        'category': risk_category,
        'explanation': risk_explanation,
        'factors': risk_factors
    }
