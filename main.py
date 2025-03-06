#!/usr/bin/env python3
"""
Real Estate Flip Finder - Main Entry Point
"""

import os
import argparse
import logging
from datetime import datetime

from config import settings
from data import mls_connector, redfin_connector, public_records, market_data
from analysis import property_scorer, deal_analyzer
from visualization import dashboard
from utils import excel_exporter, notification

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/flip_finder_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_directories():
    """Create necessary directories if they don't exist"""
    dirs = ['logs', 'output', 'output/excel', 'output/dashboards', 'data/raw', 'data/processed']
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Real Estate Flip Finder')
    parser.add_argument('--area', type=str, help='Target area or ZIP code')
    parser.add_argument('--budget', type=float, help='Maximum purchase budget')
    parser.add_argument('--roi', type=float, default=20.0, help='Minimum ROI percentage')
    parser.add_argument('--export', action='store_true', help='Export results to Excel')
    parser.add_argument('--notify', action='store_true', help='Send email notification with results')
    parser.add_argument('--visualize', action='store_true', help='Generate visualizations')
    parser.add_argument('--source', type=str, default='mls', choices=['mls', 'redfin', 'both'],
                       help='Data source to use (mls, redfin, or both)')
    
    return parser.parse_args()

def get_properties_from_source(source, area, max_price, days_on_market, property_types):
    """Get properties from specified data source"""
    properties = []
    
    if source in ['mls', 'both']:
        logger.info("Fetching property listings from Bright MLS...")
        mls_properties = mls_connector.get_properties(
            area=area,
            max_price=max_price,
            days_on_market=days_on_market,
            property_types=property_types
        )
        properties.extend(mls_properties)
        logger.info(f"Found {len(mls_properties)} properties from MLS matching initial criteria")
    
    if source in ['redfin', 'both']:
        logger.info("Fetching property listings from Redfin...")
        redfin_properties = redfin_connector.get_properties(
            location=area,
            max_price=max_price,
            property_types=property_types
        )
        properties.extend(redfin_properties)
        logger.info(f"Found {len(redfin_properties)} properties from Redfin matching initial criteria")
    
    # De-duplicate properties if using both sources (simple deduplication by address)
    if source == 'both':
        unique_addresses = set()
        unique_properties = []
        
        for prop in properties:
            if prop.address not in unique_addresses:
                unique_addresses.add(prop.address)
                unique_properties.append(prop)
        
        logger.info(f"After deduplication: {len(unique_properties)} unique properties")
        properties = unique_properties
    
    return properties

def main():
    """Main execution function"""
    create_directories()
    args = parse_arguments()
    
    logger.info("Starting Real Estate Flip Finder")
    logger.info(f"Search parameters: Area={args.area}, Budget=${args.budget}, ROI={args.roi}%, Source={args.source}")
    
    # 1. Gather property data from selected source(s)
    properties = get_properties_from_source(
        source=args.source,
        area=args.area,
        max_price=args.budget,
        days_on_market=settings.MAX_DAYS_ON_MARKET,
        property_types=settings.PROPERTY_TYPES
    )
    
    if not properties:
        logger.warning("No properties found matching criteria")
        print("No properties found matching criteria. Try adjusting your search parameters.")
        return
    
    # 2. Enrich with additional data
    logger.info("Enriching property data...")
    for prop in properties:
        # Add public records data
        public_records.enrich_property(prop)
        # Add market data
        market_data.add_comps(prop)
    
    # 3. Analyze deals
    logger.info("Analyzing potential deals...")
    deals = []
    for prop in properties:
        # Estimate repair costs
        repair_costs = deal_analyzer.estimate_repairs(prop)
        
        # Calculate ARV
        arv = deal_analyzer.calculate_arv(prop)
        
        # Calculate potential profit
        deal = deal_analyzer.analyze_deal(
            property_data=prop,
            arv=arv,
            repair_costs=repair_costs,
            min_roi=args.roi
        )
        
        if deal['meets_criteria']:
            deals.append(deal)
    
    logger.info(f"Found {len(deals)} viable deals")
    
    # 4. Score and rank deals
    logger.info("Scoring and ranking deals...")
    scored_deals = property_scorer.score_deals(deals)
    
    # 5. Output results
    if args.export:
        logger.info("Exporting results to Excel...")
        excel_exporter.export_deals(
            scored_deals, 
            f"output/excel/potential_deals_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
    
    if args.visualize:
        logger.info("Generating visualizations...")
        dashboard.generate_dashboard(
            scored_deals, 
            f"output/dashboards/dashboard_{datetime.now().strftime('%Y%m%d')}.html"
        )
    
    if args.notify and deals:
        logger.info("Sending notification...")
        notification.send_email(
            subject=f"Found {len(deals)} potential flip properties",
            deals=scored_deals[:10]  # Send top 10 deals
        )
    
    # Print summary of top deals
    print("\nTop 5 Properties for Flipping:")
    for i, deal in enumerate(scored_deals[:5], 1):
        print(f"\n{i}. {deal['address']} - Score: {deal['score']:.2f}")
        print(f"   List Price: ${deal['list_price']:,.2f}, ARV: ${deal['arv']:,.2f}")
        print(f"   Estimated Repair: ${deal['repair_costs']:,.2f}")
        print(f"   Potential Profit: ${deal['potential_profit']:,.2f} (ROI: {deal['roi']:.2f}%)")

if __name__ == "__main__":
    main()
