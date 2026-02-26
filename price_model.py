import pandas as pd
from datetime import datetime, timedelta

def predict_price(crop):
    """Simple price prediction - returns base price for crop"""
    # This is a fallback function for basic price prediction
    crop_prices = {
        'soyabean': 5800,
        'wheat': 4500,
        'cotton': 6200,
        'rice': 3200
    }
    return crop_prices.get(crop.lower(), 5000)

def get_market_recommendations(selected_crop):
    """
    Load dataset and analyze market trends for selected crop
    
    Returns:
    - best_mandi: Mandi with highest positive trend
    - latest_price: Latest modal price for best mandi
    - trend_percentage: Trend percentage for best mandi
    - comparison_dict: Dictionary of all mandis with their prices and trends
    """
    try:
        # Load dataset
        df = pd.read_csv('data/mandi_prices.csv')
        
        # Filter by selected crop
        crop_data = df[df['crop'].str.lower() == selected_crop.lower()].copy()
        
        if crop_data.empty:
            # Fallback if no data found
            return get_fallback_recommendations(selected_crop)
        
        # Convert date column to datetime
        crop_data['date'] = pd.to_datetime(crop_data['date'])
        
        # Sort by date
        crop_data = crop_data.sort_values('date')
        
        # Get latest date in dataset
        latest_date = crop_data['date'].max()
        
        # Filter data for last 7 days from latest date
        seven_days_ago = latest_date - timedelta(days=7)
        recent_data = crop_data[crop_data['date'] >= seven_days_ago]
        
        if recent_data.empty:
            # If no recent data, use last available data
            recent_data = crop_data.tail(7)
        
        # Calculate trends for each mandi
        mandi_trends = {}
        
        for mandi in recent_data['mandi'].unique():
            mandi_data = recent_data[recent_data['mandi'] == mandi].sort_values('date')
            
            if len(mandi_data) >= 2:
                # Calculate trend percentage
                first_price = mandi_data.iloc[0]['price']
                last_price = mandi_data.iloc[-1]['price']
                trend_pct = ((last_price - first_price) / first_price) * 100
                latest_price = last_price
            else:
                # If only one data point, no trend
                trend_pct = 0
                latest_price = mandi_data.iloc[0]['price']
            
            mandi_trends[mandi] = {
                'latest_price': latest_price,
                'trend_percentage': round(trend_pct, 2)
            }
        
        if not mandi_trends:
            return get_fallback_recommendations(selected_crop)
        
        # Find best mandi (highest positive trend)
        best_mandi = max(mandi_trends.items(), key=lambda x: x[1]['trend_percentage'])
        
        # Prepare comparison dictionary
        comparison_dict = {}
        for mandi, data in mandi_trends.items():
            comparison_dict[mandi] = {
                'price': data['latest_price'],
                'trend': data['trend_percentage']
            }
        
        return {
            'best_mandi': best_mandi[0],
            'latest_price': best_mandi[1]['latest_price'],
            'trend_percentage': best_mandi[1]['trend_percentage'],
            'comparison_dict': comparison_dict
        }
        
    except Exception as e:
        print(f"Error in market recommendations: {e}")
        return get_fallback_recommendations(selected_crop)

def get_fallback_recommendations(selected_crop):
    """Fallback recommendations when data is not available"""
    fallback_markets = {
        'Nagpur': {'price': 5800, 'trend': 4.0},
        'Pune': {'price': 5400, 'trend': 1.5},
        'Amravati': {'price': 5600, 'trend': 2.8},
        'Mumbai': {'price': 6200, 'trend': 0.5},
        'Nashik': {'price': 5200, 'trend': -1.2}
    }
    
    best_mandi = max(fallback_markets.items(), key=lambda x: x[1]['trend'])
    
    return {
        'best_mandi': best_mandi[0],
        'latest_price': best_mandi[1]['price'],
        'trend_percentage': best_mandi[1]['trend'],
        'comparison_dict': fallback_markets
    }
