#!/usr/bin/env python3
"""
Real Estate Flip Finder - Interactive Web Dashboard
"""

import os
import pandas as pd
import numpy as np
import panel as pn
import param
import hvplot.pandas
import holoviews as hv
from holoviews import opts
import datetime
from bokeh.models import HoverTool

from config import settings
from data import mls_connector, redfin_connector, public_records, market_data
from analysis import property_scorer, deal_analyzer
from models.property import Property
from typing import List, Dict, Any

# Initialize Panel
pn.extension('tabulator', sizing_mode="stretch_width")
hv.extension('bokeh')

# Create logger
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure necessary directories exist
def create_directories():
    """Create necessary directories if they don't exist"""
    dirs = ['logs', 'output', 'output/excel', 'output/dashboards', 'data/raw', 'data/processed']
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

create_directories()

# Define the main dashboard class
class PropertyDetailView(param.Parameterized):
    """Individual property detail view with customizable parameters"""
    
    # Property selection
    property_address = param.Selector(default=None, objects=[], doc="Select a property")
    
    # Individual property ARV parameters
    use_comps_within_miles = param.Number(default=1.0, bounds=(0.1, 5.0), step=0.1, doc="Only use comps within this distance (miles)")
    max_comp_age_months = param.Integer(default=6, bounds=(1, 24), doc="Maximum age of comps in months")
    min_comp_sqft_pct = param.Number(default=0.8, bounds=(0.5, 1.0), step=0.05, doc="Minimum comp square footage (as % of property)")
    max_comp_sqft_pct = param.Number(default=1.2, bounds=(1.0, 1.5), step=0.05, doc="Maximum comp square footage (as % of property)")
    exclude_outliers = param.Boolean(default=True, doc="Exclude outlier comps (±2 std dev)")
    
    # Individual repair estimates
    repair_cost_per_sqft = param.Number(default=settings.REPAIR_COSTS['base_sqft_cost'], bounds=(10, 100), step=5, doc="Base repair cost per square foot")
    kitchen_reno_cost = param.Number(default=settings.REPAIR_COSTS['kitchen'], bounds=(5000, 50000), step=1000, doc="Kitchen renovation cost")
    bathroom_reno_cost = param.Number(default=settings.REPAIR_COSTS['bathroom'], bounds=(2500, 25000), step=500, doc="Bathroom renovation cost")
    roof_repair = param.Boolean(default=False, doc="Needs roof repair/replacement")
    hvac_repair = param.Boolean(default=False, doc="Needs HVAC repair/replacement")
    electrical_work = param.Boolean(default=False, doc="Needs electrical updates")
    plumbing_work = param.Boolean(default=False, doc="Needs plumbing updates")
    
    # Individual holding costs
    flip_months = param.Number(default=settings.AVERAGE_FLIP_MONTHS, bounds=(1, 12), step=0.5, doc="Estimated months to flip this property")
    mortgage_rate = param.Number(default=settings.HOLDING_COSTS['mortgage_rate']*100, bounds=(3, 12), step=0.25, doc="Mortgage rate (%)")
    
    # Actions
    recalculate_deal = param.Action(lambda x: x.param.trigger('recalculate_deal'), doc="Recalculate Deal")
    
    def __init__(self, parent_dashboard, **params):
        super(PropertyDetailView, self).__init__(**params)
        self.parent = parent_dashboard
        self.selected_property = None
        self.selected_deal = None
        self.selected_property_index = -1
        self.comp_toggles = {}
        self.comp_df = pd.DataFrame()
        
    def update_property_list(self, properties, deals):
        """Update the list of properties available to select"""
        if not properties:
            self.param.property_address.objects = []
            return
            
        # Create address list for dropdown
        addresses = [prop.get_full_address() for prop in properties]
        self.param.property_address.objects = addresses
        
        # If we have properties but none selected, select the first one
        if addresses and self.property_address is None:
            self.property_address = addresses[0]
            
    def select_property(self, address):
        """Select a property by address"""
        if not address or not self.parent.properties:
            return None
            
        # Find the property and its deal
        for i, prop in enumerate(self.parent.properties):
            if prop.get_full_address() == address:
                self.selected_property = prop
                self.selected_property_index = i
                
                # Find matching deal
                for deal in self.parent.deals:
                    if deal['address'] == address:
                        self.selected_deal = deal
                        break
                        
                # Update parameters based on this property
                self.update_params_from_property()
                # Create comp toggles
                self.create_comp_toggles()
                return prop
                
        return None
        
    def update_params_from_property(self):
        """Update parameters based on selected property"""
        if not self.selected_property:
            return
            
        # Get parent parameters as defaults
        self.use_comps_within_miles = self.parent.use_comps_within_miles
        self.max_comp_age_months = self.parent.max_comp_age_months
        self.min_comp_sqft_pct = self.parent.min_comp_sqft_pct
        self.max_comp_sqft_pct = self.parent.max_comp_sqft_pct
        self.exclude_outliers = self.parent.exclude_outliers
        self.repair_cost_per_sqft = self.parent.repair_cost_per_sqft
        self.kitchen_reno_cost = self.parent.kitchen_reno_cost
        self.bathroom_reno_cost = self.parent.bathroom_reno_cost
        self.flip_months = self.parent.flip_months
        self.mortgage_rate = self.parent.mortgage_rate
        
        # Check opportunity keywords for repair flags
        keywords = [k.lower() for k in self.selected_property.opportunity_keywords]
        
        if any(k in ['roof', 'leak', 'ceiling'] for k in keywords):
            self.roof_repair = True
            
        if any(k in ['hvac', 'heat', 'cooling', 'furnace'] for k in keywords):
            self.hvac_repair = True
            
        if any(k in ['electric', 'wiring'] for k in keywords):
            self.electrical_work = True
            
        if any(k in ['plumbing', 'pipe', 'water'] for k in keywords):
            self.plumbing_work = True
    
    def create_comp_toggles(self):
        """Create toggle switches for each comp"""
        self.comp_toggles = {}
        
        if not self.selected_property or not self.selected_property.comps:
            return {}
            
        # Create a toggle for each comp
        for i, comp in enumerate(self.selected_property.comps):
            is_used = self.parent.is_comp_used(self.selected_property, comp)
            toggle_name = f"comp_{i}"
            address = comp['address']
            
            self.comp_toggles[toggle_name] = pn.widgets.Checkbox(
                name=f"{address} - ${comp['price']:,.0f} - {comp['sale_date']}",
                value=is_used
            )
            
        # Create DataFrame for all comps
        comp_data = []
        for i, comp in enumerate(self.selected_property.comps):
            comp_data.append({
                'Comp ID': i, 
                'Address': comp['address'],
                'Price': comp['price'],
                'Price/SqFt': comp['price_per_sqft'],
                'SqFt': comp['square_feet'],
                'Beds': comp.get('bedrooms', '-'),
                'Baths': comp.get('bathrooms', '-'),
                'Sale Date': comp['sale_date'],
                'Distance': comp['distance'],
                'Used in ARV': self.comp_toggles[f"comp_{i}"].value
            })
            
        self.comp_df = pd.DataFrame(comp_data)
        
        return self.comp_toggles
        
    def recalculate_property_deal(self):
        """Recalculate deal metrics for the selected property with custom parameters"""
        if not self.selected_property or not self.selected_deal:
            return None
            
        # Apply custom filters to comps based on parameters and toggles
        filtered_comps = []
        
        for i, comp in enumerate(self.selected_property.comps):
            # Check if manually included via toggle
            toggle_name = f"comp_{i}"
            if toggle_name in self.comp_toggles and self.comp_toggles[toggle_name].value:
                filtered_comps.append(comp)
                
        # If no comps are selected, reset to automatic filtering
        if not filtered_comps:
            filtered_comps = self.filter_comps()
            
        # Update the property comps
        self.selected_property.comps = filtered_comps
        
        # Calculate custom repair costs
        repair_costs = self.calculate_repair_costs()
        
        # Calculate ARV
        arv = self.calculate_arv()
        
        # Update deal with custom metrics
        custom_deal = deal_analyzer.analyze_deal(
            property_data=self.selected_property,
            arv=arv,
            repair_costs=repair_costs,
            min_roi=self.parent.min_roi
        )
        
        # Update selected deal
        self.selected_deal = custom_deal
        
        # Update the deal in the parent's deals list
        if self.selected_property_index >= 0 and self.selected_property_index < len(self.parent.properties):
            for i, deal in enumerate(self.parent.deals):
                if deal['property_id'] == custom_deal['property_id']:
                    self.parent.deals[i] = custom_deal
                    break
        
        # Re-score all deals to update rankings
        self.parent.score_deals()
        
        return custom_deal
        
    def filter_comps(self):
        """Filter property comps based on current parameters"""
        if not self.selected_property or not self.selected_property.comps:
            return []
            
        filtered_comps = []
        min_sqft = self.selected_property.square_feet * self.min_comp_sqft_pct
        max_sqft = self.selected_property.square_feet * self.max_comp_sqft_pct
        max_distance = self.use_comps_within_miles
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=self.max_comp_age_months * 30)).strftime('%Y-%m-%d')
        
        for comp in self.selected_property.comps:
            if (comp['square_feet'] >= min_sqft and 
                comp['square_feet'] <= max_sqft and
                comp['distance'] <= max_distance and
                comp['sale_date'] >= cutoff_date):
                filtered_comps.append(comp)
                
        return filtered_comps
        
    def calculate_arv(self):
        """Calculate ARV with custom filters applied"""
        if not self.selected_property or not self.selected_property.comps:
            return self.selected_property.list_price * 1.5
            
        # Extract price per square foot from comps
        comp_psf = [comp['price_per_sqft'] for comp in self.selected_property.comps]
        
        if not comp_psf:
            return self.selected_property.list_price * 1.5
            
        # Remove outliers if specified
        if self.exclude_outliers and len(comp_psf) > 5:
            mean_psf = np.mean(comp_psf)
            std_psf = np.std(comp_psf)
            filtered_psf = [psf for psf in comp_psf if abs(psf - mean_psf) <= 2 * std_psf]
            
            if filtered_psf:
                avg_psf = np.mean(filtered_psf)
            else:
                avg_psf = mean_psf
        else:
            avg_psf = np.mean(comp_psf)
            
        # Calculate ARV based on average price per square foot
        arv = self.selected_property.square_feet * avg_psf
        
        return arv
        
    def calculate_repair_costs(self):
        """Calculate custom repair costs based on parameters"""
        base_cost = self.selected_property.square_feet * self.repair_cost_per_sqft
        
        # Add kitchen and bathroom costs
        kitchen_cost = self.kitchen_reno_cost
        bathroom_cost = self.bathroom_reno_cost * self.selected_property.bathrooms
        
        # Add additional repair costs if needed
        additional_costs = 0
        if self.roof_repair:
            additional_costs += settings.REPAIR_COSTS['roof']
        if self.hvac_repair:
            additional_costs += settings.REPAIR_COSTS['hvac']
        if self.electrical_work:
            additional_costs += settings.REPAIR_COSTS['electrical']
        if self.plumbing_work:
            additional_costs += settings.REPAIR_COSTS['plumbing']
            
        # Calculate total with contingency
        total_cost = (base_cost + kitchen_cost + bathroom_cost + additional_costs) * 1.1  # 10% contingency
        
        return total_cost

