"""
Deal Analyzer - Financial analysis for potential flip properties
"""

import logging
from typing import Dict, Any
import numpy as np
from config import settings
from models.property import Property

logger = logging.getLogger(__name__)

def estimate_repairs(property_data: Property) -> float:
    """
    Estimate repair costs based on property characteristics.
    This is a simplified model and should be calibrated with actual project data.
    """
    base_sqft_cost = settings.REPAIR_COSTS['base_sqft_cost']
    
    # Age factors
    if property_data.age is None:
        age_factor = 1.0
    elif property_data.age > 50:
        age_factor = 1.5
    elif property_data.age > 30:
        age_factor = 1.3
    elif property_data.age > 15:
        age_factor = 1.1
    else:
        age_factor = 1.0
    
    # Condition factor (based on keywords in the description)
    condition_factor = 1.0
    high_repair_keywords = ['fixer', 'needs work', 'tlc', 'handyman', 'distressed']
    moderate_repair_keywords = ['dated', 'original', 'renovate', 'update']
    
    for keyword in high_repair_keywords:
        if keyword in property_data.opportunity_keywords:
            condition_factor = 1.5
            break
    
    if condition_factor == 1.0:
        for keyword in moderate_repair_keywords:
            if keyword in property_data.opportunity_keywords:
                condition_factor = 1.25
                break
    
    # Calculate the base repair estimate
    repair_estimate = property_data.square_feet * base_sqft_cost * age_factor * condition_factor
    
    # Add bathroom and kitchen renovation costs if property is older
    if property_data.age and property_data.age > 20:
        repair_estimate += settings.REPAIR_COSTS['kitchen'] * min(1, int(property_data.square_feet / 1500))
        repair_estimate += settings.REPAIR_COSTS['bathroom'] * min(property_data.bathrooms, 2)
    
    # Add a contingency
    repair_estimate *= 1.1  # 10% contingency
    
    logger.info(f"Repair estimate for {property_data.address}: ${repair_estimate:,.2f}")
    return repair_estimate

def calculate_closing_costs(purchase_price: float, sale_price: float) -> Dict[str, float]:
    """Calculate estimated closing costs for purchase and sale"""
    # Purchase closing costs
    purchase_closing = purchase_price * settings.CLOSING_COSTS['purchase_percentage']
    
    # Sale closing costs
    agent_commission = sale_price * settings.CLOSING_COSTS['agent_commission']
    seller_closing = sale_price * settings.CLOSING_COSTS['seller_closing_percentage']
    
    return {
        'purchase_closing': purchase_closing,
        'agent_commission': agent_commission,
        'seller_closing': seller_closing,
        'total': purchase_closing + agent_commission + seller_closing
    }

def calculate_holding_costs(purchase_price: float, months: float) -> float:
    """Calculate holding costs during renovation and sale"""
    monthly_costs = {
        'mortgage': (purchase_price * settings.HOLDING_COSTS['mortgage_rate'] / 12),
        'taxes': (purchase_price * settings.HOLDING_COSTS['property_tax_rate'] / 12),
        'insurance': (purchase_price * settings.HOLDING_COSTS['insurance_rate'] / 12),
        'utilities': settings.HOLDING_COSTS['monthly_utilities']
    }
    
    total_monthly = sum(monthly_costs.values())
    return total_monthly * months

def analyze_deal(property_data: Property, arv: float, repair_costs: float, min_roi: float = 20.0) -> Dict[str, Any]:
    """
    Analyze a potential flip deal and determine if it meets criteria
    Returns a dictionary with analysis results
    """
    # Store values in property object
    property_data.estimated_repair_cost = repair_costs
    property_data.estimated_arv = arv
    
    # Calculate closing costs
    closing_costs = calculate_closing_costs(property_data.list_price, arv)
    
    # Calculate holding costs (assuming 4 months for renovation and sale)
    holding_period = settings.AVERAGE_FLIP_MONTHS
    holding_costs = calculate_holding_costs(property_data.list_price, holding_period)
    
    # Calculate total project costs
    total_project_cost = property_data.list_price + repair_costs + closing_costs['total'] + holding_costs
    
    # Calculate potential profit
    potential_profit = arv - total_project_cost
    property_data.estimated_profit = potential_profit
    
    # Calculate ROI
    roi = (potential_profit / total_project_cost) * 100
    property_data.estimated_roi = roi
    
    # Check if deal meets minimum ROI criteria
    meets_criteria = roi >= min_roi
    
    # Apply the 70% rule check
    max_purchase_price = 0.7 * arv - repair_costs
    meets_70_percent_rule = property_data.list_price <= max_purchase_price
    
    # Create deal object
    deal = {
        'property_id': property_data.mls_id,
        'address': property_data.get_full_address(),
        'list_price': property_data.list_price,
        'arv': arv,
        'repair_costs': repair_costs,
        'closing_costs': closing_costs['total'],
        'holding_costs': holding_costs,
        'total_project_cost': total_project_cost,
        'potential_profit': potential_profit,
        'roi': roi,
        'meets_criteria': meets_criteria,
        'meets_70_percent_rule': meets_70_percent_rule,
        'max_purchase_price': max_purchase_price,
        'property_data': property_data.to_dict()
    }
    
    logger.info(f"Deal analysis for {property_data.address}: ROI={roi:.2f}%, Profit=${potential_profit:,.2f}")
    
    return deal

def calculate_arv(property_data: Property) -> float:
    """Calculate After Repair Value based on comps"""
    if not property_data.comps:
        logger.warning(f"No comparable properties found for {property_data.address}")
        # Fallback: assume a certain percentage increase over list price
        return property_data.list_price * 1.5
    
    # Extract price per square foot from comps
    comp_psf = [comp['price'] / comp['square_feet'] for comp in property_data.comps 
                if comp.get('square_feet', 0) > 0]
    
    if not comp_psf:
        return property_data.list_price * 1.5
    
    # Remove outliers (more than 2 standard deviations from mean)
    mean_psf = np.mean(comp_psf)
    std_psf = np.std(comp_psf)
    filtered_psf = [psf for psf in comp_psf if abs(psf - mean_psf) <= 2 * std_psf]
    
    if filtered_psf:
        avg_psf = np.mean(filtered_psf)
    else:
        avg_psf = mean_psf
    
    # Calculate ARV based on average price per square foot
    arv = property_data.square_feet * avg_psf
    
    logger.info(f"Calculated ARV for {property_data.address}: ${arv:,.2f}")
    return arv
    