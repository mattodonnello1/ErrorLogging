import streamlit as st
st.set_page_config(page_title="Error Logging Tool", layout="wide")
st.title("🔐 Secure Login")

import streamlit_authenticator as stauth

# Single credential
names = ['UKIOps']
usernames = ['UKIOps']
passwords = ['Flutter2024']

# Hash the single password
hashed_passwords = [stauth.Hasher().hash(pw) for pw in passwords]

authenticator = stauth.Authenticate(
    names,
    usernames,
    hashed_passwords,
    'my_cookie_name',
    'my_signature_key',
    1    # This is the cookie_expiry_days, as a positional argument if your version wants it
)

name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status == False:
    st.error('Username or password is incorrect')
elif authentication_status == None:
    st.warning('Please enter your username and password')
else:
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.success(f'Logged in as {name}')

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
            
            # Filter by datetime range
            if start_date and end_date:
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                filtered_df = filtered_df[
                    (filtered_df['TimeBetStruckAt'] >= start_dt) & 
                    (filtered_df['TimeBetStruckAt'] <= end_dt)
                ]
        except Exception as e:
            st.warning(f"Warning: Could not process date filtering - {str(e)}")
    
    # Filter by MarketName if specified
    if 'MarketName' in filtered_df.columns and selected_markets and 'Select All' not in selected_markets:
        filtered_df = filtered_df[filtered_df['MarketName'].isin(selected_markets)]
    
    # Filter by SelectionName if specified
    if 'SelectionName' in filtered_df.columns and selected_selections and 'Select All' not in selected_selections:
        filtered_df = filtered_df[filtered_df['SelectionName'].isin(selected_selections)]
    
    # Check if we have a Source column or similar
    source_column = None
    for col in filtered_df.columns:
        if col.lower() in ['source', 'brand', 'operator']:
            source_column = col
            break
    
    if source_column is None:
        st.error("No source/brand column found in the data. Expected columns: 'Source', 'Brand', or 'Operator'")
        return None
    
    # Filter to only include your specific brands
    target_brands = ['BETFAIR', 'PADDY_POWER', 'SKYBET']
    filtered_df = filtered_df[filtered_df[source_column].isin(target_brands)]
    
    # Map source names to display format
    source_mapping = {
        'BETFAIR': 'Betfair',
        'PADDY_POWER': 'Paddy Power', 
        'SKYBET': 'SBGv2'
    }
    
    # Initialize results for all three brands
    results = []
    
    # Process each target brand
    for brand in target_brands:
        source_data = filtered_df[filtered_df[source_column] == brand]
        display_name = source_mapping.get(brand, brand)
        
        if len(source_data) > 0:
            # Calculate unique bets (unique BetId values)
            if 'BetId' in source_data.columns:
                unique_bet_ids = source_data['BetId'].nunique()
                
                # Calculate total stakes - sum TotalStakeGBP only once per unique BetId
                if 'TotalStakeGBP' in source_data.columns:
                    # Group by BetId and take first stake value to avoid double counting
                    unique_stakes = source_data.groupby('BetId')['TotalStakeGBP'].first()
                    total_stakes = unique_stakes.sum()
                else:
                    total_stakes = 0
            else:
                unique_bet_ids = len(source_data)
                total_stakes = source_data.get('TotalStakeGBP', pd.Series([0])).sum()
            
            # Count unique customers
            if 'CustomerId' in source_data.columns:
                unique_customers = source_data['CustomerId'].nunique()
            else:
                unique_customers = 0
        else:
            # No data for this brand - set all metrics to 0
            unique_bet_ids = 0
            total_stakes = 0
            unique_customers = 0
        
        results.append({
            'Brand': display_name,
            'Single Bets': '',  # Empty as shown in screenshot
            'Single Stakes': '',  # Empty as shown in screenshot
            'Total Bets': unique_bet_ids,
            'Total Stakes': f"£{total_stakes:.2f}",
            'Total Unique Customers': unique_customers
        })
    
    # Convert to DataFrame and sort by brand name for consistent ordering
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        # Sort to match the order: Betfair, Paddy Power, SBGv2
        brand_order = ['Betfair', 'Paddy Power', 'SBGv2']
        brand_order_map = {brand: i for i, brand in enumerate(brand_order)}
        results_df['sort_order'] = results_df['Brand'].apply(lambda x: brand_order_map.get(x, 999))
        results_df = results_df.sort_values('sort_order').drop('sort_order', axis=1)
    
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
    
    # SelectionName filter - dynamically filtered based on selected markets
    with col2:
        selected_selections = []
        if 'SelectionName' in df.columns and 'MarketName' in df.columns:
            # Filter selections based on selected markets
            if selected_markets and 'Select All' not in selected_markets:
                # Get selections only for the selected markets
                filtered_df_for_selections = df[df['MarketName'].isin(selected_markets)]
                available_selections = list(filtered_df_for_selections['SelectionName'].dropna().unique())
            else:
                # Show all selections if all markets are selected
                available_selections = list(df['SelectionName'].dropna().unique())
            
            unique_selections = ['Select All'] + sorted(available_selections)
            selected_selections = st.multiselect(
                "Select Selection Names",
                options=unique_selections,
                default=['Select All'],
                help="Choose specific selections or 'Select All' for all selections"
            )
        elif 'SelectionName' in df.columns:
            unique_selections = ['Select All'] + sorted(df['SelectionName'].dropna().unique().tolist())
            selected_selections = st.multiselect(
                "Select Selection Names",
                options=unique_selections,
                default=['Select All'],
                help="Choose specific selections or 'Select All' for all selections"
            )
        else:
            st.info("SelectionName column not found in data")
    
    # Date and time range filter
    st.subheader("📅 Date & Time Range Filter")
    
    start_datetime = None
    end_datetime = None
    
    if 'TimeBetStruckAt' in df.columns:
        try:
            # Convert to datetime and get min/max datetimes
            df_temp = df.copy()
            df_temp['TimeBetStruckAt'] = pd.to_datetime(df_temp['TimeBetStruckAt'])
            min_datetime = df_temp['TimeBetStruckAt'].min()
            max_datetime = df_temp['TimeBetStruckAt'].max()
            
            date_col1, date_col2 = st.columns(2)
            
            with date_col1:
                st.write("**Start Date & Time**")
                start_date = st.date_input(
                    "Start Date",
                    value=min_datetime.date(),
                    min_value=min_datetime.date(),
                    max_value=max_datetime.date(),
                    key="start_date"
                )
                
                # Quick time selection dropdown
                start_time_quick = st.time_input(
                    "Quick Time Selection",
                    value=min_datetime.time(),
                    key="start_time_quick"
                )
                
                # Precise time adjustment
                start_time_str = st.text_input(
                    "Precise Time (HH:MM:SS)",
                    value=start_time_quick.strftime("%H:%M:%S"),
                    help="Fine-tune time with seconds precision (e.g., 03:01:05)",
                    key="start_time_precise"
                )
                
                # Parse and validate start time
                try:
                    start_time = datetime.strptime(start_time_str, "%H:%M:%S").time()
                    start_datetime = datetime.combine(start_date, start_time)
                except ValueError:
                    st.error("Invalid time format. Please use HH:MM:SS")
                    start_datetime = datetime.combine(start_date, start_time_quick)
            
            with date_col2:
                st.write("**End Date & Time**")
                end_date = st.date_input(
                    "End Date", 
                    value=max_datetime.date(),
                    min_value=min_datetime.date(),
                    max_value=max_datetime.date(),
                    key="end_date"
                )
                
                # Quick time selection dropdown
                end_time_quick = st.time_input(
                    "Quick Time Selection",
                    value=max_datetime.time(),
                    key="end_time_quick"
                )
                
                # Precise time adjustment
                end_time_str = st.text_input(
                    "Precise Time (HH:MM:SS)",
                    value=end_time_quick.strftime("%H:%M:%S"),
                    help="Fine-tune time with seconds precision (e.g., 15:10:00)",
                    key="end_time_precise"
                )
                
                # Parse and validate end time
                try:
                    end_time = datetime.strptime(end_time_str, "%H:%M:%S").time()
                    end_datetime = datetime.combine(end_date, end_time)
                except ValueError:
                    st.error("Invalid time format. Please use HH:MM:SS")
                    end_datetime = datetime.combine(end_date, end_time_quick)
            
            # Display selected datetime range
            st.info(f"Selected range: {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")
                
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
                start_datetime, 
                end_datetime
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