class FlipFinderDashboard(param.Parameterized):
    """Interactive dashboard for Real Estate Flip Finder"""
    
    # Class attributes
    default_columns = ['Address', 'List Price', 'ARV', 'Repair Costs', 'Profit', 'ROI (%)', 'Score']
    
    # Input parameters
    area = param.String(default="20878", doc="Target area or ZIP code")
    budget = param.Number(default=400000, bounds=(50000, 2000000), step=10000, doc="Maximum purchase budget")
    min_roi = param.Number(default=20.0, bounds=(5, 50), step=1.0, doc="Minimum ROI percentage")
    data_source = param.ObjectSelector(default="redfin", objects=["mls", "redfin", "both"], doc="Data source to use")
    
    # ARV parameters
    use_comps_within_miles = param.Number(default=1.0, bounds=(0.1, 5.0), step=0.1, doc="Only use comps within this distance (miles)")
    max_comp_age_months = param.Integer(default=6, bounds=(1, 24), doc="Maximum age of comps in months")
    min_comp_sqft_pct = param.Number(default=0.8, bounds=(0.5, 1.0), step=0.05, doc="Minimum comp square footage (as % of property)")
    max_comp_sqft_pct = param.Number(default=1.2, bounds=(1.0, 1.5), step=0.05, doc="Maximum comp square footage (as % of property)")
    exclude_outliers = param.Boolean(default=True, doc="Exclude outlier comps (±2 std dev)")
    
    # Repair cost parameters
    repair_cost_per_sqft = param.Number(default=settings.REPAIR_COSTS['base_sqft_cost'], bounds=(10, 100), step=5, doc="Base repair cost per square foot")
    kitchen_reno_cost = param.Number(default=settings.REPAIR_COSTS['kitchen'], bounds=(5000, 50000), step=1000, doc="Kitchen renovation cost")
    bathroom_reno_cost = param.Number(default=settings.REPAIR_COSTS['bathroom'], bounds=(2500, 25000), step=500, doc="Bathroom renovation cost")
    
    # Holding cost parameters
    flip_months = param.Number(default=settings.AVERAGE_FLIP_MONTHS, bounds=(1, 12), step=0.5, doc="Average months to flip")
    mortgage_rate = param.Number(default=settings.HOLDING_COSTS['mortgage_rate']*100, bounds=(3, 12), step=0.25, doc="Mortgage rate (%)")
    
    # Action buttons
    run_analysis = param.Action(lambda x: x.param.trigger('run_analysis'), doc="Run Analysis")
    export_to_excel = param.Action(lambda x: x.param.trigger('export_to_excel'), doc="Export to Excel")
    
    def __init__(self, **params):
        super(FlipFinderDashboard, self).__init__(**params)
        self.properties = []
        self.deals = []
        self.scored_deals = []
        self.deal_df = pd.DataFrame()
        self.comp_df = pd.DataFrame()
        self.property_detail_view = PropertyDetailView(parent_dashboard=self)
        self.dashboard = None  # Will store reference to the dashboard for tab switching
        
    def get_properties(self):
        """Get properties from selected data source"""
        properties = []
        
        try:
            if self.data_source in ['mls', 'both']:
                logger.info("Fetching property listings from Bright MLS...")
                mls_properties = mls_connector.get_properties(
                    area=self.area,
                    max_price=self.budget,
                    days_on_market=settings.MAX_DAYS_ON_MARKET,
                    property_types=settings.PROPERTY_TYPES
                )
                properties.extend(mls_properties)
                logger.info(f"Found {len(mls_properties)} properties from MLS")
            
            if self.data_source in ['redfin', 'both']:
                logger.info("Fetching property listings from Redfin...")
                redfin_properties = redfin_connector.get_properties(
                    location=self.area,
                    max_price=self.budget,
                    property_types=settings.PROPERTY_TYPES
                )
                properties.extend(redfin_properties)
                logger.info(f"Found {len(redfin_properties)} properties from Redfin")
            
            # De-duplicate properties if using both sources
            if self.data_source == 'both':
                unique_addresses = set()
                unique_properties = []
                
                for prop in properties:
                    if prop.address not in unique_addresses:
                        unique_addresses.add(prop.address)
                        unique_properties.append(prop)
                
                properties = unique_properties
                logger.info(f"After deduplication: {len(properties)} unique properties")
            
        except Exception as e:
            logger.error(f"Error fetching properties: {str(e)}")
            return []
        
        self.properties = properties
        return properties
    
    def enrich_properties(self):
        """Enrich properties with additional data"""
        logger.info("Enriching property data...")
        for prop in self.properties:
            # Add public records data
            public_records.enrich_property(prop)
            # Add market data
            market_data.add_comps(prop)
    
    def analyze_deals(self):
        """Analyze potential deals with current parameters"""
        logger.info("Analyzing potential deals...")
        deals = []
        
        # Update settings with current parameter values
        settings.REPAIR_COSTS['base_sqft_cost'] = self.repair_cost_per_sqft
        settings.REPAIR_COSTS['kitchen'] = self.kitchen_reno_cost
        settings.REPAIR_COSTS['bathroom'] = self.bathroom_reno_cost
        settings.AVERAGE_FLIP_MONTHS = self.flip_months
        settings.HOLDING_COSTS['mortgage_rate'] = self.mortgage_rate / 100
        
        for prop in self.properties:
            # Filter comps based on parameters
            filtered_comps = self.filter_comps(prop)
            prop.comps = filtered_comps
            
            # Skip if we don't have enough comps
            if len(filtered_comps) < 3:
                logger.warning(f"Not enough comps for {prop.address} after filtering. Skipping...")
                continue
            
            # Estimate repair costs
            repair_costs = deal_analyzer.estimate_repairs(prop)
            
            # Calculate ARV
            arv = self.calculate_arv(prop)
            
            # Calculate potential profit
            deal = deal_analyzer.analyze_deal(
                property_data=prop,
                arv=arv,
                repair_costs=repair_costs,
                min_roi=self.min_roi
            )
            
            # Add to deals list, even if it doesn't meet criteria
            deals.append(deal)
        
        self.deals = deals
        return deals
    
    def filter_comps(self, property_data: Property) -> List[Dict]:
        """Filter property comps based on current parameters"""
        if not property_data.comps:
            return []
        
        filtered_comps = []
        min_sqft = property_data.square_feet * self.min_comp_sqft_pct
        max_sqft = property_data.square_feet * self.max_comp_sqft_pct
        max_distance = self.use_comps_within_miles
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=self.max_comp_age_months * 30)).strftime('%Y-%m-%d')
        
        for comp in property_data.comps:
            if (comp['square_feet'] >= min_sqft and 
                comp['square_feet'] <= max_sqft and
                comp['distance'] <= max_distance and
                comp['sale_date'] >= cutoff_date):
                filtered_comps.append(comp)
        
        return filtered_comps
    
    def calculate_arv(self, property_data: Property) -> float:
        """Calculate After Repair Value based on filtered comps"""
        if not property_data.comps:
            logger.warning(f"No comparable properties found for {property_data.address}")
            # Fallback: assume a certain percentage increase over list price
            return property_data.list_price * 1.5
        
        # Extract price per square foot from comps
        comp_psf = [comp['price'] / comp['square_feet'] for comp in property_data.comps 
                    if comp.get('square_feet', 0) > 0]
        
        if not comp_psf:
            return property_data.list_price * 1.5
        
        # Remove outliers if specified
        if self.exclude_outliers and len(comp_psf) > 5:
            mean_psf = np.mean(comp_psf)
            std_psf = np.std(comp_psf)
            filtered_psf = [psf for psf in comp_psf if abs(psf - mean_psf) <= 2 * std_psf]
            
            if filtered_psf:
                avg_psf = np.mean(filtered_psf)
            else:
                avg_psf = mean_psf
        else:
            avg_psf = np.mean(comp_psf)
        
        # Calculate ARV based on average price per square foot
        arv = property_data.square_feet * avg_psf
        
        logger.info(f"Calculated ARV for {property_data.address}: ${arv:,.2f}")
        return arv
    
    def score_deals(self):
        """Score and rank deals using the current parameters"""
        self.scored_deals = property_scorer.score_deals(self.deals)
        
        # Convert to DataFrame for easier manipulation in Panel
        deal_data = []
        for deal in self.scored_deals:
            deal_row = {
                'Address': deal['address'],
                'List Price': deal['list_price'],
                'ARV': deal['arv'],
                'Repair Costs': deal['repair_costs'],
                'Closing Costs': deal['closing_costs'],
                'Holding Costs': deal['holding_costs'],
                'Total Cost': deal['total_project_cost'],
                'Profit': deal['potential_profit'],
                'ROI (%)': deal['roi'],
                'Score': deal['score'],
                'Meets 70% Rule': deal['meets_70_percent_rule'],
                'Max Purchase': deal['max_purchase_price'],
                'Beds': deal['property_data']['bedrooms'],
                'Baths': deal['property_data']['bathrooms'],
                'SqFt': deal['property_data']['square_feet'],
                'Year Built': deal['property_data']['year_built'],
                'DOM': deal['property_data']['days_on_market'],
                'Latitude': deal['property_data']['latitude'],
                'Longitude': deal['property_data']['longitude'],
                'Keywords': ', '.join(deal['property_data'].get('opportunity_keywords', []))
            }
            deal_data.append(deal_row)
        
        self.deal_df = pd.DataFrame(deal_data)
        
        # Also create a dataframe of all comps for visualization
        comp_data = []
        for prop in self.properties:
            for comp in prop.comps:
                comp_row = {
                    'Property': prop.address,
                    'Comp Address': comp['address'],
                    'Comp Price': comp['price'],
                    'Comp SqFt': comp['square_feet'],
                    'Price/SqFt': comp['price_per_sqft'],
                    'Distance': comp['distance'],
                    'Sale Date': comp['sale_date'],
                    'Used in ARV': self.is_comp_used(prop, comp)
                }
                comp_data.append(comp_row)
        
        self.comp_df = pd.DataFrame(comp_data)
        
        return self.deal_df
    
    def is_comp_used(self, property_data: Property, comp: Dict) -> bool:
        """Check if a comp was used in ARV calculation based on current filters"""
        min_sqft = property_data.square_feet * self.min_comp_sqft_pct
        max_sqft = property_data.square_feet * self.max_comp_sqft_pct
        max_distance = self.use_comps_within_miles
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=self.max_comp_age_months * 30)).strftime('%Y-%m-%d')
        
        return (comp['square_feet'] >= min_sqft and 
                comp['square_feet'] <= max_sqft and
                comp['distance'] <= max_distance and
                comp['sale_date'] >= cutoff_date)
    
    def export_excel(self):
        """Export results to Excel"""
        from utils import excel_exporter
        
        if not self.scored_deals:
            logger.warning("No deals to export")
            return False
        
        output_file = f"output/excel/potential_deals_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        result = excel_exporter.export_deals(self.scored_deals, output_file)
        
        if result:
            logger.info(f"Exported deals to: {output_file}")
        else:
            logger.error("Failed to export deals to Excel")
        
        return result
    
    def run_full_analysis(self):
        """Run the complete analysis pipeline"""
        # Get properties
        self.get_properties()
        
        if not self.properties:
            return pn.pane.Markdown("## No properties found matching criteria. Try adjusting search parameters.")
        
        # Enrich properties with additional data
        self.enrich_properties()
        
        # Analyze deals
        self.analyze_deals()
        
        # Score deals
        self.score_deals()
        
        # Update property detail view with new properties and select first property
        self.property_detail_view.update_property_list(self.properties, self.deals)
        if self.properties and self.deals:
            first_property = self.properties[0]
            self.property_detail_view.property_address = first_property.get_full_address()
            self.property_detail_view.select_property(first_property.get_full_address())
        
        if self.deal_df.empty:
            return pn.pane.Markdown("## No viable deals found. Try adjusting parameters.")
        
        return self.create_dashboard()
    
    def create_reactive_deal_table(self, columns, df):
        """Create a reactive deal table with editable columns"""
        # Define editable columns with their editor types
        editable_columns = {
            'List Price': 'number',
            'Repair Costs': 'number',
            'SqFt': 'number',
            'Beds': 'number',
            'Baths': 'number'
        }
        
        if not columns:
            columns = self.default_columns
        filtered_df = df[columns].copy()
        
        # Create column configurations
        column_configs = []
        
        # Add configurations for columns
        for col in columns:
            config = {
                "title": col,
                "field": col,
                "headerFilter": True,
                "resizable": True
            }
            
            if col == 'Address':
                config.update({
                    "formatter": "link",
                    "formatterParams": {
                        "labelField": "Address",
                        "target": "_self",
                        "urlPrefix": "#"
                    }
                })
            elif col in editable_columns:
                config["editor"] = editable_columns[col]
            
            column_configs.append(config)
        
        table = pn.widgets.Tabulator(
            filtered_df,
            pagination='remote',
            page_size=10,
            sizing_mode='stretch_width',
            selectable=1,
            header_filters=True,
            layout='fit_data_fill',
            theme='site',
            configuration={
                "columnDefaults": {
                    "headerFilter": True,
                    "resizable": True,
                },
                "columns": column_configs
            }
        )
        
        # Add callbacks for table
        if hasattr(table, 'on_edit'):
            table.on_edit(self.handle_cell_edit)
            
        # Add row click handler
        def on_click(event):
            if event.row is not None:
                # Get the row data using the index
                row_data = filtered_df.iloc[event.row]
                if 'Address' in row_data:
                    self.handle_row_click({'row': {'Address': row_data['Address']}})
                
        table.on_click(on_click)
        
        return table

    def create_dashboard(self):
        """Create the dashboard with current results"""
        if self.deal_df.empty:
            return pn.pane.Markdown("## No deals to display. Run analysis first.")

        # Define default columns to show in deal table
        default_columns = ['Address', 'List Price', 'ARV', 'Repair Costs', 'Profit', 'ROI (%)', 'Score']
        # All available columns for selection
        all_columns = self.deal_df.columns.tolist()
        
        # Create column selector widget
        column_selector = pn.widgets.MultiChoice(
            name='Select Columns to Display',
            value=default_columns,
            options=all_columns,
            solid=False,
            height=50
        )
        
        # Create the table with reactive updates
        deal_table = pn.bind(
            self.create_reactive_deal_table,
            columns=column_selector.param.value,
            df=self.deal_df
        )

        # Welcome content in its own tab
        welcome_content = pn.pane.Markdown("""
        # Welcome to Real Estate Flip Finder
        
        This tool helps you analyze potential real estate flip opportunities.
        
        ## Getting Started
        
        1. Go to the 'New Search' tab to set your parameters:
           - Enter your target ZIP code or area
           - Set your maximum purchase budget
           - Adjust ARV and repair cost settings if needed
        
        2. Click 'Run Analysis' to find properties
        
        3. Use the Deals tab to:
           - View all potential deals in table or map format
           - Sort and filter properties
           - Click on any property address for detailed analysis
        
        4. In the Property Details tab:
           - View comprehensive property information
           - Analyze ARV and repair costs
           - Calculate potential profit and ROI
           - Recalculate deals with custom parameters
        
        5. Additional Features:
           - ROI Analysis: Analyze return on investment distribution
           - Export to Excel: Save your analysis for offline review
        """)
        
        # Layout the deal table with column selector
        deal_table_layout = pn.Column(
            pn.Row(
                pn.pane.Markdown("## Deal Table"),
                column_selector
            ),
            deal_table,
            sizing_mode='stretch_width'
        )
        
        # Property map if we have coordinates
        if 'Latitude' in self.deal_df.columns and not self.deal_df['Latitude'].isna().all():
            tiles = hv.element.tiles.OSM()  # Create OpenStreetMap tile source
            points = self.deal_df.hvplot.points(
                'Longitude', 'Latitude',
                geo=True,
                hover_cols=['Address', 'List Price', 'ARV', 'Profit', 'ROI (%)', 'Score'],
                color='ROI (%)',
                colorbar=True,
                height=600,
                width=None,  # Let it stretch
                sizing_mode='stretch_width',
                title="Property Map",
                line_color='black',
                size=10,
                alpha=0.8,
                clabel='ROI (%)'
            )
            property_map = (tiles * points).opts(
                width=800,
                height=600,
                tools=['hover', 'tap', 'zoom_in', 'zoom_out', 'reset', 'pan'],
                active_tools=['pan', 'wheel_zoom']
            )
        else:
            property_map = pn.pane.Markdown("## No location data available for mapping")

        # Create deals view with table and map tabs
        deals_view = pn.Column(
            pn.Tabs(
                ('Table View', deal_table_layout),
                ('Map View', property_map)
            ),
            sizing_mode='stretch_width'
        )
        
        # ROI distribution
        roi_hist = self.deal_df.hvplot.hist(
            'ROI (%)', 
            bins=20, 
            height=300,
            width=500,
            title="ROI Distribution"
        )
        
        # Create property detail view
        property_detail = self.create_property_detail_view()
        
        # Update property selector options in detail view
        self.property_detail_view.update_property_list(self.properties, self.deals)

        # Create the search parameters panel
        input_params = pn.Param(
            self.param, 
            parameters=['area', 'budget', 'min_roi', 'data_source', 'run_analysis', 'export_to_excel'],
            name="Search Parameters",
            show_name=True,
            default_layout=pn.Column
        )

        arv_params = pn.Param(
            self.param,
            parameters=['use_comps_within_miles', 'max_comp_age_months', 'min_comp_sqft_pct', 
                       'max_comp_sqft_pct', 'exclude_outliers'],
            name="ARV Calculation Parameters",
            show_name=True,
            default_layout=pn.Column
        )

        cost_params = pn.Param(
            self.param,
            parameters=['repair_cost_per_sqft', 'kitchen_reno_cost', 'bathroom_reno_cost', 
                       'flip_months', 'mortgage_rate'],
            name="Cost & Timeline Parameters",
            show_name=True,
            default_layout=pn.Column
        )

        # Create the search panel
        search_panel = pn.Column(
            pn.pane.Markdown("# New Search"),
            pn.Accordion(
                ('Search Parameters', input_params),
                ('ARV Settings', arv_params),
                ('Cost Settings', cost_params)
            ),
            sizing_mode='stretch_width'
        )
        
        # Create the dashboard layout with tabs
        dashboard = pn.Column(
            pn.Tabs(
                ('Welcome', welcome_content),
                ('Deals', deals_view),
                ('ROI Analysis', roi_hist),
                ('Property Details', property_detail),
                ('New Search', search_panel)
            ),
            sizing_mode='stretch_width'
        )
        
        # Store reference to the dashboard
        self.dashboard = dashboard
        
        return dashboard

    def create_property_detail_view(self):
        """Create the individual property detail view"""
        # Create property selector and recalculate button in a row
        property_selector = pn.Param(
            self.property_detail_view.param.property_address,
            widgets={
                'property_address': {'width': 400}
            }
        )
        
        recalc_button = pn.Param(
            self.property_detail_view.param.recalculate_deal,
            default_layout=pn.Column
        )
        
        # Function to generate comprehensive deal analysis
        def property_analysis():
            if not self.property_detail_view.selected_property or not self.property_detail_view.selected_deal:
                return pn.pane.Markdown("Select a property to view details")
            
            prop = self.property_detail_view.selected_property
            deal = self.property_detail_view.selected_deal

            # Create KPI cards with CSS styling
            kpi_style = """
            .kpi-card {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .kpi-title {
                font-size: 14px;
                color: #666;
                margin-bottom: 5px;
            }
            .kpi-value {
                font-size: 18px;
                font-weight: bold;
                color: #333;
            }
            """

            # Property Information KPIs
            property_info = pn.Column(
                pn.pane.HTML(f"<style>{kpi_style}</style>"),
                pn.pane.Markdown("### Property Information"),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Address</div>
                        <div class="kpi-value">{prop.address}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Location</div>
                        <div class="kpi-value">{prop.city}, {prop.state} {prop.zip_code}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Bedrooms</div>
                        <div class="kpi-value">{prop.bedrooms}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Bathrooms</div>
                        <div class="kpi-value">{prop.bathrooms}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Square Feet</div>
                        <div class="kpi-value">{prop.square_feet:,.0f}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Year Built</div>
                        <div class="kpi-value">{prop.year_built}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Days on Market</div>
                        <div class="kpi-value">{prop.days_on_market}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                sizing_mode='stretch_width'
            )

            # Financial Metrics KPIs
            financial_metrics = pn.Column(
                pn.pane.Markdown("### Financial Metrics"),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">List Price</div>
                        <div class="kpi-value">${deal['list_price']:,.2f}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Price/SqFt</div>
                        <div class="kpi-value">${prop.price_per_sqft:.2f}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">After Repair Value</div>
                        <div class="kpi-value">${deal['arv']:,.2f}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                sizing_mode='stretch_width'
            )

            # Cost Analysis KPIs
            cost_analysis = pn.Column(
                pn.pane.Markdown("### Cost Analysis"),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Repair Costs</div>
                        <div class="kpi-value">${deal['repair_costs']:,.2f}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Closing Costs</div>
                        <div class="kpi-value">${deal['closing_costs']:,.2f}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Holding Costs</div>
                        <div class="kpi-value">${deal['holding_costs']:,.2f}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Total Project Cost</div>
                        <div class="kpi-value">${deal['total_project_cost']:,.2f}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-title">Maximum Purchase Price</div>
                        <div class="kpi-value">${deal['max_purchase_price']:,.2f}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                sizing_mode='stretch_width'
            )

            # Deal Analysis KPIs
            deal_analysis = pn.Column(
                pn.pane.Markdown("### Deal Analysis"),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Potential Profit</div>
                        <div class="kpi-value">${deal['potential_profit']:,.2f}</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">ROI</div>
                        <div class="kpi-value">{deal['roi']:.2f}%</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Score</div>
                        <div class="kpi-value">{deal['score']:.2f}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Meets 70% Rule</div>
                        <div class="kpi-value">{"Yes" if deal['meets_70_percent_rule'] else "No"}</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                sizing_mode='stretch_width'
            )

            # Keywords section
            keywords = pn.Column(
                pn.pane.Markdown("### Property Keywords"),
                pn.pane.HTML(f"""
                <div class="kpi-card">
                    <div class="kpi-value">{', '.join(prop.opportunity_keywords)}</div>
                </div>
                """),
                sizing_mode='stretch_width'
            )

            # Create collapsible sections using Accordion
            accordion = pn.Accordion(
                ('Property Information', property_info),
                ('Financial Metrics', financial_metrics),
                ('Cost Analysis', cost_analysis),
                ('Deal Analysis', deal_analysis),
                ('Keywords', keywords),
                active=[0],  # Keep first panel open by default
                sizing_mode='stretch_width'
            )

            return pn.Column(
                pn.pane.Markdown("# Property Analysis"),
                accordion,
                sizing_mode='stretch_width'
            )
            
        # Create ARV tab content
        def arv_tab():
            if not self.property_detail_view.selected_deal:
                return pn.pane.Markdown("Select a property to view ARV analysis")
                
            deal = self.property_detail_view.selected_deal
            
            arv_summary = pn.pane.Markdown(f"""
            # ARV Analysis
            ## Estimated After Repair Value: ${deal['arv']:,.2f}
            
            Adjust the parameters below to recalculate ARV:
            """)
            
            arv_params = pn.Param(
                self.property_detail_view.param,
                parameters=['use_comps_within_miles', 'max_comp_age_months', 
                            'min_comp_sqft_pct', 'max_comp_sqft_pct', 'exclude_outliers'],
                name="ARV Calculation Parameters",
                default_layout=pn.Column
            )
            
            # Create comp data table
            comp_table = pn.widgets.Tabulator(
                self.property_detail_view.comp_df,
                pagination='remote',
                page_size=10,
                sizing_mode='stretch_width',
                header_filters=True,
                height=300
            )
            
            return pn.Column(
                arv_summary,
                pn.Accordion(('ARV Settings', arv_params)),
                pn.pane.Markdown("### Comparable Properties"),
                comp_table
            )
            
        # Create Repair tab content
        def repair_tab():
            if not self.property_detail_view.selected_deal:
                return pn.pane.Markdown("Select a property to view repair estimates")
                
            deal = self.property_detail_view.selected_deal
            
            repair_summary = pn.pane.Markdown(f"""
            # Repair Cost Analysis
            ## Total Repair Estimate: ${deal['repair_costs']:,.2f}
            
            Adjust the parameters below to recalculate repair costs:
            """)
            
            repair_params = pn.Param(
                self.property_detail_view.param,
                parameters=['repair_cost_per_sqft', 'kitchen_reno_cost', 'bathroom_reno_cost',
                           'roof_repair', 'hvac_repair', 'electrical_work', 'plumbing_work'],
                name="Repair Cost Parameters",
                default_layout=pn.Column
            )
            
            return pn.Column(
                repair_summary,
                repair_params
            )
            
        # Create Holding Costs tab content
        def holding_tab():
            if not self.property_detail_view.selected_deal:
                return pn.pane.Markdown("Select a property to view holding costs")
                
            deal = self.property_detail_view.selected_deal
            
            holding_summary = pn.pane.Markdown(f"""
            # Holding & Closing Cost Analysis
            ## Total Holding Costs: ${deal['holding_costs']:,.2f}
            ## Total Closing Costs: ${deal['closing_costs']:,.2f}
            
            Adjust the parameters below to recalculate costs:
            """)
            
            holding_params = pn.Param(
                self.property_detail_view.param,
                parameters=['flip_months', 'mortgage_rate'],
                name="Holding Cost Parameters",
                default_layout=pn.Column
            )
            
            return pn.Column(
                holding_summary,
                holding_params
            )
            
        # Create the layout
        analysis_pane = pn.bind(property_analysis)
        arv_pane = pn.bind(arv_tab)
        repair_pane = pn.bind(repair_tab)
        holding_pane = pn.bind(holding_tab)
        
        # Layout the property detail view
        header = pn.Row(
            pn.Column(property_selector, width=400),
            pn.Column(recalc_button, width=200),
            sizing_mode='stretch_width'
        )

        # Create deal summary KPIs
        def deal_summary():
            if not self.property_detail_view.selected_property or not self.property_detail_view.selected_deal:
                return pn.pane.Markdown("")
            
            deal = self.property_detail_view.selected_deal
            
            kpi_style = """
            .sticky-container {
                position: sticky;
                top: 0;
                z-index: 100;
                background-color: white;
                padding: 10px 0;
                border-bottom: 1px solid #e0e0e0;
                margin-bottom: 20px;
            }
            .summary-kpi {
                background-color: #ffffff;
                border-radius: 10px;
                padding: 20px;
                margin: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                text-align: center;
                border: 1px solid #e0e0e0;
            }
            .summary-title {
                font-size: 16px;
                color: #666;
                margin-bottom: 10px;
                text-transform: uppercase;
            }
            .summary-value {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
            }
            .summary-subtitle {
                font-size: 14px;
                color: #999;
                margin-top: 5px;
            }
            """

            summary = pn.Column(
                pn.pane.HTML(f"<style>{kpi_style}</style>"),
                pn.pane.HTML("""
                <div class="sticky-container">
                """),
                pn.Row(
                    pn.pane.HTML(f"""
                    <div class="summary-kpi">
                        <div class="summary-title">Maximum Offer</div>
                        <div class="summary-value">${deal['max_purchase_price']:,.0f}</div>
                        <div class="summary-subtitle">70% Rule Price</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="summary-kpi">
                        <div class="summary-title">List Price</div>
                        <div class="summary-value">${deal['list_price']:,.0f}</div>
                        <div class="summary-subtitle">Current Ask</div>
                    </div>
                    """),
                    pn.pane.HTML(f"""
                    <div class="summary-kpi">
                        <div class="summary-title">Expected Profit</div>
                        <div class="summary-value">${deal['potential_profit']:,.0f}</div>
                        <div class="summary-subtitle">ROI: {deal['roi']:.1f}%</div>
                    </div>
                    """),
                    sizing_mode='stretch_width'
                ),
                pn.pane.HTML("</div>"),
                sizing_mode='stretch_width'
            )
            return summary

        # Create the layout with new organization
        detail_panel = pn.Column(
            header,
            pn.bind(deal_summary),  # Deal summary KPIs at top (now sticky)
            pn.Column(  # Scrollable content below
                pn.Column(  # Property details in own row
                    pn.bind(property_analysis),
                    sizing_mode='stretch_width',
                    margin=(20, 0)  # Add some vertical spacing
                ),
                pn.Column(  # Parameter tabs below
                    pn.Tabs(
                        ('ARV Analysis', arv_pane),
                        ('Repair Costs', repair_pane),
                        ('Holding & Closing', holding_pane)
                    ),
                    sizing_mode='stretch_width'
                ),
                sizing_mode='stretch_width'
            ),
            sizing_mode='stretch_both'
        )
        
        # Property change callback
        def on_property_change(event):
            if event.new:
                self.property_detail_view.select_property(event.new)
                
        self.property_detail_view.param.watch(on_property_change, 'property_address')
        
        # Recalculate callback
        def on_recalculate(event):
            if event.name == 'recalculate_deal':
                self.property_detail_view.recalculate_property_deal()
                
        self.property_detail_view.param.watch(on_recalculate, 'recalculate_deal')
        
        return detail_panel

    def handle_cell_edit(self, event):
        """Handle edits to the deal table cells"""
        address = event.row['Address']
        column = event.column
        new_value = event.value
        
        # Find the corresponding property and deal
        for i, prop in enumerate(self.properties):
            if prop.get_full_address() == address:
                # Update property data
                if column == 'List Price':
                    prop.list_price = float(new_value)
                elif column == 'SqFt':
                    prop.square_feet = float(new_value)
                elif column == 'Beds':
                    prop.bedrooms = int(new_value)
                elif column == 'Baths':
                    prop.bathrooms = float(new_value)
                
                # Find and update the deal
                for j, deal in enumerate(self.deals):
                    if deal['address'] == address:
                        if column == 'Repair Costs':
                            deal['repair_costs'] = float(new_value)
                        # Recalculate the deal
                        updated_deal = deal_analyzer.analyze_deal(
                            property_data=prop,
                            arv=deal['arv'],
                            repair_costs=deal['repair_costs'],
                            min_roi=self.min_roi
                        )
                        self.deals[j] = updated_deal
                        break
                
                # Rescore deals and update dataframe
                self.score_deals()
                break

    def handle_row_click(self, event):
        """Handle clicks on deal table rows"""
        address = event['row']['Address']
        self.property_detail_view.property_address = address
        self.property_detail_view.select_property(address)
        # Switch to the Property Details tab
        for tab in self.dashboard.objects:
            if isinstance(tab, pn.Tabs):
                tab.active = 3  # Index of Property Details tab

