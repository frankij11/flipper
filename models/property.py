"""
Property - Data model for real estate properties
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class Property:
    """Class for storing property data"""
    mls_id: str
    address: str
    city: str
    state: str
    zip_code: str
    list_price: float
    bedrooms: int
    bathrooms: float
    square_feet: float
    lot_size: Any
    year_built: int
    days_on_market: int
    description: str
    latitude: float = 0.0
    longitude: float = 0.0
    
    # Optional fields that may be populated later
    photos: List[str] = field(default_factory=list)
    opportunity_keywords: List[str] = field(default_factory=list)
    
    # Fields to be filled with additional data
    comps: List[Dict] = field(default_factory=list)
    tax_data: Dict = field(default_factory=dict)
    neighborhood_data: Dict = field(default_factory=dict)
    
    # Analysis fields
    estimated_repair_cost: float = 0.0
    estimated_arv: float = 0.0
    estimated_profit: float = 0.0
    estimated_roi: float = 0.0
    
    def __post_init__(self):
        """Validate and set defaults for the property"""
        # Ensure numeric fields are correct type
        self.list_price = float(self.list_price)
        self.square_feet = float(self.square_feet)
        self.bedrooms = int(self.bedrooms) if self.bedrooms else 0
        self.year_built = int(self.year_built) if self.year_built else 0
        
        # Calculate price per square foot
        self.price_per_sqft = round(self.list_price / self.square_feet, 2) if self.square_feet else 0
        
        # Property age
        current_year = datetime.now().year
        self.age = current_year - self.year_built if self.year_built > 0 else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert property to dictionary for serialization"""
        return {
            'mls_id': self.mls_id,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'list_price': self.list_price,
            'bedrooms': self.bedrooms,
            'bathrooms': self.bathrooms,
            'square_feet': self.square_feet,
            'lot_size': self.lot_size,
            'year_built': self.year_built,
            'age': self.age,
            'days_on_market': self.days_on_market,
            'price_per_sqft': self.price_per_sqft,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'opportunity_keywords': self.opportunity_keywords,
            'estimated_repair_cost': self.estimated_repair_cost,
            'estimated_arv': self.estimated_arv,
            'estimated_profit': self.estimated_profit,
            'estimated_roi': self.estimated_roi
        }
    
    def get_full_address(self) -> str:
        """Get the full address as a formatted string"""
        return f"{self.address}, {self.city}, {self.state} {self.zip_code}"
