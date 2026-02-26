def calculate_spoilage(storage, transit):
    if storage == "open" and transit > 3:
        return 65  # High risk percentage
    elif storage == "warehouse":
        return 35  # Medium risk percentage
    elif storage == "cold":
        return 15  # Low risk percentage
    else:
        return 45  # Default medium risk
