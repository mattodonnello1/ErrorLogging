import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, time
import io
import streamlit.components.v1 as components

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

def get_time_range_for_filters(df, markets, market_selection_map):
    """Get the time range for the currently selected markets and selections"""
    if df.empty or 'TimeBetStruckAt' not in df.columns:
        return None, None
    
    filtered_df = df.copy()
    
    # If "Select All" is chosen for markets, use entire dataset
    if markets and 'Select All' in markets:
        # Use the entire dataset - no market filtering
        pass
    elif markets:
        # Filter by specific markets only
        filtered_df = filtered_df[filtered_df['MarketName'].isin(markets)]
        
        # Handle selections filtering only if we have specific markets (not "Select All" for markets)
        if ('SelectionName' in filtered_df.columns and market_selection_map):
            mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
            for market in markets:
                selections = market_selection_map.get(market, [])
                if 'Select All' in selections or not selections:
                    # Include all selections for this market when "Select All" is chosen or no selections specified
                    market_mask = (filtered_df['MarketName'] == market)
                    mask = mask | market_mask
                else:
                    # Include only specific selections for this market
                    selection_mask = ((filtered_df['MarketName'] == market) & (filtered_df['SelectionName'].isin(selections)))
                    mask = mask | selection_mask
            filtered_df = filtered_df[mask]
    
    if filtered_df.empty:
        return None, None
    
    try:
        filtered_df['TimeBetStruckAt'] = pd.to_datetime(filtered_df['TimeBetStruckAt'])
        min_datetime = filtered_df['TimeBetStruckAt'].min()
        max_datetime = filtered_df['TimeBetStruckAt'].max()
        return min_datetime, max_datetime
    except:
        return None, None

def copy_to_clipboard_js(text):
    """Generate JavaScript code to copy text to clipboard"""
    js_code = f"""
    <script>
    function copyToClipboard() {{
        navigator.clipboard.writeText(`{text}`).then(function() {{
            alert('Error description copied to clipboard!');
        }}, function(err) {{
            // Fallback for older browsers
            var textArea = document.createElement("textarea");
            textArea.value = `{text}`;
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                document.execCommand('copy');
                alert('Error description copied to clipboard!');
            }} catch (err) {{
                alert('Failed to copy to clipboard');
            }}
            document.body.removeChild(textArea);
        }});
    }}
    </script>
    <button onclick="copyToClipboard()" style="
        background-color: #ff4b4b;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        margin-top: 10px;
    ">Copy Error Description</button>
    """
    return js_code

