"""
MLS Connector - Interface with Bright MLS API
"""

import logging
import requests
from datetime import datetime, timedelta
from config import credentials, settings
from models.property import Property

logger = logging.getLogger(__name__)

class BrightMLSConnector:
    """Connector for Bright MLS API"""
    
    def __init__(self):
        self.api_key = credentials.BRIGHT_MLS_API_KEY
        self.api_url = credentials.BRIGHT_MLS_API_URL
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def authenticate(self):
        """Authenticate with the MLS API"""
        try:
            auth_url = f"{self.api_url}/oauth2/token"
            payload = {
                'client_id': credentials.BRIGHT_MLS_CLIENT_ID,
                'client_secret': credentials.BRIGHT_MLS_CLIENT_SECRET,
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(auth_url, json=payload)
            response.raise_for_status()
            
            token_data = response.json()
            self.headers['Authorization'] = f"Bearer {token_data['access_token']}"
            logger.info("Successfully authenticated with Bright MLS")
            
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    def build_search_query(self, area, max_price, days_on_market, property_types):
        """Build the search query for the MLS API"""
        # Construct date for days on market filter
        dom_date = (datetime.now() - timedelta(days=days_on_market)).strftime('%Y-%m-%d')
        
        # Build query
        query = {
            "filter": {
                "$and": [
                    {"StandardStatus": {"$in": ["Active", "Coming Soon"]}},
                    {"ListPrice": {"$lte": max_price}},
                    {"PropertyType": {"$in": property_types}},
                    {"ListingContractDate": {"$gte": dom_date}}
                ]
            },
            "fields": [
                "ListingId", "ListPrice", "UnparsedAddress", "City", "StateOrProvince", 
                "PostalCode", "BedroomsTotal", "BathroomsFull", "BathroomsHalf", 
                "LivingArea", "LotSize", "YearBuilt", "DaysOnMarket", "ListingContractDate",
                "PublicRemarks", "PrivateRemarks", "Latitude", "Longitude", "Media"
            ],
            "limit": 100
        }
        
        # Add area-specific filters (ZIP, city, etc.)
        if area:
            if area.isdigit() and len(area) == 5:
                # It's a ZIP code
                query["filter"]["$and"].append({"PostalCode": area})
            else:
                # It's a city or area name
                query["filter"]["$and"].append({"City": {"$eq": area}})
        
        return query
    
    def search_properties(self, area, max_price, days_on_market, property_types):
        """Search for properties matching criteria"""
        if not self.authenticate():
            return []
        
        query = self.build_search_query(area, max_price, days_on_market, property_types)
        
        try:
            search_url = f"{self.api_url}/properties/search"
            response = requests.post(search_url, headers=self.headers, json=query)
            response.raise_for_status()
            
            results = response.json()
            logger.info(f"Found {len(results['value'])} properties in MLS search")
            
            return results['value']
        except requests.exceptions.RequestException as e:
            logger.error(f"Property search error: {str(e)}")
            return []
    
    def convert_to_property_objects(self, mls_properties):
        """Convert MLS data to Property objects"""
        properties = []
        
        for prop_data in mls_properties:
            try:
                # Create property object
                property_obj = Property(
                    mls_id=prop_data.get('ListingId', ''),
                    address=prop_data.get('UnparsedAddress', ''),
                    city=prop_data.get('City', ''),
                    state=prop_data.get('StateOrProvince', ''),
                    zip_code=prop_data.get('PostalCode', ''),
                    list_price=float(prop_data.get('ListPrice', 0)),
                    bedrooms=int(prop_data.get('BedroomsTotal', 0)),
                    bathrooms=int(prop_data.get('BathroomsFull', 0)) + 0.5 * int(prop_data.get('BathroomsHalf', 0)),
                    square_feet=float(prop_data.get('LivingArea', 0)),
                    lot_size=prop_data.get('LotSize', ''),
                    year_built=int(prop_data.get('YearBuilt', 0)),
                    days_on_market=int(prop_data.get('DaysOnMarket', 0)),
                    description=prop_data.get('PublicRemarks', ''),
                    latitude=float(prop_data.get('Latitude', 0)),
                    longitude=float(prop_data.get('Longitude', 0)),
                    photos=[photo.get('MediaURL', '') for photo in prop_data.get('Media', [])]
                )
                
                # Extract keywords that might indicate potential for flipping
                property_obj.opportunity_keywords = self.extract_opportunity_keywords(prop_data)
                
                properties.append(property_obj)
            except Exception as e:
                logger.error(f"Error converting property data: {str(e)}")
                continue
        
        return properties
    
    def extract_opportunity_keywords(self, prop_data):
        """Extract keywords that might indicate a good flip opportunity"""
        keywords = []
        remarks = (prop_data.get('PublicRemarks', '') + ' ' + prop_data.get('PrivateRemarks', '')).lower()
        
        for term in settings.OPPORTUNITY_KEYWORDS:
            if term in remarks:
                keywords.append(term)
        
        return keywords

def get_properties(area=None, max_price=None, days_on_market=90, property_types=None):
    """Get properties matching criteria from Bright MLS"""
    if property_types is None:
        property_types = ['Residential', 'Condo/Co-Op']
    
    connector = BrightMLSConnector()
    mls_properties = connector.search_properties(area, max_price, days_on_market, property_types)
    
    return connector.convert_to_property_objects(mls_properties)
