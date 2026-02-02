def estimate_trip_budget(trip_state):
    """Estimate trip budget based on profile and planned days"""
    profile = trip_state.get("trip_profile", {})
    trip = trip_state.get("trip", {})
    days = trip.get("days", [])
    
    # Get stay days
    stay_days = profile.get("time_days", 1)
    group_size = profile.get("group", {}).get("count", 1)
    comfort = profile.get("comfort", "mid")
    
    # Base daily costs in NPR (Nepalese Rupees)
    accommodation_costs = {
        "budget": 800,
        "mid": 1500, 
        "comfortable": 2500
    }
    
    food_costs = {
        "budget": 800,
        "mid": 1200,
        "comfortable": 2000
    }
    
    transport_costs = {
        "budget": 300,
        "mid": 500,
        "comfortable": 800
    }
    
    # Calculate daily costs
    accommodation = accommodation_costs.get(comfort, 1500)
    food = food_costs.get(comfort, 1200)
    transport = transport_costs.get(comfort, 500)
    
    # Entry fees (estimated per day with 2 places)
    entry_fee_per_day = 500
    
    # Daily total
    daily_total = accommodation + food + transport + entry_fee_per_day
    
    # Trip totals
    total_accommodation = accommodation * stay_days
    total_food = food * stay_days  
    total_transport = transport * stay_days
    total_entry_fees = entry_fee_per_day * stay_days
    
    # Convert to ranges (add 30% variance)
    def add_range(amount):
        low = int(amount * 0.8)
        high = int(amount * 1.3)
        return f"{low:,}–{high:,}"
    
    budget_breakdown = {
        "stay": add_range(total_accommodation),
        "food": add_range(total_food),
        "transport": add_range(total_transport), 
        "entry_fees": add_range(total_entry_fees),
        "total": add_range(total_accommodation + total_food + total_transport + total_entry_fees),
        "currency": "NPR",
        "days": stay_days,
        "group_size": group_size
    }
    
    return budget_breakdown

def format_budget_summary(budget_data):
    """Format budget data into readable summary"""
    lines = [
        f"Here's a realistic {budget_data['days']}-day estimate for {'solo' if budget_data['group_size'] == 1 else f'{budget_data['group_size']} people'}:",
        "",
        f"Stay: {budget_data['currency']} {budget_data['stay']} / night",
        f"Transport: {budget_data['currency']} {budget_data['transport']}", 
        f"Entry fees: {budget_data['currency']} {budget_data['entry_fees']}",
        f"Food: {budget_data['currency']} {budget_data['food']} / day",
        "",
        f"Estimated total: {budget_data['currency']} {budget_data['total']}",
        "",
        "Always a range — prices fluctuate by season and your choices."
    ]
    
    return "\n".join(lines)
