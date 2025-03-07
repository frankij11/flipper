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
class FlipFinderDashboard(param.Parameterized):
    """Interactive dashboard for Real Estate Flip Finder"""
    
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
        
    def get_properties(self):
        """Get properties from selected data source"""
        properties = []
        
        if self.data_source in ['mls', 'both']:
            logger.info("Fetching property listings from Bright MLS...")
            try:
                mls_properties = mls_connector.get_properties(
                    area=self.area,
                    max_price=self.budget,
                    days_on_market=settings.MAX_DAYS_ON_MARKET,
                    property_types=settings.PROPERTY_TYPES
                )
                properties.extend(mls_properties)
                logger.info(f"Found {len(mls_properties)} properties from MLS matching initial criteria")
            except Exception as e:
                logger.error(f"Error fetching MLS properties: {str(e)}")
        
        if self.data_source in ['redfin', 'both']:
            logger.info("Fetching property listings from Redfin...")
            try:
                redfin_properties = redfin_connector.get_properties(
                    location=self.area,
                    max_price=self.budget,
                    property_types=settings.PROPERTY_TYPES
                )
                properties.extend(redfin_properties)
                logger.info(f"Found {len(redfin_properties)} properties from Redfin matching initial criteria")
            except Exception as e:
                logger.error(f"Error fetching Redfin properties: {str(e)}")
        
        # De-duplicate properties if using both sources (simple deduplication by address)
        if self.data_source == 'both':
            unique_addresses = set()
            unique_properties = []
            
            for prop in properties:
                if prop.address not in unique_addresses:
                    unique_addresses.add(prop.address)
                    unique_properties.append(prop)
            
            logger.info(f"After deduplication: {len(unique_properties)} unique properties")
            properties = unique_properties
        
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
        
        if self.deal_df.empty:
            return pn.pane.Markdown("## No viable deals found. Try adjusting parameters.")
        
        return self.create_dashboard()
    
    def create_dashboard(self):
        """Create the dashboard with current results"""
        if self.deal_df.empty:
            return pn.pane.Markdown("## No deals to display. Run analysis first.")
        
        # Summary statistics
        total_props = len(self.properties)
        viable_deals = len([d for d in self.deals if d['meets_criteria']])
        avg_roi = self.deal_df['ROI (%)'].mean()
        avg_profit = self.deal_df['Profit'].mean()
        
        summary = pn.pane.Markdown(f"""
        ## Analysis Summary
        - **Total Properties Analyzed**: {total_props}
        - **Viable Deals (>={self.min_roi}% ROI)**: {viable_deals}
        - **Average ROI**: {avg_roi:.2f}%
        - **Average Profit**: ${avg_profit:,.2f}
        """)
        
        # Create deal table
        deal_table = pn.widgets.Tabulator(
            self.deal_df,
            pagination='remote',
            page_size=10,
            sizing_mode='stretch_width',
            selectable=True,
            header_filters=True,
            layout='fit_columns',
            theme='site',
            configuration={
                "columnDefaults": {
                    "headerFilter": True,
                    "resizable": True,
                },
            },
        )
        
        # Property map if we have coordinates
        if 'Latitude' in self.deal_df.columns and not self.deal_df['Latitude'].isna().all():
            property_map = self.deal_df.hvplot.points(
                'Longitude', 'Latitude', 
                color='ROI (%)', 
                hover_cols=['Address', 'List Price', 'ARV', 'Profit', 'ROI (%)', 'Score'],
                colorbar=True,
                height=500,
                width=700,
                tools=['hover', 'tap', 'zoom_in', 'zoom_out', 'reset'],
                title="Property Map"
            )
        else:
            property_map = pn.pane.Markdown("## No location data available for mapping")
        
        # ROI distribution
        roi_hist = self.deal_df.hvplot.hist(
            'ROI (%)', 
            bins=20, 
            height=300,
            width=500,
            title="ROI Distribution"
        )
        
        # Profit vs ROI scatter
        profit_roi_scatter = self.deal_df.hvplot.scatter(
            'Profit', 'ROI (%)',
            color='Score',
            size=80,
            alpha=0.7,
            hover_cols=['Address', 'List Price'],
            height=400,
            width=500,
            colorbar=True,
            title="Profit vs ROI"
        )
        
        # Repair cost vs Profit
        repair_profit_scatter = self.deal_df.hvplot.scatter(
            'Repair Costs', 'Profit',
            color='ROI (%)',
            size=80,
            alpha=0.7,
            hover_cols=['Address', 'List Price'],
            height=400,
            width=500,
            colorbar=True,
            title="Repair Costs vs Profit"
        )
        
        # Top properties by score
        top_deals = self.deal_df.sort_values('Score', ascending=False).head(10)
        top_deals_chart = top_deals.hvplot.bar(
            'Address', 'Score',
            title="Top 10 Properties by Score",
            height=400,
            width=700,
            rot=45
        )
        
        # Comps visualization if we have comp data
        if not self.comp_df.empty:
            comp_scatter = self.comp_df.hvplot.scatter(
                'Comp SqFt', 'Price/SqFt',
                by='Used in ARV',
                hover_cols=['Property', 'Comp Address', 'Comp Price', 'Distance', 'Sale Date'],
                height=400,
                width=500,
                alpha=0.7,
                title="Comp Analysis: Price/SqFt vs SqFt"
            )
            
            # Price distribution of comps
            comp_price_hist = self.comp_df.hvplot.hist(
                'Price/SqFt',
                by='Used in ARV',
                bins=20,
                height=300,
                width=500,
                alpha=0.7,
                title="Comp Price/SqFt Distribution"
            )
            
            comp_tabs = pn.Tabs(
                ('Comp Scatter', comp_scatter),
                ('Comp Price Distribution', comp_price_hist)
            )
        else:
            comp_tabs = pn.pane.Markdown("## No comp data available")
        
        # Organize dashboard components
        dashboard = pn.Column(
            summary,
            pn.Tabs(
                ('Deal Table', deal_table),
                ('Property Map', property_map),
                ('Top Properties', top_deals_chart),
                ('ROI Analysis', pn.Row(roi_hist, profit_roi_scatter)),
                ('Repair Analysis', pn.Row(repair_profit_scatter, pn.Column())),
                ('Comp Analysis', comp_tabs)
            )
        )
        
        return dashboard