def main():
    """Main Streamlit application"""

    st.title("Betting Data Error Logging Analysis Tool")
    st.write("Upload Excel files containing betting data to analyze metrics by source")
    
    # Initialize session state for time synchronization
    if 'time_sync_enabled' not in st.session_state:
        st.session_state.time_sync_enabled = True
    if 'last_quick_start_time' not in st.session_state:
        st.session_state.last_quick_start_time = None
    if 'last_quick_end_time' not in st.session_state:
        st.session_state.last_quick_end_time = None

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

    # Get time range for current filters
    current_min_datetime, current_max_datetime = get_time_range_for_filters(df, selected_markets, market_selection_map)

    if current_min_datetime and current_max_datetime:
        # Track filter changes to reset times appropriately
        current_filter_key = f"{sorted(selected_markets) if selected_markets else []}_{sorted([str(market_selection_map) for market in selected_markets])}"
        
        # Initialize or reset times when filters change
        if ('filter_key' not in st.session_state or 
            st.session_state.filter_key != current_filter_key or
            'precise_start_time' not in st.session_state):
            
            st.session_state.filter_key = current_filter_key
            # Set precise time to exact first/last bet times (with seconds)
            st.session_state.precise_start_time = current_min_datetime.strftime("%H:%M:%S")
            st.session_state.precise_end_time = current_max_datetime.strftime("%H:%M:%S")

        date_col1, date_col2 = st.columns(2)

        with date_col1:
            st.write("**Start Date & Time**")
            start_date = st.date_input(
                "Start Date",
                value=current_min_datetime.date(),
                min_value=current_min_datetime.date(),
                max_value=current_max_datetime.date(),
                key="start_date"
            )

            # Time selection
            start_time_str = st.text_input(
                "Time (HH:MM:SS)",
                value=st.session_state.get('precise_start_time', current_min_datetime.strftime("%H:%M:%S")),
                help="Shows exact time of first bet. Fine-tune with seconds precision (e.g., 03:01:05)",
                key="start_time_precise"
            )

            # Update session state with current time
            st.session_state.precise_start_time = start_time_str

            # Parse and validate start time
            try:
                start_time = datetime.strptime(start_time_str, "%H:%M:%S").time()
                start_datetime = datetime.combine(start_date, start_time)
            except ValueError:
                st.error("Invalid time format. Please use HH:MM:SS")
                start_datetime = datetime.combine(start_date, current_min_datetime.time())

        with date_col2:
            st.write("**End Date & Time**")
            end_date = st.date_input(
                "End Date", 
                value=current_max_datetime.date(),
                min_value=current_min_datetime.date(),
                max_value=current_max_datetime.date(),
                key="end_date"
            )

            # Time selection
            end_time_str = st.text_input(
                "Time (HH:MM:SS)",
                value=st.session_state.get('precise_end_time', current_max_datetime.strftime("%H:%M:%S")),
                help="Shows exact time of last bet. Fine-tune with seconds precision (e.g., 15:10:00)",
                key="end_time_precise"
            )

            # Update session state with current time
            st.session_state.precise_end_time = end_time_str

            # Parse and validate end time
            try:
                end_time = datetime.strptime(end_time_str, "%H:%M:%S").time()
                end_datetime = datetime.combine(end_date, end_time)
            except ValueError:
                st.error("Invalid time format. Please use HH:MM:SS")
                end_datetime = datetime.combine(end_date, current_max_datetime.time())

        # Display selected datetime range
        st.info(f"Selected range: {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")

    else:
        st.info("TimeBetStruckAt column not found in data or no data for selected filters")

    # Error description input
    st.subheader("Paste Trader Error Description (optional)")
    trader_error_raw = st.text_area("Paste Trader Error Description (optional)", value="", height=180, key="trader_error_raw")
    generated_error_description = ""
    def parse_trader_error(raw):
        import re
        
        # Check if this is structured text (has section headers) or unstructured
        if any(header in raw.lower() for header in ['action required', 'event/market', 'describe what caused']):
            # Handle structured format
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
        else:
            # Handle unstructured format - parse as a single description
            # Look for common patterns in the text
            text = raw.strip()
            
            # Split into sentences to identify components
            sentences = re.split(r'[.!]\s+', text)
            
            event_market_str = ""
            cause_str = ""
            action = ""
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                # Look for event/market info (usually first sentence with team names or event info)
                if any(keyword in sentence.lower() for keyword in ['vs', 'v ', 'against', 'match', 'game']) and not event_market_str:
                    event_market_str = sentence + "."
                # Look for action patterns (void, palp, resettle, etc.)
                elif any(keyword in sentence.lower() for keyword in ['void', 'palp', 'resettle', 'unsettle', 'cancel', 'reprice']):
                    action = sentence
                # Everything else goes to cause
                else:
                    if cause_str:
                        cause_str += " " + sentence + "."
                    else:
                        cause_str = sentence.capitalize() + "."
        # Format action (past tense)
        def to_past_tense(text):
            import re
            text = text.strip()
            
            # Remove "please" first (case insensitive)
            text = re.sub(r'\bplease\b', '', text, flags=re.IGNORECASE).strip()
            
            # Remove common question prefixes and transform
            text = re.sub(r'^(can\s+we\s+|can\s+this\s+be\s+|can\s+any\s+|can\s+all\s+|need\s+to\s+)', '', text, flags=re.IGNORECASE).strip()
            
            # Handle "Can all x after y be z" pattern specifically for questions
            can_all_pattern = r'^all\s+(.+?)\s+be\s+(.+?)[\?\.]?$'
            can_all_match = re.match(can_all_pattern, text, re.IGNORECASE)
            if can_all_match:
                what = can_all_match.group(1).strip()
                action = can_all_match.group(2).strip()
                # Convert action to past tense
                if action.lower() in ["voided", "void"]:
                    return f"All {what} have been voided."
                elif action.lower() in ["resettled", "resettle"]:
                    return f"All {what} have been resettled."
                else:
                    return f"All {what} have been {action}."
            
            # Handle compound actions with slashes
            if "/" in text:
                parts = text.split("/")
                transformed_parts = []
                for part in parts:
                    part = part.strip()
                    if part.lower() == "void":
                        transformed_parts.append("Voided")
                    elif part.lower() == "re-price":
                        transformed_parts.append("Re-priced")
                    elif part.lower() == "reprice":
                        transformed_parts.append("Repriced")
                    elif part.lower() == "action":
                        transformed_parts.append("Actioned")
                    elif part.lower() == "resettle":
                        transformed_parts.append("Resettled")
                    elif part.lower() == "unsettle":
                        transformed_parts.append("Unsettled")
                    elif part.lower() == "palp":
                        transformed_parts.append("Palped")
                    elif part.lower() == "cancel":
                        transformed_parts.append("Cancelled")
                    else:
                        transformed_parts.append(part.capitalize())
                return "/".join(transformed_parts) + "."
            
            # Handle specific action verbs with proper spacing
            if text.lower().startswith("void bets"):
                remainder = text[9:].strip()
                return f"Voided bets {remainder}" if remainder else "Voided bets"
            elif text.lower().startswith("void bet"):
                remainder = text[8:].strip()
                return f"Voided bet {remainder}" if remainder else "Voided bet"
            elif text.lower().startswith("void all"):
                remainder = text[8:].strip()
                return f"Voided all {remainder}" if remainder else "Voided all"
            elif text.lower().startswith("void"):
                remainder = text[4:].strip()
                return f"Voided {remainder}" if remainder else "Voided"
            elif text.lower().startswith("palp"):
                remainder = text[4:].strip()
                return f"Palped {remainder}" if remainder else "Palped"
            elif text.lower().startswith("unsettle"):
                remainder = text[8:].strip()
                return f"Unsettled {remainder}" if remainder else "Unsettled"
            elif text.lower().startswith("settle"):
                remainder = text[6:].strip()
                return f"Settled {remainder}" if remainder else "Settled"
            elif text.lower().startswith("resettle"):
                remainder = text[8:].strip()
                return f"Resettled {remainder}" if remainder else "Resettled"
            elif text.lower().startswith("re-price"):
                remainder = text[8:].strip()
                return f"Re-priced {remainder}" if remainder else "Re-priced"
            elif text.lower().startswith("reprice"):
                remainder = text[7:].strip()
                return f"Repriced {remainder}" if remainder else "Repriced"
            elif text.lower().startswith("cancel"):
                remainder = text[6:].strip()
                return f"Cancelled {remainder}" if remainder else "Cancelled"
            elif text.lower().startswith("action account"):
                return "Actioned account"
            elif text.lower().startswith("action"):
                remainder = text[6:].strip()
                return f"Actioned {remainder}" if remainder else "Actioned"
            
            # Handle "This needs to be" patterns
            if "needs to be" in text.lower():
                text = re.sub(r'this\s+needs\s+to\s+be\s+', '', text, flags=re.IGNORECASE).strip()
                # Capitalize first word after removal
                if text:
                    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
            
            # Handle "There are" -> "There was"
            text = re.sub(r'\bthere\s+are\b', 'There was', text, flags=re.IGNORECASE)
            
            # Clean up extra spaces
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Ensure it ends with a period (only if it doesn't already end with punctuation)
            if text and not text.endswith(('.', '!', '?')):
                text += '.'
            
            # Capitalize the first letter if not already
            if text:
                text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
            
            return text
        action_str = to_past_tense(action) if action else ""
        result = " ".join([s for s in [event_market_str, cause_str, action_str] if s]).strip()
        
        # Remove the word "please" from the final result (case insensitive)
        import re
        result = re.sub(r'\bplease\b', '', result, flags=re.IGNORECASE)
        # Clean up any double spaces that might result from removing "please"
        result = re.sub(r'\s+', ' ', result).strip()
        
        # Capitalize first letter after each full stop
        sentences = result.split('. ')
        capitalized_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                # Capitalize first letter of each sentence
                sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
            capitalized_sentences.append(sentence)
        result = '. '.join(capitalized_sentences)
        
        return result

    # Generate error description if trader_error_raw is filled (outside of button click)
    generated_error_description = ""
    if trader_error_raw.strip():
        generated_error_description = parse_trader_error(trader_error_raw)

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

        # Show generated error description if available
        if generated_error_description:
            st.subheader("Generated Error Description")
            
            # Create a copyable text area with copy button
            col1, col2 = st.columns([6, 1])
            with col1:
                # Custom styled text area with white text
                st.markdown(
                    f"""
                    <div style="
                        background-color: #262730;
                        color: white;
                        padding: 15px;
                        border-radius: 5px;
                        border: 1px solid #c4c4c4;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
                        font-size: 14px;
                        min-height: 120px;
                        white-space: pre-wrap;
                        overflow-wrap: break-word;
                        margin-bottom: 10px;
                        line-height: 1.6;
                    ">{generated_error_description}</div>
                    """,
                    unsafe_allow_html=True
                )
            with col2:
                # Use HTML and JavaScript for a working copy button
                escaped_error = generated_error_description.replace('`', '\\`').replace('\n', '\\n').replace('\r', '\\r').replace('\\', '\\\\').replace("'", "\\'")
                
                copy_button_html = f"""
                <div style="margin-top: 25px;">
                    <button 
                        onclick="copyToClipboard()" 
                        style="
                            background: #f0f2f6;
                            border: 1px solid #c4c4c4;
                            border-radius: 4px;
                            padding: 8px 12px;
                            cursor: pointer;
                            font-size: 14px;
                            color: #262730;
                        "
                        title="Copy to clipboard"
                    >
                        📋 Copy
                    </button>
                </div>
                <script>
                function copyToClipboard() {{
                    const text = `{escaped_error}`;
                    navigator.clipboard.writeText(text).then(function() {{
                        console.log('Copied to clipboard');
                    }}).catch(function(err) {{
                        // Fallback for older browsers
                        const textArea = document.createElement("textarea");
                        textArea.value = text;
                        document.body.appendChild(textArea);
                        textArea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textArea);
                    }});
                }}
                </script>
                """
                components.html(copy_button_html, height=80)

        if results_df is not None and not results_df.empty:
            st.subheader("Summary by Source")
            
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

    # Footer
    st.markdown("---")
    st.caption("Betting Data Analysis Tool - Built with Streamlit")

if __name__ == "__main__":
    main()