def calculate_spoilage(storage, transit):
    if storage == "Open" and transit > 3:
        return "High"
    elif storage == "Warehouse":
        return "Medium"
    else:
        return "Low"
