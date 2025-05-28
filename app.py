import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import io

def load_excel_data(uploaded_files):
    """Load and combine data from uploaded Excel files"""
    all_data = []
    
    for uploaded_file in uploaded_files:
        try:
            # Try to read the Excel file
            df = pd.read_excel(uploaded_file)
            all_data.append(df)
        except Exception as e:
            st.error(f"Error reading file {uploaded_file.name}: {str(e)}")
            return None
    
    if all_data:
        # Combine all dataframes
        combined_df = pd.concat(all_data, ignore_index=True)
        return combined_df
    else:
        return None

def process_betting_data(df, selected_markets, selected_selections, start_date, end_date):
    """Process betting data based on filters and calculate metrics"""
    
    # Make a copy to avoid modifying original data
    filtered_df = df.copy()
    
    # Convert TimeBetStruckAt to datetime if it exists
    if 'TimeBetStruckAt' in filtered_df.columns:
        try:
            filtered_df['TimeBetStruckAt'] = pd.to_datetime(filtered_df['TimeBetStruckAt'])
            
            # Filter by date range
            if start_date and end_date:
                start_datetime = pd.to_datetime(start_date)
                end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # Include end date
                filtered_df = filtered_df[
                    (filtered_df['TimeBetStruckAt'] >= start_datetime) & 
                    (filtered_df['TimeBetStruckAt'] < end_datetime)
                ]
        except Exception as e:
            st.warning(f"Warning: Could not process date filtering - {str(e)}")
    
    # Filter by MarketName if specified
    if 'MarketName' in filtered_df.columns and selected_markets and 'Select All' not in selected_markets:
        filtered_df = filtered_df[filtered_df['MarketName'].isin(selected_markets)]
    
    # Filter by SelectionName if specified
    if 'SelectionName' in filtered_df.columns and selected_selections and 'Select All' not in selected_selections:
        filtered_df = filtered_df[filtered_df['SelectionName'].isin(selected_selections)]
    
    # Map source names to standardized format
    source_mapping = {
        'BETFAIR': 'Betfair',
        'PADDY_POWER': 'Paddy Power', 
        'SKYBET': 'SBGv2',
        'SBGv2': 'SBGv2'
    }
    
    # Check if we have a Source column or similar
    source_column = None
    for col in filtered_df.columns:
        if col.lower() in ['source', 'brand', 'operator']:
            source_column = col
            break
    
    if source_column is None:
        st.error("No source/brand column found in the data. Expected columns: 'Source', 'Brand', or 'Operator'")
        return None
    
    # Standardize source names
    filtered_df['StandardizedSource'] = filtered_df[source_column].map(source_mapping).fillna(filtered_df[source_column])
    
    # Initialize results dictionary
    results = []
    
    # Process each source
    for source in filtered_df['StandardizedSource'].unique():
        source_data = filtered_df[filtered_df['StandardizedSource'] == source]
        
        # Calculate metrics
        total_bets = len(source_data)
        
        # Handle duplicate BetId entries for stakes - sum stakes only once per unique BetId
        if 'BetId' in source_data.columns and 'Stake' in source_data.columns:
            # Group by BetId and sum stakes to handle duplicates
            unique_stakes = source_data.groupby('BetId')['Stake'].sum()
            total_stakes = unique_stakes.sum()
        elif 'Stake' in source_data.columns:
            total_stakes = source_data['Stake'].sum()
        else:
            total_stakes = 0
        
        # Count unique customers
        if 'CustomerId' in source_data.columns:
            unique_customers = source_data['CustomerId'].nunique()
        else:
            unique_customers = 0
        
        results.append({
            'Brand': source,
            'Total Bets': total_bets,
            'Total Stakes': f"£{total_stakes:.2f}",
            'Total Unique Customers': unique_customers
        })
    
    # Convert to DataFrame and sort by brand name
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values('Brand')
    
    return results_df

