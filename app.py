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
                default=[],
                help="Choose specific markets or 'Select All' for all markets"
            )
        else:
            st.info("MarketName column not found in data")

    # For each selected market, show a multiselect for its selections
    market_selection_map = {}
    with col2:
        if 'SelectionName' in df.columns and 'MarketName' in df.columns and selected_markets and 'Select All' not in selected_markets:
            for market in selected_markets:
                selections_for_market = sorted(df[df['MarketName'] == market]['SelectionName'].dropna().unique().tolist())
                options = ['Select All'] + selections_for_market
                selected = st.multiselect(
                    f"Select for {market}",
                    options=options,
                    default=[],
                    key=f"selection_{market}"
                )
                market_selection_map[market] = selected
                if not selections_for_market:
                    st.info(f"No selections found for {market}")
        elif 'SelectionName' in df.columns:
            st.info("Please select at least one market to choose selections.")
        else:
            st.info("SelectionName column not found in data")

    # Date and time range filter
    st.subheader("📅 Date & Time Range Filter")
    
    start_datetime = None
    end_datetime = None
    
    # Filter df for selected markets and selections for time range
    filtered_time_df = df.copy()
    if 'MarketName' in filtered_time_df.columns and selected_markets and 'Select All' not in selected_markets:
        filtered_time_df = filtered_time_df[filtered_time_df['MarketName'].isin(selected_markets)]
    # Now filter by market_selection_map, using selected_markets as the source of truth
    if 'SelectionName' in filtered_time_df.columns and selected_markets and 'Select All' not in selected_markets:
        mask = pd.Series([False] * len(filtered_time_df))
        for market in selected_markets:
            selections = market_selection_map.get(market, [])
            if 'Select All' in selections:
                mask = mask | (filtered_time_df['MarketName'] == market)
            elif selections:
                mask = mask | ((filtered_time_df['MarketName'] == market) & (filtered_time_df['SelectionName'].isin(selections)))
        filtered_time_df = filtered_time_df[mask]

    if 'TimeBetStruckAt' in filtered_time_df.columns and not filtered_time_df.empty:
        try:
            # Convert to datetime and get min/max datetimes from filtered data
            filtered_time_df['TimeBetStruckAt'] = pd.to_datetime(filtered_time_df['TimeBetStruckAt'])
            min_datetime = filtered_time_df['TimeBetStruckAt'].min()
            max_datetime = filtered_time_df['TimeBetStruckAt'].max()
            
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
                    value=min_datetime.time().strftime("%H:%M:%S"),
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
                    value=max_datetime.time().strftime("%H:%M:%S"),
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
        st.info("TimeBetStruckAt column not found in data or no data for selected filters")
    
    # Error description input
    st.subheader("Paste Trader Error Description (optional)")
    trader_error_raw = st.text_area("Paste Trader Error Description (optional)", value="", height=180, key="trader_error_raw")
    generated_error_description = ""
    def parse_trader_error(raw):
        import re
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        event_market = []
        cause = ""
        action = ""
        section = None
        section_map = {
            'event': [
                'event/market(s) affected',
                'event/markets affected',
                'event/market affected',
            ],
            'cause': [
                'describe what caused this error',
                'describe what caused the error',
                'describe what caused error',
            ],
            'action': [
                'action required',
            ]
        }
        current_section = None
        buffer = []
        def flush_buffer():
            nonlocal event_market, cause, action, current_section, buffer
            if current_section == 'event':
                event_market.extend(buffer)
            elif current_section == 'cause' and buffer:
                cause = buffer[0]
            elif current_section == 'action' and buffer:
                action = buffer[0]
            buffer.clear()
        for line in lines:
            lower = line.lower()
            found_section = None
            for sec, keys in section_map.items():
                if any(lower.startswith(k) for k in keys):
                    found_section = sec
                    break
            if found_section:
                flush_buffer()
                current_section = found_section
                continue
            # If line is a bullet, remove bullet
            if line.startswith('-') or line.startswith('•'):
                line = line[1:].strip()
            if current_section:
                buffer.append(line)
        flush_buffer()
        # Format event/market
        event_market_str = " - ".join(event_market) + "." if event_market else ""
        # Format cause
        cause_str = cause.capitalize().rstrip('.') + '.' if cause else ""
        # Format action (past tense)
        def to_past_tense(text):
            text = text.strip()
            if text.lower().startswith("void bet"):
                return "Voided" + text[4:].replace("bet", "bets", 1).strip().capitalize() + "."
            if text.lower().startswith("void bets"):
                return "Voided" + text[8:].strip() + "."
            if text.lower().startswith("palp"):
                return "Palped" + text[4:].strip() + "."
            if text.lower().startswith("unsettle"):
                return "Unsettled" + text[8:].strip() + "."
            return text.capitalize().rstrip('.') + '.'
        action_str = to_past_tense(action) if action else ""
        return " ".join([s for s in [event_market_str, cause_str, action_str] if s]).strip()

    # Process and display results
    st.header("📈 Analysis Results")
    
    if st.button("Generate Analysis", type="primary"):
        with st.spinner("Processing data..."):
            # Build lists for process_betting_data
            filtered_markets = list(market_selection_map.keys()) if market_selection_map else selected_markets
            filtered_selections = []
            for market, selections in market_selection_map.items():
                if 'Select All' in selections or not selections:
                    # Add all selections for this market
                    filtered_selections.extend(df[df['MarketName'] == market]['SelectionName'].dropna().unique().tolist())
                else:
                    filtered_selections.extend(selections)
            results_df = process_betting_data(
                df, 
                filtered_markets, 
                filtered_selections, 
                start_datetime, 
                end_datetime
            )
            
            # Generate error description if trader_error_raw is filled
            if trader_error_raw.strip():
                generated_error_description = parse_trader_error(trader_error_raw)

        # Show generated error description if available (always, before results)
        if generated_error_description:
            st.subheader("Generated Error Description")
            edited_error = st.text_area("Edit Error Description", value=generated_error_description, height=100, key="edited_error")
            st.button("Copy Error Description", on_click=lambda: st.session_state.update({"copied_error": edited_error}))

        if results_df is not None and not results_df.empty:
            st.subheader("Summary by Source")
            st.dataframe(
                results_df,
                use_container_width=True,
                hide_index=True
            )
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
    
    # Footer
    st.markdown("---")
    st.caption("Betting Data Analysis Tool - Built with Streamlit")

if __name__ == "__main__":
    main()

