"""
Redfin Connector - Unofficial API access to Redfin property data
"""

import logging
import requests
import requests_html
import pandas as pd
import re
import json
import csv
import io
import time
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import urllib.parse
from models.property import Property

logger = logging.getLogger(__name__)

class RedfinConnector:
    """
    Connector for Redfin's unofficial API
    
    Note: This uses undocumented endpoints that may change.
    Use responsibly and respect Redfin's terms of service.
    """
    
    def __init__(self):
        self.base_url = "https://www.redfin.com"
        self.search_url = "https://www.redfin.com/stingray/api/gis-csv?al=3&fixer=true&has_att_fiber=false&has_deal=false&has_dishwasher=false&has_laundry_facility=false&has_laundry_hookups=false&has_parking=false&has_pool=false&has_short_term_lease=false&include_pending_homes=false&isRentals=false&is_furnished=false&is_income_restricted=false&is_senior_living=false&market=dc&num_homes=350&ord=redfin-recommended-asc&page_number=1&poly=-77.119901%2038.791514%2C-76.9095394%2038.791514%2C-76.9095394%2038.9953797%2C-77.119901%2038.9953797%2C-77.119901%2038.791514&pool=false&region_id=12839&region_type=6&sf=1,2,3,5,6,7&status=9&travel_with_traffic=false&travel_within_region=false&uipt=1,3&utilities_included=false&v=8"#f"{self.base_url}/stingray/do/location-autocomplete"
        self.initial_info_url = f"{self.base_url}/stingray/api/gis"
        self.gis_url = f"{self.base_url}/stingray/api/gis"
        self.filter_url = f"https://www.redfin.com/stingray/api/gis-csv?al=3&fixer=true&has_att_fiber=false&has_deal=false&has_dishwasher=false&has_laundry_facility=false&has_laundry_hookups=false&has_parking=false&has_pool=false&has_short_term_lease=false&include_pending_homes=false&isRentals=false&is_furnished=false&is_income_restricted=false&is_senior_living=false&market=dc&num_homes=350&ord=redfin-recommended-asc&page_number=1&poly=-77.119901%2038.791514%2C-76.9095394%2038.791514%2C-76.9095394%2038.9953797%2C-77.119901%2038.9953797%2C-77.119901%2038.791514&pool=false&region_id=12839&region_type=6&sf=1,2,3,5,6,7&status=9&travel_with_traffic=false&travel_within_region=false&uipt=1,3&utilities_included=false&v=8"#f"{self.base_url}/api/v1/search/filterParamsFromQuery"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "TE": "Trailers",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_location_id(self, location: str) -> Optional[str]:
        """
        Get Redfin location ID from a location string (ZIP code, city, address)
        
        Args:
            location: Location string (ZIP, city, etc.)
            
        Returns:
            Redfin location ID or None if not found
        """
        try:
            params = {
                "location": location,
                "start": 0,
                "count": 10,
                "v": 2,
                "market": "false",
                "iss": "false",
                "ooa": "true",
                "mrs": "false",
                "region_id": "",
                "region_type": "",
                "lat": "",
                "lng": ""
            }
            
            response = self.session.get(self.search_url)#, params=params)
            response.raise_for_status()
            
            # Parse the response (it's in a special format)
            data = response.text
            if not data.startswith("{}&&"):
                logger.warning(f"Unexpected Redfin response format for location: {location}")
                return None
            
            # Remove the {}&& prefix and parse JSON
            json_data = json.loads(data[4:])
            
            # Get the exact match or first match
            matches = json_data.get("payload", {}).get("exactMatch", [])
            if not matches:
                matches = json_data.get("payload", {}).get("sections", [{}])[0].get("rows", [])
            
            if not matches:
                logger.warning(f"No location matches found for: {location}")
                return None
            
            # Get the location ID from the URL
            match = matches[0]
            url = match.get("url", "")
            location_id = None
            
            # Extract region ID from URL
            if url:
                region_match = re.search(r"/(\d+)_nb/", url)
                if region_match:
                    location_id = region_match.group(1)
            
            if not location_id:
                # Try getting ID directly
                location_id = match.get("id", None)
            
            logger.info(f"Found Redfin location ID for {location}: {location_id}")
            return location_id
            
        except Exception as e:
            logger.error(f"Error getting Redfin location ID: {str(e)}")
            return None
    
    def get_properties_by_location(self, location: str, max_price: Optional[float] = None, 
                                 property_types: Optional[List[str]] = None,
                                 status: str = "for-sale") -> List[Dict[str, Any]]:
        """
        Get properties from Redfin by location
        
        Args:
            location: Location string (ZIP, city, etc.)
            max_price: Maximum price filter
            property_types: List of property types to include
            status: Property status ('for-sale', 'sold', etc.)
            
        Returns:
            List of property dictionaries
        """
        try:
            # Map property types to Redfin property types
            redfin_property_types = []
            if property_types:
                mapping = {
                    "Residential": "1",
                    "Condo/Co-Op": "2",
                    "Townhouse": "3",
                    "Multi-Family": "4",
                    "Land": "5",
                    "Other": "6"
                }
                redfin_property_types = [mapping.get(pt, "1") for pt in property_types if pt in mapping]
            
            if not redfin_property_types:
                redfin_property_types = ["1", "2"]  # Default to house and condo
            
            # Get location ID
            location_id = self.get_location_id(location)
            if not location_id:
                logger.error(f"Could not get Redfin location ID for: {location}")
                return []
            
            # Build the search URL
            filters = {
                "status": status,
                "propertyType": ",".join(redfin_property_types)
            }
            
            if max_price:
                filters["maxPrice"] = str(int(max_price))
            
            # Get filter parameters
            filter_params_str = urllib.parse.urlencode(filters)
            filter_response = self.session.get(f"{self.filter_url}?{filter_params_str}")
            filter_response.raise_for_status()
            filter_data = filter_response.json()
            
            # The request URL for data in CSV format
            request_url = f"{self.base_url}/api/gis?al=1&market=false&type=5&v=8"
            request_url += f"&region_id={location_id}&region_type=6&uipt={','.join(redfin_property_types)}"
            
            if max_price:
                request_url += f"&max_price={int(max_price)}"
            
            request_url += "&num_homes=10000&sf=1,2,3,4,5,6,7&status=9"
            
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Host": "www.redfin.com",
                "Referer": f"{self.base_url}/city/{location_id}/filter/property-type=house+condo",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            response = self.session.get(request_url, headers=headers)
            response.raise_for_status()
            
            # The response contains a download link to the CSV data
            match = re.search(r'\"url\":\"([^\"]+)\"', response.text)
            if not match:
                logger.error(f"Could not find CSV download URL in Redfin response for {location}")
                return []
            
            download_url = match.group(1).replace("\\u002F", "/")
            download_url = f"{self.base_url}{download_url}"
            
            # Get the CSV data
            csv_response = self.session.get(download_url)
            csv_response.raise_for_status()
            
            # Parse CSV data into list of dictionaries
            properties = []
            csv_data = csv_response.content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_data))
            
            for row in csv_reader:
                properties.append(dict(row))
            
            logger.info(f"Found {len(properties)} properties in Redfin for {location}")
            return properties
            
        except Exception as e:
            logger.error(f"Error getting Redfin properties: {str(e)}")
            return []
    
    def get_property_details(self, property_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific property
        
        Args:
            property_id: Redfin property ID
            
        Returns:
            Dictionary with property details
        """
        try:
            url = f"{self.base_url}/stingray/api/home/details/propertyId/{property_id}"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse the response (it's in a special format)
            data = response.text
            if not data.startswith("{}&&"):
                logger.warning(f"Unexpected Redfin response format for property: {property_id}")
                return {}
            
            # Remove the {}&& prefix and parse JSON
            json_data = json.loads(data[4:])
            
            return json_data.get("payload", {})
            
        except Exception as e:
            logger.error(f"Error getting Redfin property details: {str(e)}")
            return {}
    
    def convert_to_property_objects(self, redfin_properties: List[Dict[str, Any]]) -> List[Property]:
        """
        Convert Redfin property data to Property objects
        
        Args:
            redfin_properties: List of Redfin property dictionaries
            
        Returns:
            List of Property objects
        """
        properties = []
        
        for prop_data in redfin_properties:
            try:
                # Extract and map data from Redfin format to our Property model
                
                # Get address components
                address = prop_data.get('ADDRESS', '')
                city = prop_data.get('CITY', '')
                state = prop_data.get('STATE OR PROVINCE', '')
                zip_code = prop_data.get('ZIP OR POSTAL CODE', '')
                
                # Create property object
                property_obj = Property(
                    mls_id=f"REDFIN_{prop_data.get('MLS#', prop_data.get('LISTING ID', ''))}",
                    address=address,
                    city=city,
                    state=state,
                    zip_code=zip_code,
                    list_price=float(prop_data.get('PRICE',0)), #float(prop_data.get('PRICE', '0').replace('$', '').replace(',', '')) if prop_data.get('PRICE') else 0,
                    bedrooms=int(float(prop_data.get('BEDS', 0))) if prop_data.get('BEDS') else 0,
                    bathrooms=float(prop_data.get('BATHS', 0)) if prop_data.get('BATHS') else 0,
                    square_feet=float(prop_data.get('SQUARE FEET', '0').replace(',', '')) if prop_data.get('SQUARE FEET') else 0,
                    lot_size=prop_data.get('LOT SIZE', ''),
                    year_built=int(float(prop_data.get('YEAR BUILT', 0))) if prop_data.get('YEAR BUILT') else 0,
                    days_on_market=int(prop_data.get('DAYS ON MARKET', 0)) if prop_data.get('DAYS ON MARKET') else 0,
                    description=prop_data.get('REMARKS', ''),
                    latitude=float(prop_data.get('LATITUDE', 0)) if prop_data.get('LATITUDE') else 0,
                    longitude=float(prop_data.get('LONGITUDE', 0)) if prop_data.get('LONGITUDE') else 0,
                    photos=[prop_data.get('PHOTO', '')] if prop_data.get('PHOTO') else []
                )
                
                # Extract keywords that might indicate potential for flipping
                property_obj.opportunity_keywords = self.extract_opportunity_keywords(prop_data)
                
                properties.append(property_obj)
            except Exception as e:
                logger.error(f"Error converting Redfin property data: {str(e)}")
                continue
        
        return properties
    
    def extract_opportunity_keywords(self, prop_data: Dict[str, Any]) -> List[str]:
        """
        Extract keywords that might indicate a good flip opportunity
        
        Args:
            prop_data: Redfin property data dictionary
            
        Returns:
            List of opportunity keywords found
        """
        keywords = []
        description = (prop_data.get('REMARKS', '') + ' ' + prop_data.get('PUBLIC REMARKS', '')).lower()
        
        opportunity_terms = [
            'as-is', 'fixer', 'needs work', 'handyman', 'tlc', 'potential', 'opportunity',
            'estate sale', 'foreclosure', 'bank owned', 'reo', 'short sale', 'distressed',
            'investor', 'renovation', 'remodel', 'restore', 'flip', 'under market', 'bargain',
            'motivated', 'must sell', 'bring offer', 'priced to sell', 'reduced'
        ]
        
        for term in opportunity_terms:
            if term in description:
                keywords.append(term)
        
        return keywords
    def get_properties_from_csv(self,file_path: str=None ) -> List[Property]:
        """
        Get properties from a CSV file
        """
        #file_path = "https://www.redfin.com/stingray/api/gis-csv?al=3&fixer=true&has_att_fiber=false&has_deal=false&has_dishwasher=false&has_laundry_facility=false&has_laundry_hookups=false&has_parking=false&has_pool=false&has_short_term_lease=false&include_pending_homes=false&isRentals=false&is_furnished=false&is_income_restricted=false&is_senior_living=false&market=dc&num_homes=350&ord=redfin-recommended-asc&page_number=1&poly=-77.119901%2038.791514%2C-76.9095394%2038.791514%2C-76.9095394%2038.9953797%2C-77.119901%2038.9953797%2C-77.119901%2038.791514&pool=false&region_id=12839&region_type=6&sf=1,2,3,5,6,7&status=9&travel_with_traffic=false&travel_within_region=false&uipt=1,3&utilities_included=false&v=8"
        file_path = 'https://www.redfin.com/stingray/api/gis-csv?al=1&market=dc&max_price=500000&min_stories=1&num_homes=350&ord=redfin-recommended-asc&page_number=1&region_id=20065&region_type=6&sf=1,2,3,5,6,7&status=9&uipt=1,2,3,4,5,6&v=8'
        with requests_html.HTMLSession() as session:
            from io import StringIO
            r = session.get(file_path)
            #r.html.render()
            df = pd.read_csv(StringIO(r.html.html)).assign(**{"AS of Date":datetime.now().strftime("%Y-%m-%d")})
            logger.info("fetch data from refin")
            logger.info(df.head())
            #df = pd.read_csv(url)
            df.columns = df.columns.str.strip().str.upper().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
            try:
                all_df = pd.read_csv("data/raw/redfin_properties.csv")
            except:
                all_df = pd.DataFrame()
            try:
                all_df = pd.concat([all_df,df]).drop_duplicates()
            except:
                all_df = df
            all_df.to_csv("data/raw/redfin_properties.csv",index=False)
        
        return df.to_dict(orient='records') 

def get_properties(location: str, max_price: Optional[float] = None, 
                   property_types: Optional[List[str]] = None) -> List[Property]:
    """
    Get properties from Redfin matching criteria
    
    Args:
        location: Location string (ZIP, city, etc.)
        max_price: Maximum price filter
        property_types: List of property types to include
        
    Returns:
        List of Property objects
    """
    connector = RedfinConnector()
    redfin_properties = connector.get_properties_from_csv()
    
    return connector.convert_to_property_objects(redfin_properties)