# Create the dashboard app and initialize with sample data
dashboard = FlipFinderDashboard()

# Parameter update callback
def update_analysis(event):
    if event.name == 'run_analysis':
        spinner = pn.indicators.LoadingSpinner(value=True)
        main.clear()
        main.append(spinner)
        try:
            result = dashboard.run_full_analysis()
            if isinstance(result, pn.viewable.Viewable):
                main.clear()
                main.append(result)
        finally:
            spinner.value = False
    elif event.name == 'export_to_excel':
        dashboard.export_excel()

# Watch for parameter changes
dashboard.param.watch(update_analysis, ['run_analysis', 'export_to_excel'])

# Run initial analysis
initial_result = dashboard.run_full_analysis()

# Create initial welcome content
welcome_content = pn.Column(
    pn.pane.Markdown("## Welcome to Real Estate Flip Finder"),
    pn.pane.Markdown("""
    This tool helps you analyze potential real estate flip opportunities.
    
    To get started:
    1. Go to the 'New Search' tab to set your parameters
    2. Click 'Run Analysis' to find properties
    3. Use the table and visualizations to analyze deals
    4. Click on any property address for detailed analysis
    """),
    sizing_mode='stretch_width'
)

# Create the main area with initial analysis
main = pn.Column(sizing_mode='stretch_both')

# Initialize main with initial analysis result
if isinstance(initial_result, pn.viewable.Viewable):
    main.clear()
    main.append(initial_result)

# Create the template with proper sizing
template = pn.template.MaterialTemplate(
    title='Real Estate Flip Finder',
    main=main,
    header_background='#007bff',
    header_color='white',
    busy_indicator=pn.indicators.LoadingSpinner(value=True),
)

# Make the app servable
template.servable()

# For development
if __name__ == "__main__":
    # Run initial analysis before showing
    initial_result = dashboard.run_full_analysis()
    if isinstance(initial_result, pn.viewable.Viewable):
        main.clear()
        main.append(initial_result)
    template.show()
