"""
Repair Estimator - Estimate renovation costs
"""

import logging
from typing import Dict, List, Any
from models.property import Property

logger = logging.getLogger(__name__)

# Standard renovation costs per square foot
COST_LEVELS = {
    'cosmetic': 15,       # Paint, flooring, minor repairs
    'moderate': 30,       # Some updating of kitchens/baths, some systems
    'extensive': 60,      # Major renovations, kitchen/bath remodels
    'complete': 100       # Complete gut and rebuild interior
}

# Additional costs for specific items
ITEM_COSTS = {
    'roof': {
        'repair': 2500,
        'replace': 10000
    },
    'hvac': {
        'repair': 1500,
        'replace': 8000
    },
    'kitchen': {
        'cosmetic': 5000,
        'moderate': 15000,
        'high_end': 30000
    },
    'bathroom': {
        'cosmetic': 2500,
        'moderate': 7500,
        'high_end': 15000
    },
    'windows': {
        'per_window': 500
    },
    'foundation': {
        'minor': 5000,
        'major': 20000
    },
    'electrical': {
        'update': 5000,
        'rewire': 15000
    },
    'plumbing': {
        'update': 5000,
        'replace': 15000
    }
}

def estimate_renovation_level(property_data: Property) -> str:
    """
    Estimate the level of renovation needed based on property characteristics
    
    Args:
        property_data: Property object with details
        
    Returns:
        Renovation level: 'cosmetic', 'moderate', 'extensive', or 'complete'
    """
    # Start with assumption based on age
    if property_data.age is None:
        base_level = 'moderate'
    elif property_data.age > 50:
        base_level = 'extensive'
    elif property_data.age > 30:
        base_level = 'moderate'
    elif property_data.age > 15:
        base_level = 'cosmetic'
    else:
        base_level = 'cosmetic'
    
    # Adjust based on keywords in description and opportunity keywords
    description = property_data.description.lower()
    keywords = property_data.opportunity_keywords
    
    # Check for keywords indicating more extensive work
    extensive_indicators = [
        'fixer', 'needs work', 'tlc', 'handyman special', 'distressed',
        'as-is', 'potential', 'opportunity', 'needs renovation'
    ]
    
    moderate_indicators = [
        'dated', 'original', 'some updating', 'could use', 'older'
    ]
    
    # Check for keywords indicating specific issues
    has_roof_issues = any(k in description for k in ['roof', 'leak'])
    has_hvac_issues = any(k in description for k in ['hvac', 'heat', 'cooling'])
    has_foundation_issues = any(k in description for k in ['foundation', 'structural'])
    has_electrical_issues = any(k in description for k in ['electrical', 'wiring'])
    has_plumbing_issues = any(k in description for k in ['plumbing', 'pipes'])
    
    # Count serious issues
    serious_issues = sum([
        has_roof_issues, has_hvac_issues, has_foundation_issues,
        has_electrical_issues, has_plumbing_issues
    ])
    
    # Count extensive and moderate indicators
    extensive_count = sum(1 for k in extensive_indicators if any(k in kw for kw in keywords) or k in description)
    moderate_count = sum(1 for k in moderate_indicators if any(k in kw for kw in keywords) or k in description)
    
    # Determine final renovation level
    if extensive_count >= 2 or serious_issues >= 2:
        return 'extensive'
    elif extensive_count >= 1 or moderate_count >= 2 or serious_issues >= 1:
        return 'moderate'
    elif moderate_count >= 1:
        if base_level == 'cosmetic':
            return 'moderate'
        else:
            return base_level
    else:
        return base_level

def detailed_repair_estimate(property_data: Property) -> Dict[str, Any]:
    """
    Generate a detailed repair estimate with line items
    
    Args:
        property_data: Property object with details
        
    Returns:
        Dictionary with repair estimates by category
    """
    # Determine overall renovation level
    renovation_level = estimate_renovation_level(property_data)
    
    # Base cost using square footage and renovation level
    base_cost = property_data.square_feet * COST_LEVELS[renovation_level]
    
    # Initialize repairs dictionary
    repairs = {
        'overall_level': renovation_level,
        'base_sqft_cost': COST_LEVELS[renovation_level],
        'base_estimate': base_cost,
        'line_items': {},
        'total': base_cost
    }
    
    # Check for specific issues based on keywords and add line items
    description = property_data.description.lower()
    
    # Check for roof issues
    if any(k in description for k in ['roof', 'leak', 'ceiling']):
        if 'new roof' in description or 'roof replaced' in description:
            # Roof was recently replaced
            pass
        elif 'roof leak' in description or 'roof damage' in description:
            repairs['line_items']['roof'] = ITEM_COSTS['roof']['replace']
            repairs['total'] += ITEM_COSTS['roof']['replace']
        else:
            repairs['line_items']['roof'] = ITEM_COSTS['roof']['repair']
            repairs['total'] += ITEM_COSTS['roof']['repair']
    
    # Check for HVAC issues
    if any(k in description for k in ['hvac', 'heat', 'cooling', 'furnace', 'air conditioning']):
        if 'new hvac' in description or 'new furnace' in description:
            # HVAC was recently replaced
            pass
        elif 'hvac issue' in description or 'heating problem' in description:
            repairs['line_items']['hvac'] = ITEM_COSTS['hvac']['replace']
            repairs['total'] += ITEM_COSTS['hvac']['replace']
        else:
            repairs['line_items']['hvac'] = ITEM_COSTS['hvac']['repair']
            repairs['total'] += ITEM_COSTS['hvac']['repair']
    
    # Kitchen renovation based on renovation level
    if renovation_level in ['moderate', 'extensive', 'complete']:
        kitchen_level = 'high_end' if renovation_level == 'complete' else renovation_level
        repairs['line_items']['kitchen'] = ITEM_COSTS['kitchen'][kitchen_level]
        repairs['total'] += ITEM_COSTS['kitchen'][kitchen_level]
    
    # Bathroom renovations based on count and renovation level
    if renovation_level in ['moderate', 'extensive', 'complete']:
        bath_level = 'high_end' if renovation_level == 'complete' else renovation_level
        bath_count = min(property_data.bathrooms, 3)  # Cap at 3 bathrooms
        bath_cost = ITEM_COSTS['bathroom'][bath_level] * bath_count
        repairs['line_items']['bathrooms'] = bath_cost
        repairs['total'] += bath_cost
    
    # Adjust for other potential issues based on age
    if property_data.age and property_data.age > 30:
        # Older homes likely need electrical updates
        repairs['line_items']['electrical'] = ITEM_COSTS['electrical']['update']
        repairs['total'] += ITEM_COSTS['electrical']['update']
        
        # Older homes likely need plumbing updates
        repairs['line_items']['plumbing'] = ITEM_COSTS['plumbing']['update']
        repairs['total'] += ITEM_COSTS['plumbing']['update']
    
    # Add contingency (10%)
    contingency = repairs['total'] * 0.10
    repairs['contingency'] = contingency
    repairs['total'] += contingency
    
    logger.info(f"Detailed repair estimate for {property_data.address}: {renovation_level} level, ${repairs['total']:,.2f}")
    
    return repairs
