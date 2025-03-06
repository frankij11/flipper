# Real Estate Flip Finder

A Python-based tool for finding, analyzing, and scoring real estate properties for flipping.

## Overview

Real Estate Flip Finder automatically pulls property data from Bright MLS, Redfin, and other sources, analyzes potential flip opportunities, and ranks them based on profitability, ROI, and other factors. It helps investors quickly identify the most promising properties and make data-driven decisions.

## Features

- MLS data integration with Bright MLS
- Redfin data access through unofficial API
- Property scoring algorithm based on profitability and ROI
- Repair cost estimation
- After Repair Value (ARV) calculation using comparable sales
- Deal analysis using the 70% rule and other metrics
- Interactive visualizations and dashboards
- Excel exports for detailed analysis
- Email notifications for new opportunities

## Installation

1. Clone the repository
2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Configure your API credentials in `config/credentials.py`

## Usage

Basic usage:

```
python main.py --area "20878" --budget 400000 --roi 20 --source redfin --export --visualize
```

Command line options:

- `--area`: Target ZIP code or city
- `--budget`: Maximum purchase budget
- `--roi`: Minimum ROI percentage (default: 20.0)
- `--source`: Data source to use (mls, redfin, or both)
- `--export`: Export results to Excel
- `--notify`: Send email notification with results
- `--visualize`: Generate visualizations

## Data Sources

### Bright MLS
Requires valid MLS credentials for API access. This is the primary source for accurate, up-to-date listing data.

### Redfin
Uses an unofficial API to access Redfin property data. No credentials required, but be aware:
- Data may be less comprehensive than MLS
- API endpoints may change without notice
- Usage should comply with Redfin's terms of service
- Request frequency should be limited to avoid IP blocking

## Project Structure

- `config/`: Configuration settings and credentials
- `data/`: Data connectors for MLS, Redfin and other sources
- `analysis/`: Analysis algorithms and scoring
- `visualization/`: Data visualization tools
- `utils/`: Utility functions
- `models/`: Data models for properties and deals

## Example

Finding properties in ZIP code 20878 with a budget of $400,000 using Redfin:

```
python main.py --area "20878" --budget 400000 --source redfin --export --visualize
```

This will:
1. Search for properties in ZIP 20878 under $400,000 on Redfin
2. Analyze potential profit and ROI for each property
3. Export results to Excel
4. Generate an HTML dashboard

## Extending the Project

### Adding New Data Sources

To add a new data source:
1. Create a new module in the `data/` directory
2. Implement functions to fetch and process the data
3. Integrate the prediction model into the scoring algorithm

## Managing Data Sources

### Using Multiple Data Sources

The application supports getting property data from multiple sources simultaneously:

```
python main.py --area "20878" --budget 400000 --source both --export
```

When using multiple sources, the application will:
1. Collect data from all selected sources
2. Deduplicate properties based on address
3. Process and analyze the combined dataset

### Data Source Comparison

| Feature | Bright MLS | Redfin |
|---------|------------|--------|
| Data completeness | High | Medium |
| Property details | Comprehensive | Good |
| API reliability | High (with credentials) | Medium (unofficial) |
| Historical data | Available | Limited |
| Usage limitations | By MLS subscription | Web scraping limits |

## License

This project is licensed under the MIT License - see the LICENSE file for details. with the main analysis workflow

### Customizing the Scoring Algorithm

The property scoring algorithm can be modified in `analysis/property_scorer.py` to adjust weights or add new scoring factors based on your specific investment criteria.

### Adding Machine Learning Capabilities

For advanced users, consider adding machine learning capabilities:
1. Create a historic database of flips
2. Train a model to predict profitable properties
3. Integrate# Real Estate Flip Finder

A Python-based tool for finding, analyzing, and scoring real estate properties for flipping.

## Overview

Real Estate Flip Finder automatically pulls property data from Bright MLS and other sources, analyzes potential flip opportunities, and ranks them based on profitability, ROI, and other factors. It helps investors quickly identify the most promising properties and make data-driven decisions.

## Features

- MLS data integration with Bright MLS
- Property scoring algorithm based on profitability and ROI
- Repair cost estimation
- After Repair Value (ARV) calculation using comparable sales
- Deal analysis using the 70% rule and other metrics
- Interactive visualizations and dashboards
- Excel exports for detailed analysis
- Email notifications for new opportunities

## Installation

1. Clone the repository
2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Configure your API credentials in `config/credentials.py`

## Usage

Basic usage:

```
python main.py --area "20878" --budget 400000 --roi 20 --export --visualize
```

Command line options:

- `--area`: Target ZIP code or city
- `--budget`: Maximum purchase budget
- `--roi`: Minimum ROI percentage (default: 20.0)
- `--export`: Export results to Excel
- `--notify`: Send email notification with results
- `--visualize`: Generate visualizations

## Project Structure

- `config/`: Configuration settings and credentials
- `data/`: Data connectors for MLS and other sources
- `analysis/`: Analysis algorithms and scoring
- `visualization/`: Data visualization tools
- `utils/`: Utility functions
- `models/`: Data models for properties and deals

## Example

Finding properties in ZIP code 20878 with a budget of $400,000:

```
python main.py --area "20878" --budget 400000 --export --visualize
```

This will:
1. Search for properties in ZIP 20878 under $400,000
2. Analyze potential profit and ROI for each property
3. Export results to Excel
4. Generate an HTML dashboard

## Extending the Project

### Adding New Data Sources

To add a new data source:
1. Create a new module in the `data/` directory
2. Implement functions to fetch and process the data
3. Integrate with the main analysis workflow

### Customizing the Scoring Algorithm

The property scoring algorithm can be modified in `analysis/property_scorer.py` to adjust weights or add new scoring factors based on your specific investment criteria.

### Adding Machine Learning Capabilities

For advanced users, consider adding machine learning capabilities:
1. Create a historic database of flips
2. Train a model to predict profitable properties
3. Integrate the prediction model into the scoring algorithm

## License

This project is licensed under the MIT License - see the LICENSE file for details.
