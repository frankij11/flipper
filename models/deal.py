"""
Deal - Data model for real estate deals
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass
class Deal:
    """Class for storing real estate deal data"""
    property_id: str
    address: str
    list_price: float
    arv: float
    repair_costs: float
    closing_costs: float
    holding_costs: float
    total_project_cost: float
    potential_profit: float
    roi: float
    
    # Additional fields
    max_purchase_price: float
    meets_criteria: bool = False
    meets_70_percent_rule: bool = False
    score: float = 0.0
    analysis_date: datetime = field(default_factory=datetime.now)
    notes: str = ""
    
    # Reference to full property data
    property_data: Dict[str, Any] = field(default_factory=dict)
    
    # Optional fields
    offers: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert deal to dictionary for serialization"""
        return {
            'property_id': self.property_id,
            'address': self.address,
            'list_price': self.list_price,
            'arv': self.arv,
            'repair_costs': self.repair_costs,
            'closing_costs': self.closing_costs,
            'holding_costs': self.holding_costs,
            'total_project_cost': self.total_project_cost,
            'potential_profit': self.potential_profit,
            'roi': self.roi,
            'max_purchase_price': self.max_purchase_price,
            'meets_criteria': self.meets_criteria,
            'meets_70_percent_rule': self.meets_70_percent_rule,
            'score': self.score,
            'analysis_date': self.analysis_date.isoformat(),
            'notes': self.notes,
            'offers': self.offers
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Deal':
        """Create a Deal object from a dictionary"""
        # Handle datetime conversion
        if 'analysis_date' in data and isinstance(data['analysis_date'], str):
            data['analysis_date'] = datetime.fromisoformat(data['analysis_date'])
        
        return cls(**data)
    
    def add_offer(self, offer_price: float, date: datetime = None, notes: str = "") -> None:
        """Add an offer to the deal"""
        if date is None:
            date = datetime.now()
        
        offer = {
            'price': offer_price,
            'date': date.isoformat(),
            'notes': notes
        }
        
        self.offers.append(offer)
