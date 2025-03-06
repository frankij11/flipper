"""
Dashboard - Create interactive visualizations for property analysis
"""

import logging
import pandas as pd
import json
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

def generate_dashboard(deals: List[Dict[str, Any]], output_file: str) -> bool:
    """
    Generate an HTML dashboard with property analysis visualizations
    
    Args:
        deals: List of analyzed property deals
        output_file: Path to save the HTML dashboard
        
    Returns:
        Boolean indicating success
    """
    try:
        if not deals:
            logger.warning("No deals to visualize")
            return False
        
        # Create a basic HTML template with placeholders for our data
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Real Estate Flip Finder Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/leaflet@1.7.1/dist/leaflet.js"></script>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.7.1/dist/leaflet.css">
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
                h1, h2 { color: #333; }
                .dashboard-container { display: flex; flex-wrap: wrap; }
                .chart-container { width: 48%; margin: 1%; height: 300px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                .full-width { width: 98%; }
                .property-list { margin-top: 20px; }
                .property-card { border: 1px solid #ddd; padding: 15px; margin-bottom: 10px; border-radius: 5px; }
                .property-header { display: flex; justify-content: space-between; }
                .property-title { font-weight: bold; }
                .property-score { font-weight: bold; color: #4CAF50; }
                .property-details { display: flex; flex-wrap: wrap; margin-top: 10px; }
                .property-detail { width: 25%; margin-bottom: 5px; }
                .map-container { height: 400px; width: 98%; margin: 1%; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
                tr:hover { background-color: #f5f5f5; }
            </style>
        </head>
        <body>
            <h1>Real Estate Flip Finder Dashboard</h1>
            
            <div class="dashboard-container">
                <div class="chart-container">
                    <canvas id="profitChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="roiChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="repairCostChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="scoreChart"></canvas>
                </div>
                <div id="mapContainer" class="map-container"></div>
            </div>
            
            <h2>Top Properties</h2>
            <div class="property-list" id="propertyList">
                <!-- Property cards will be inserted here -->
            </div>
            
            <h2>Deal Comparison</h2>
            <table id="dealTable">
                <tr>
                    <th>Address</th>
                    <th>List Price</th>
                    <th>ARV</th>
                    <th>Repair Cost</th>
                    <th>Total Cost</th>
                    <th>Profit</th>
                    <th>ROI</th>
                    <th>Score</th>
                </tr>
                <!-- Table rows will be inserted here -->
            </table>
            
            <script>
                // Data from Python
                const dealsData = DEALS_JSON_PLACEHOLDER;
                
                // Create property cards
                const propertyListEl = document.getElementById('propertyList');
                dealsData.slice(0, 5).forEach(deal => {
                    const card = document.createElement('div');
                    card.className = 'property-card';
                    card.innerHTML = `
                        <div class="property-header">
                            <div class="property-title">${deal.address}</div>
                            <div class="property-score">Score: ${deal.score.toFixed(1)}</div>
                        </div>
                        <div class="property-details">
                            <div class="property-detail">List: $${deal.list_price.toLocaleString()}</div>
                            <div class="property-detail">ARV: $${deal.arv.toLocaleString()}</div>
                            <div class="property-detail">Repair: $${deal.repair_costs.toLocaleString()}</div>
                            <div class="property-detail">Profit: $${deal.potential_profit.toLocaleString()}</div>
                            <div class="property-detail">ROI: ${deal.roi.toFixed(1)}%</div>
                        </div>
                    `;
                    propertyListEl.appendChild(card);
                });
                
                // Create table rows
                const tableEl = document.getElementById('dealTable');
                dealsData.forEach(deal => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${deal.address}</td>
                        <td>$${deal.list_price.toLocaleString()}</td>
                        <td>$${deal.arv.toLocaleString()}</td>
                        <td>${deal.repair_costs.toLocaleString()}</td>
                        <td>${deal.total_project_cost.toLocaleString()}</td>
                        <td>${deal.potential_profit.toLocaleString()}</td>
                        <td>${deal.roi.toFixed(1)}%</td>
                        <td>${deal.score.toFixed(1)}</td>
                    `;
                    tableEl.appendChild(row);
                });
                
                // Profit Chart
                const profitCtx = document.getElementById('profitChart').getContext('2d');
                new Chart(profitCtx, {
                    type: 'bar',
                    data: {
                        labels: dealsData.slice(0, 10).map(deal => deal.address.split(',')[0]),
                        datasets: [{
                            label: 'Potential Profit',
                            data: dealsData.slice(0, 10).map(deal => deal.potential_profit),
                            backgroundColor: 'rgba(54, 162, 235, 0.5)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Potential Profit by Property'
                            }
                        }
                    }
                });
                
                // ROI Chart
                const roiCtx = document.getElementById('roiChart').getContext('2d');
                new Chart(roiCtx, {
                    type: 'bar',
                    data: {
                        labels: dealsData.slice(0, 10).map(deal => deal.address.split(',')[0]),
                        datasets: [{
                            label: 'ROI (%)',
                            data: dealsData.slice(0, 10).map(deal => deal.roi),
                            backgroundColor: 'rgba(75, 192, 192, 0.5)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'ROI by Property'
                            }
                        }
                    }
                });
                
                // Repair Cost Chart
                const repairCtx = document.getElementById('repairCostChart').getContext('2d');
                new Chart(repairCtx, {
                    type: 'bar',
                    data: {
                        labels: dealsData.slice(0, 10).map(deal => deal.address.split(',')[0]),
                        datasets: [{
                            label: 'Repair Costs',
                            data: dealsData.slice(0, 10).map(deal => deal.repair_costs),
                            backgroundColor: 'rgba(255, 99, 132, 0.5)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Repair Costs by Property'
                            }
                        }
                    }
                });
                
                // Score Chart
                const scoreCtx = document.getElementById('scoreChart').getContext('2d');
                new Chart(scoreCtx, {
                    type: 'bar',
                    data: {
                        labels: dealsData.slice(0, 10).map(deal => deal.address.split(',')[0]),
                        datasets: [{
                            label: 'Property Score',
                            data: dealsData.slice(0, 10).map(deal => deal.score),
                            backgroundColor: 'rgba(153, 102, 255, 0.5)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Property Score'
                            }
                        }
                    }
                });
                
                // Initialize map if we have properties with coordinates
                if (dealsData.some(deal => 
                    deal.property_data.latitude && 
                    deal.property_data.longitude &&
                    deal.property_data.latitude !== 0 &&
                    deal.property_data.longitude !== 0)) {
                    
                    const map = L.map('mapContainer').setView([dealsData[0].property_data.latitude, dealsData[0].property_data.longitude], 12);
                    
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    }).addTo(map);
                    
                    dealsData.forEach(deal => {
                        if (deal.property_data.latitude && 
                            deal.property_data.longitude &&
                            deal.property_data.latitude !== 0 &&
                            deal.property_data.longitude !== 0) {
                                
                            L.marker([deal.property_data.latitude, deal.property_data.longitude])
                                .addTo(map)
                                .bindPopup(
                                    '<b>' + deal.address + '</b><br>' +
                                    'List:  + deal.list_price.toLocaleString() + '<br>' +
                                    'Profit:  + deal.potential_profit.toLocaleString() + '<br>' +
                                    'ROI: ' + deal.roi.toFixed(1) + '%'
                                );
                        }
                    });
                } else {
                    document.getElementById('mapContainer').innerHTML = '<p>No valid property coordinates available for mapping</p>';
                }
            </script>
        </body>
        </html>
        """
        
        # Convert deals to JSON for embedding in HTML
        deals_json = json.dumps([{
            'address': deal['address'],
            'list_price': deal['list_price'],
            'arv': deal['arv'],
            'repair_costs': deal['repair_costs'],
            'total_project_cost': deal['total_project_cost'],
            'potential_profit': deal['potential_profit'],
            'roi': deal['roi'],
            'score': deal['score'],
            'property_data': deal['property_data']
        } for deal in deals])
        
        # Replace placeholder with actual JSON data
        html_content = html_template.replace('DEALS_JSON_PLACEHOLDER', deals_json)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Write HTML to file
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Dashboard generated and saved to {output_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error generating dashboard: {str(e)}")
        return False