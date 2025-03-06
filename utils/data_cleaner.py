"""
Data Cleaner - Clean and normalize property data
"""

import logging
import re
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Union

logger = logging.getLogger(__name__)

def clean_address(address: str) -> str:
    """
    Clean and standardize property address
    
    Args:
        address: Property address string
        
    Returns:
        Cleaned address string
    """
    if not address:
        return ""
    
    # Convert to string if not already
    address = str(address)
    
    # Remove extra whitespace
    address = re.sub(r'\s+', ' ', address).strip()
    
    # Standardize abbreviations
    replacements = {
        r'\bAVENUE\b': 'AVE',
        r'\bAVE\.$': 'AVE',
        r'\bBOULEVARD\b': 'BLVD',
        r'\bBLVD\.$': 'BLVD',
        r'\bCIRCLE\b': 'CIR',
        r'\bCIR\.$': 'CIR',
        r'\bCOURT\b': 'CT',
        r'\bCT\.$': 'CT',
        r'\bDRIVE\b': 'DR',
        r'\bDR\.$': 'DR',
        r'\bLANE\b': 'LN',
        r'\bLN\.$': 'LN',
        r'\bPLACE\b': 'PL',
        r'\bPL\.$': 'PL',
        r'\bROAD\b': 'RD',
        r'\bRD\.$': 'RD',
        r'\bSTREET\b': 'ST',
        r'\bST\.$': 'ST',
        r'\bWAY\b': 'WAY',
        r'\bTERRACE\b': 'TER',
        r'\bTER\.$': 'TER',
        r'\bNORTH\b': 'N',
        r'\bSOUTH\b': 'S',
        r'\bEAST\b': 'E',
        r'\bWEST\b': 'W',
        r'\bN\.$': 'N',
        r'\bS\.$': 'S',
        r'\bE\.$': 'E',
        r'\bW\.$': 'W',
        r'\bAPARTMENT\b': 'APT',
        r'\bAPT\.$': 'APT',
        r'\bSUITE\b': 'STE',
        r'\bSTE\.$': 'STE',
        r'\bUNIT\b': 'UNIT'
    }
    
    for pattern, replacement in replacements.items():
        address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
    
    return address

def clean_property_data(properties: List[Any]) -> List[Any]:
    """
    Clean and standardize property data
    
    Args:
        properties: List of property objects or dictionaries
        
    Returns:
        List of cleaned property objects/dictionaries
    """
    clean_properties = []
    
    for prop in properties:
        try:
            # Create a copy of the property data
            clean_prop = prop.copy() if isinstance(prop, dict) else prop
            
            # Clean address if it's a dictionary
            if isinstance(clean_prop, dict):
                if 'address' in clean_prop:
                    clean_prop['address'] = clean_address(clean_prop['address'])
                
                # Ensure numeric values are correct type
                numeric_fields = ['list_price', 'square_feet', 'bedrooms', 'bathrooms', 'year_built']
                for field in numeric_fields:
                    if field in clean_prop:
                        try:
                            if field in ['bedrooms', 'year_built']:
                                clean_prop[field] = int(float(clean_prop[field])) if clean_prop[field] else 0
                            elif field == 'bathrooms':
                                clean_prop[field] = float(clean_prop[field]) if clean_prop[field] else 0
                            else:
                                clean_prop[field] = float(clean_prop[field]) if clean_prop[field] else 0
                        except (ValueError, TypeError):
                            if field in ['bedrooms', 'year_built']:
                                clean_prop[field] = 0
                            elif field == 'bathrooms':
                                clean_prop[field] = 0.0
                            else:
                                clean_prop[field] = 0.0
            
            clean_properties.append(clean_prop)
        
        except Exception as e:
            logger.error(f"Error cleaning property data: {str(e)}")
            # Add the original property data if cleaning fails
            clean_properties.append(prop)
    
    return clean_properties

def detect_outliers(df: pd.DataFrame, columns: List[str], threshold: float = 3.0) -> pd.DataFrame:
    """
    Detect outliers in specified columns using z-score
    
    Args:
        df: DataFrame with property data
        columns: List of column names to check for outliers
        threshold: Z-score threshold (default: 3.0)
        
    Returns:
        DataFrame with outlier flags
    """
    result_df = df.copy()
    
    for col in columns:
        if col in df.columns and df[col].dtype in ['int64', 'float64']:
            # Calculate z-scores
            z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
            
            # Flag outliers
            result_df[f'{col}_outlier'] = z_scores > threshold
    
    return result_df

def normalize_numerical_features(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """
    Normalize numerical features to a 0-1 scale
    
    Args:
        df: DataFrame with property data
        columns: List of column names to normalize
        
    Returns:
        DataFrame with normalized columns
    """
    result_df = df.copy()
    
    for col in columns:
        if col in df.columns and df[col].dtype in ['int64', 'float64']:
            min_val = df[col].min()
            max_val = df[col].max()
            
            if max_val > min_val:
                result_df[f'{col}_normalized'] = (df[col] - min_val) / (max_val - min_val)
            else:
                result_df[f'{col}_normalized'] = 0.0
    
    return result_df

def clean_zip_code(zip_code: Union[str, int]) -> str:
    """
    Clean and standardize ZIP code
    
    Args:
        zip_code: ZIP code as string or integer
        
    Returns:
        Cleaned 5-digit ZIP code string
    """
    if not zip_code:
        return ""
    
    # Convert to string if not already
    zip_str = str(zip_code).strip()
    
    # Extract the first 5 digits
    match = re.search(r'^\d{5}', zip_str)
    if match:
        return match.group(0)
    
    # If not a 5-digit ZIP, return original
    return zip_str
