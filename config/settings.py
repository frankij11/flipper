"""
Configuration Settings for Real Estate Flip Finder
"""

# Search Parameters
MAX_DAYS_ON_MARKET = 90
PROPERTY_TYPES = ['Residential', 'Condo/Co-Op', 'Townhouse']

# Opportunity Keywords
OPPORTUNITY_KEYWORDS = [
    'as-is', 'fixer', 'needs work', 'handyman', 'tlc', 'potential', 'opportunity',
    'estate sale', 'foreclosure', 'bank owned', 'reo', 'short sale', 'distressed',
    'investor', 'renovation', 'remodel', 'restore', 'flip', 'under market', 'bargain',
    'motivated', 'must sell', 'bring offer', 'priced to sell', 'reduced'
]

# Analysis Constants
REPAIR_COSTS = {
    'base_sqft_cost': 20,  # Base cost per square foot for repairs
    'kitchen': 15000,      # Average kitchen renovation
    'bathroom': 7500,      # Average bathroom renovation
    'roof': 10000,         # Roof replacement
    'hvac': 8000,          # HVAC replacement
    'foundation': 15000,   # Foundation repairs
    'electrical': 8000,    # Electrical updates
    'plumbing': 7000       # Plumbing updates
}

CLOSING_COSTS = {
    'purchase_percentage': 0.03,    # 3% of purchase price
    'seller_closing_percentage': 0.02,  # 2% of sale price
    'agent_commission': 0.06        # 6% of sale price
}

HOLDING_COSTS = {
    'mortgage_rate': 0.07,      # 7% annual rate
    'property_tax_rate': 0.015, # 1.5% annual rate
    'insurance_rate': 0.005,    # 0.5% annual rate
    'monthly_utilities': 200    # $200 per month
}

AVERAGE_FLIP_MONTHS = 4  # Average months to buy, renovate, and sell

# Scoring System
SCORING = {
    'profit_weight': 40,             # 40% importance on profit
    'roi_weight': 30,                # 30% importance on ROI
    'repair_cost_weight': 15,        # 15% importance on repair costs (lower is better)
    'dom_weight': 10,                # 10% importance on days on market
    'opportunity_keywords_weight': 5, # 5% importance on opportunity keywords
    'meets_70_rule_weight': 5        # 5% bonus for meeting 70% rule
}

# Output Settings
EXCEL_FORMATTING = {
    'header_color': 'CCCCCC',
    'good_roi_color': '90EE90',
    'medium_roi_color': 'FFFFE0',
    'low_roi_color': 'FFC0CB'
}

# Default minimum ROI to consider a deal viable
DEFAULT_MIN_ROI = 20.0
