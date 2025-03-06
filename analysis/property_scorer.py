"""
Property Scorer - Score and rank potential flip properties
"""

import logging
from typing import List, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

def score_deals(deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Score and rank potential flip deals based on multiple factors
    Returns the deals list with added scores, sorted from best to worst
    """
    if not deals:
        logger.warning("No deals to score")
        return []
    
    scored_deals = []
    
    # Collect ranges for normalization
    profit_values = [deal['potential_profit'] for deal in deals]
    roi_values = [deal['roi'] for deal in deals]
    repair_values = [deal['repair_costs'] for deal in deals]
    dom_values = [deal['property_data']['days_on_market'] for deal in deals]
    
    # Find min/max for normalization
    max_profit = max(profit_values) if profit_values else 0
    min_profit = min(profit_values) if profit_values else 0
    max_roi = max(roi_values) if roi_values else 0
    min_roi = min(roi_values) if roi_values else 0
    max_repair = max(repair_values) if repair_values else 0
    min_repair = min(repair_values) if repair_values else 0
    max_dom = max(dom_values) if dom_values else 0
    min_dom = min(dom_values) if dom_values else 0
    
    # Prevent division by zero
    profit_range = max_profit - min_profit
    roi_range = max_roi - min_roi
    repair_range = max_repair - min_repair
    dom_range = max_dom - min_dom
    
    # Score each deal
    for deal in deals:
        # Start with base score
        score = 0
        
        # Profit score (0-40 points)
        if profit_range > 0:
            profit_score = settings.SCORING['profit_weight'] * (deal['potential_profit'] - min_profit) / profit_range
            score += profit_score
        
        # ROI score (0-30 points)
        if roi_range > 0:
            roi_score = settings.SCORING['roi_weight'] * (deal['roi'] - min_roi) / roi_range
            score += roi_score
        
        # Repair cost score (0-15 points, lower repair costs get higher scores)
        if repair_range > 0:
            repair_score = settings.SCORING['repair_cost_weight'] * (1 - (deal['repair_costs'] - min_repair) / repair_range)
            score += repair_score
        
        # Days on market score (0-10 points, higher DOM gets higher scores as they may be more negotiable)
        if dom_range > 0:
            dom_score = settings.SCORING['dom_weight'] * (deal['property_data']['days_on_market'] - min_dom) / dom_range
            score += dom_score
        
        # Bonus points for special opportunities
        opportunity_keywords = deal['property_data'].get('opportunity_keywords', [])
        if opportunity_keywords:
            # Add 1 point per keyword, up to 5 points
            score += min(settings.SCORING['opportunity_keywords_weight'], len(opportunity_keywords))
        
        # Bonus for meeting the 70% rule
        if deal['meets_70_percent_rule']:
            score += settings.SCORING['meets_70_rule_weight']
        
        # Add score to deal
        deal['score'] = score
        scored_deals.append(deal)
    
    # Sort deals by score (descending)
    scored_deals.sort(key=lambda x: x['score'], reverse=True)
    
    logger.info(f"Scored {len(scored_deals)} deals. Top score: {scored_deals[0]['score']:.2f}" if scored_deals else "No deals to score")
    
    return scored_deals