# Create the dashboard app
dashboard = FlipFinderDashboard()

# Define the parameter panels
input_params = pn.Param(
    dashboard.param, 
    parameters=['area', 'budget', 'min_roi', 'data_source', 'run_analysis', 'export_to_excel'],
    name="Search Parameters",
    show_name=True,
    default_layout=pn.Column
)

arv_params = pn.Param(
    dashboard.param,
    parameters=['use_comps_within_miles', 'max_comp_age_months', 'min_comp_sqft_pct', 
               'max_comp_sqft_pct', 'exclude_outliers'],
    name="ARV Calculation Parameters",
    show_name=True,
    default_layout=pn.Column
)

cost_params = pn.Param(
    dashboard.param,
    parameters=['repair_cost_per_sqft', 'kitchen_reno_cost', 'bathroom_reno_cost', 
               'flip_months', 'mortgage_rate'],
    name="Cost & Timeline Parameters",
    show_name=True,
    default_layout=pn.Column
)

# Define the sidebar
sidebar = pn.Column(
    pn.pane.Markdown("# Real Estate Flip Finder"),
    pn.pane.Markdown("## Parameters"),
    pn.Accordion(
        ('Search', input_params),
        ('ARV Settings', arv_params),
        ('Cost Settings', cost_params)
    )
)

# Parameter update callback
def update_analysis(event):
    if event.name == 'run_analysis':
        dashboard.run_full_analysis()
    elif event.name == 'export_to_excel':
        dashboard.export_excel()

dashboard.param.watch(update_analysis, ['run_analysis', 'export_to_excel'])

# Create the main layout
main = pn.Column(
    pn.pane.Markdown("## Click 'Run Analysis' to start"),
    pn.bind(dashboard.run_full_analysis)
)

# Create the app
app = pn.template.BootstrapTemplate(
    site="Real Estate Flip Finder",
    title="Real Estate Flip Finder Dashboard",
    sidebar=sidebar,
    main=main
)

app.servable()

# For local development
#if __name__ == "__main__":
#    app.servable()
