# Airbnb Optimiser (AirbnbEdge)

A data-driven consulting toolkit that helps Airbnb property owners maximize rental revenue using machine learning models trained on 2,879 Bristol Airbnb listings.

## Features

### Market Analysis Dashboard
- Neighbourhood revenue analysis (top performing areas)
- Price distribution charts by room type
- Revenue distribution analysis
- Property type performance comparison
- Occupancy rate analysis
- Superhost impact visualization
- Review score correlations
- Amenity revenue impact analysis

### Property Analyzer (Core Feature)
- **Web Scraper**: Extracts listing data from Airbnb URLs (handles modern 2024/2025 page structure)
- **Manual Input**: Form-based property data entry
- **CSV Upload**: Support for custom city datasets (London, Edinburgh, Manchester)
- **ML-Powered Predictions**: Predicts annual revenue using Gradient Boosting models (R² ≈ 0.72)
- **Property Scoring**: Scores properties 0-140 across 7 dimensions:
  - Pricing (0-20), Amenities (0-20), Host Quality (0-20)
  - Booking Setup (0-20), Reviews (0-20), Listing Quality (0-20)
  - Location & Availability (0-20)
- **Optimization Opportunities**: Ranked list of actionable changes with predicted revenue uplift
- **P&L Calculator**: Full profit & loss analysis including mortgage/rent, bills, insurance, cleaning, consumables, maintenance, and Airbnb fees (3%)

### Advanced Analytics
- **Model Comparison**: Gradient Boosting, Random Forest, Linear Regression, Ridge Regression
- **Feature Importance**: Identifies top revenue drivers
- **Pricing Curve Simulation**: Finds optimal nightly price
- **K-Means Clustering**: Market segmentation (5 segments)
- **Partial Dependence Plots**: Visualizes impact of guest capacity and amenities on revenue
- **Correlation Heatmaps**: Feature relationships with revenue

### Business Tools
- **PDF Report Generator**: Creates professional business plans using ReportLab
- **Consulting Framework**: 5-method approach (Linear Regression, Random Forest, Gradient Boosting, Clustering, Pricing Simulation)
- **Go-to-Market Strategy**: Built-in business plan with pricing tiers (£149-£799 packages, £249/month retainers)

## Technology Stack

| Component | Technology |
|-----------|-------------|
| **Backend Framework** | Flask 3.0.3 (Python) |
| **Data Processing** | Pandas 2.2.2, NumPy 1.26.4 |
| **Machine Learning** | Scikit-learn 1.5.1 (GradientBoostingRegressor, RandomForestRegressor, LinearRegression, Ridge, KMeans) |
| **Visualization** | Plotly 5.22.0 (interactive charts), Matplotlib, Seaborn |
| **Web Scraping** | BeautifulSoup4 4.12.3, Requests 2.32.3 |
| **PDF Generation** | ReportLab |
| **Frontend** | HTML5, CSS3 (custom design), JavaScript (Plotly.js 2.27.0) |
| **Fonts** | DM Sans, Inter (Google Fonts) |
| **WSGI Server** | Gunicorn 22.0.0 |
| **Development** | Jupyter Notebook |

## Getting Started

### Prerequisites
- Python 3.8+ installed
- pip package manager

### Installation

```bash
cd "/Users/salahbaaziz/Desktop/Projects/Airbnb Optimiser"
pip install -r requirements.txt
```

### Running the Application

```bash
cd Code
python app.py
```

Or from project root:
```bash
python "Code/app.py"
```

Access at `http://localhost:5050`

### For Production (Heroku/etc.)
```
web: gunicorn --chdir Code wsgi:app --workers 2 --timeout 120
```

## Using the Application

1. **Market Analysis Tab**: View Bristol Airbnb market insights, revenue distributions, and neighborhood analysis

2. **Complex Analysis Tab**: View ML model comparisons, feature importance, clustering, and pricing curves

3. **Property Analyzer Tab**: 
   - **Option A**: Enter Airbnb listing URL to auto-scrape data
   - **Option B**: Manually fill property details (neighborhood, bedrooms, price, amenities, etc.)
   - **Option C**: Upload custom CSV dataset for any city
   - Click "Analyze Property" to get:
     - Predicted annual revenue (current vs optimized)
     - Property score (0-140) with category (Underperforming/Average/Good/Strong/Excellent)
     - Ranked optimization opportunities with £ impact
     - Full P&L statement
     - Radar chart scorecard

## Key Insights

Based on analysis of 2,879 Bristol listings:
- **Median annual revenue**: £3,636
- **Top performers**: Earn £35,000+/year
- **Best neighborhoods**: Clifton, Central, Hotwells & Harbourside
- **Top optimization levers** (by ROI):
  1. Enable Instant Booking: +15-25% bookings (£0 cost)
  2. Achieve Superhost status: +30-50% revenue (effort only)
  3. Optimal pricing (model-driven): +10-20% revenue (£0 cost)
  4. 1-hour response templates: +10-20% bookings (30 mins setup)
  5. Dedicated workspace: +15-25% revenue (£200-500 cost)

## Project Structure

```
Airbnb Optimiser/
├── Code/
│   ├── app.py                    # Main Flask application (1537 lines)
│   ├── listing_scraper.py        # Airbnb listing scraper (1164 lines)
│   ├── wsgi.py                 # WSGI entry point
│   ├── generate_pdf.py          # PDF business plan generator (718 lines)
│   └── Airbnb_Profit_Optimiser.ipynb  # Main analysis notebook
├── dataset/
│   └── bristol.csv             # 2,879 Bristol listings
├── templates/
│   └── index.html              # Web UI (2089 lines)
├── group_outputs/               # Generated charts and reports
│   ├── AirbnbEdge_Business_Plan.pdf
│   ├── bristol_revenue_heatmap.html
│   └── [12+ analysis charts]
├── requirements.txt             # Python dependencies
├── Procfile                    # Heroku/Gunicorn config
└── Airbnb_Profit_Optimiser.pdf # PDF version of notebook
```

## Summary

A complete data science consulting business-in-a-box, from data collection and ML modeling to polished web application and business plan generation.
