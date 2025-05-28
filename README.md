# Betting Data Error Logging Analysis Tool

A Streamlit-based application for analyzing betting data errors and generating source-specific metrics.

## Features

- **Multi-file Excel Upload**: Upload one or multiple Excel files containing betting data
- **Dynamic Filtering**: 
  - Market selection with dropdown
  - Selection filtering based on chosen markets
  - Precise date and time range selection with seconds precision
- **Source Analysis**: Automatic analysis for BETFAIR, PADDY_POWER, and SKYBET
- **Metrics Calculation**:
  - Total unique bets (based on BetId)
  - Total stakes (using TotalStakeGBP, avoiding double counting)
  - Unique customers affected

## Installation

### Prerequisites
- Python 3.11 or higher
- pip package manager

### Setup Instructions

1. **Clone or download this folder to your local machine**

2. **Install required packages**:
   ```bash
   pip install streamlit pandas openpyxl numpy
   ```

3. **Run the application**:
   ```bash
   streamlit run app.py
   ```

4. **Access the app**: Open your browser and go to `http://localhost:8501`

## Usage

1. **Upload Data**: Use the file uploader to select your Excel files containing betting data
2. **Filter Data**:
   - Select market names from the dropdown
   - Choose selections (filtered based on selected markets)
   - Set precise date and time range using both dropdown and text input
3. **Generate Analysis**: Click "Generate Analysis" to see metrics by source
4. **Review Results**: View total bets, stakes, and unique customers for each brand

## Expected Data Format

Your Excel files should contain the following columns:
- `BetId`: Unique identifier for each bet
- `TotalStakeGBP`: Stake amount in GBP
- `CustomerId`: Customer identifier
- `MarketName`: Name of the betting market
- `SelectionName`: Name of the selection
- `TimeBetStruckAt`: Timestamp when bet was placed
- `Source` (or `Brand`): Source identifier (BETFAIR, PADDY_POWER, SKYBET)

## Time Selection

The app provides flexible time selection:
- **Quick Selection**: Use the dropdown time picker for fast selection
- **Precise Adjustment**: Fine-tune with seconds precision (e.g., 03:01:05)
- The text input automatically updates based on your dropdown selection

## Output

The analysis generates:
- Summary table showing metrics for each brand
- Overall totals across all brands
- Key insights with visual metrics display

## Team Usage

This tool is designed for team collaboration on betting data analysis. Each team member can:
- Upload their own Excel files
- Apply different filtering criteria
- Generate consistent reports using the same methodology

## Support

For questions or issues, please contact your development team.