def main():
    """Main Streamlit application"""
    
    st.title("Betting Data Error Logging Analysis Tool")
    st.write("Upload Excel files containing betting data to analyze metrics by source")
    
    # File upload section
    st.header("📁 Upload Data Files")
    uploaded_files = st.file_uploader(
        "Choose Excel files", 
        type=['xlsx', 'xls'], 
        accept_multiple_files=True,
        help="Upload one or more Excel files containing betting data"
    )
    
    if not uploaded_files:
        st.info("Please upload one or more Excel files to begin analysis")
        return
    
    # Load data
    with st.spinner("Loading data..."):
        df = load_excel_data(uploaded_files)
    
    if df is None:
        st.error("Failed to load data from uploaded files")
        return
    
    if df.empty:
        st.error("No data found in uploaded files")
        return
    
    st.success(f"Successfully loaded {len(df)} records from {len(uploaded_files)} file(s)")
    
    # Display data info
    with st.expander("📊 Data Overview"):
        st.write(f"**Total Records:** {len(df)}")
        st.write(f"**Columns:** {', '.join(df.columns.tolist())}")
        st.write("**Sample Data:**")
        st.dataframe(df.head())
    
    # Filter section
    st.header("🔍 Data Filters")
    
    col1, col2 = st.columns(2)
    
    # MarketName filter
    with col1:
        selected_markets = []
        if 'MarketName' in df.columns:
            unique_markets = ['Select All'] + sorted(df['MarketName'].dropna().unique().tolist())
            selected_markets = st.multiselect(
                "Select Market Names",
                options=unique_markets,
                default=['Select All'],
                help="Choose specific markets or 'Select All' for all markets"
            )
        else:
            st.info("MarketName column not found in data")
    
    # SelectionName filter  
    with col2:
        selected_selections = []
        if 'SelectionName' in df.columns:
            unique_selections = ['Select All'] + sorted(df['SelectionName'].dropna().unique().tolist())
            selected_selections = st.multiselect(
                "Select Selection Names",
                options=unique_selections,
                default=['Select All'],
                help="Choose specific selections or 'Select All' for all selections"
            )
        else:
            st.info("SelectionName column not found in data")
    
    # Date range filter
    st.subheader("📅 Date Range Filter")
    
    date_col1, date_col2 = st.columns(2)
    
    start_date = None
    end_date = None
    
    if 'TimeBetStruckAt' in df.columns:
        try:
            # Convert to datetime and get min/max dates
            df_temp = df.copy()
            df_temp['TimeBetStruckAt'] = pd.to_datetime(df_temp['TimeBetStruckAt'])
            min_date = df_temp['TimeBetStruckAt'].min().date()
            max_date = df_temp['TimeBetStruckAt'].max().date()
            
            with date_col1:
                start_date = st.date_input(
                    "Start Date",
                    value=min_date,
                    min_value=min_date,
                    max_value=max_date
                )
            
            with date_col2:
                end_date = st.date_input(
                    "End Date", 
                    value=max_date,
                    min_value=min_date,
                    max_value=max_date
                )
                
        except Exception as e:
            st.warning(f"Could not process date column: {str(e)}")
    else:
        st.info("TimeBetStruckAt column not found in data")
    
    # Process and display results
    st.header("📈 Analysis Results")
    
    if st.button("Generate Analysis", type="primary"):
        with st.spinner("Processing data..."):
            results_df = process_betting_data(
                df, 
                selected_markets, 
                selected_selections, 
                start_date, 
                end_date
            )
        
        if results_df is not None and not results_df.empty:
            st.subheader("Summary by Source")
            
            # Display the results table
            st.dataframe(
                results_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Calculate totals
            total_row = {
                'Brand': 'Totals',
                'Total Bets': results_df['Total Bets'].sum(),
                'Total Stakes': f"£{sum(float(stake.replace('£', '')) for stake in results_df['Total Stakes']):.2f}",
                'Total Unique Customers': results_df['Total Unique Customers'].sum()
            }
            
            st.subheader("Overall Totals")
            totals_df = pd.DataFrame([total_row])
            st.dataframe(
                totals_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Additional insights
            st.subheader("📊 Key Insights")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Total Bets Processed", 
                    f"{total_row['Total Bets']:,}"
                )
            
            with col2:
                st.metric(
                    "Total Stakes", 
                    total_row['Total Stakes']
                )
            
            with col3:
                st.metric(
                    "Unique Customers", 
                    f"{total_row['Total Unique Customers']:,}"
                )
            
        else:
            st.warning("No data found matching the selected criteria. Please adjust your filters and try again.")
    
    # Footer
    st.markdown("---")
    st.caption("Betting Data Analysis Tool - Built with Streamlit")

if __name__ == "__main__":
    main()
