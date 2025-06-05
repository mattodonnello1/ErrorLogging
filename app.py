import streamlit as st
import pandas as pd
import openpyxl
from datetime import datetime, time
import streamlit.components.v1 as components
import re

def load_excel_data(uploaded_files):
    """Load and combine data from uploaded Excel files"""
    combined_df = pd.DataFrame()

    for uploaded_file in uploaded_files:
        try:
            # Read Excel file yo
            df = pd.read_excel(uploaded_file)
            combined_df = pd.concat([combined_df, df], ignore_index=True)
        except Exception as e:
            st.error(f"Error reading {uploaded_file.name}: {str(e)}")
            continue

    return combined_df if not combined_df.empty else None

def process_betting_data(df, selected_markets, selected_selections, start_date, end_date):
    """Process betting data based on filters and calculate metrics"""
    filtered_df = df.copy()

    # Apply market filters
    if selected_markets and 'Select All' not in selected_markets:
        filtered_df = filtered_df[filtered_df['MarketName'].isin(selected_markets)]

    # Apply selection filters
    if selected_selections and 'Select All' not in selected_selections:
        filtered_df = filtered_df[filtered_df['SelectionName'].isin(selected_selections)]

    # Apply date range filter
    if start_date and end_date:
        if 'TimeBetStruckAt' in filtered_df.columns:
            filtered_df['TimeBetStruckAt'] = pd.to_datetime(filtered_df['TimeBetStruckAt'])
            mask = (filtered_df['TimeBetStruckAt'] >= start_date) & (filtered_df['TimeBetStruckAt'] <= end_date)
            filtered_df = filtered_df[mask]

    # Find source column
    source_column = None
    for col in ['Source', 'Brand', 'Operator']:
        if col in filtered_df.columns:
            source_column = col
            break

    if source_column is None:
        st.error("No source column found (Source, Brand, or Operator)")
        return pd.DataFrame()

    # Filter for target brands (exclude FANDUEL completely)
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

    # Create DataFrame and add sort order for consistent display
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        sort_order = {'Betfair': 1, 'Paddy Power': 2, 'SBGv2': 3}
        results_df['sort_order'] = results_df['Brand'].map(sort_order)
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

def process_fieldbook_paste(paste_data):
    """Process pasted fieldbook data and return analysis results"""
    lines = [line.strip() for line in paste_data.strip().split('\n') if line.strip()]

    # Parse tab-separated data - handle multi-line cashout format
    rows = []
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = line.split('\t')

        if len(parts) >= 18:  # Standard bet line
            rows.append(parts)
        elif len(parts) >= 4:  # Potential start of cashout format
            # Check if next lines contain FULL and cashout amount
            if i + 2 < len(lines):
                next_line = lines[i + 1].strip()
                third_line = lines[i + 2].strip()

                if next_line == 'FULL' and third_line.startswith('£'):
                    # This is a cashout format - combine into single line, skip FULL and amount
                    # Take first 4 parts, skip FULL and amount, then continue with remaining parts
                    remaining_parts = third_line.split('\t')[1:]  # Skip the cashout amount
                    combined_parts = parts + [''] + remaining_parts  # Add empty for cashout column
                    if len(combined_parts) >= 18:
                        rows.append(combined_parts)
                    i += 2  # Skip the FULL and amount lines
                else:
                    # Not a cashout format, treat as regular line if it has enough parts
                    if len(parts) >= 18:
                        rows.append(parts)
            else:
                # End of data, treat as regular line if it has enough parts
                if len(parts) >= 18:
                    rows.append(parts)

        i += 1

    if not rows:
        return None

    # Create DataFrame with proper column names
    columns = ['BetId', 'Dest', 'Shop', 'Stake', 'Cashout', 'Leg', 'SF', 'PercentMax', 
               'BT', 'Price', 'PT', 'Tag', 'Time', 'Country', 'LiabilityGroup', 'Nick', 'Id', 'NumBets']

    df = pd.DataFrame(rows, columns=columns[:len(rows[0]) if rows else 0])

    # Filter for target destinations (exclude FANDUEL completely)
    target_destinations = ['SKYBET', 'PADDY_POWER', 'BETFAIR']
    df = df[df['Dest'].isin(target_destinations)]

    # Destination mapping for display
    dest_mapping = {
        'SKYBET': 'SBGv2',
        'PADDY_POWER': 'Paddy Power',
        'BETFAIR': 'Betfair'
    }

    results = []

    for dest in target_destinations:
        dest_data = df[df['Dest'] == dest]
        display_name = dest_mapping.get(dest, dest)

        if len(dest_data) > 0:
            # Calculate unique bets (unique BetId values)
            unique_bet_ids = dest_data['BetId'].nunique()

            # Calculate total stakes - handle cashouts properly
            stakes = []
            for stake_val in dest_data['Stake']:
                stake_str = str(stake_val).strip()

                # Handle Betfair format: "£0.86 (€1.00)" - extract the GBP value
                if '£' in stake_str:
                    # Extract GBP value (before any brackets)
                    gbp_part = stake_str.split('(')[0].replace('£', '').strip()
                    try:
                        stakes.append(float(gbp_part))
                    except:
                        stakes.append(0)
                elif '€' in stake_str and '(' not in stake_str:
                    # Pure Euro value - convert or use as is
                    euro_part = stake_str.replace('€', '').strip()
                    try:
                        stakes.append(float(euro_part))
                    except:
                        stakes.append(0)
                else:
                    # Try to parse as number directly
                    clean_stake = re.sub(r'[^\d.]', '', stake_str)
                    try:
                        stakes.append(float(clean_stake))
                    except:
                        stakes.append(0)

            total_stakes = sum(stakes)

            # Count unique customers (unique Id values)
            unique_customers = dest_data['Id'].nunique()
        else:
            unique_bet_ids = 0
            total_stakes = 0
            unique_customers = 0

        results.append({
            'Brand': display_name,
            'Single Bets': '',
            'Single Stakes': '',
            'Total Bets': unique_bet_ids,
            'Total Stakes': f"£{total_stakes:.2f}",
            'Total Unique Customers': unique_customers
        })

    # Create DataFrame and add sort order
    results_df = pd.DataFrame(results)
    sort_order = {'Betfair': 1, 'Paddy Power': 2, 'SBGv2': 3}
    results_df['sort_order'] = results_df['Brand'].map(sort_order)
    results_df = results_df.sort_values('sort_order').drop('sort_order', axis=1)

    return results_df

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
        # Common replacements - remove periods to prevent double periods
        replacements = [
            ('void', 'voided'),
            ('palp', 'palped'),
            ('unsettle', 'unsettled'),
            ('resettle', 'resettled'),
            ('reprice', 'repriced'),
            ('cancel', 'cancelled'),
            ('apply liability', 'applied liability'),
            ('reverse payout', 'reversed payout'),
            ('suspend', 'suspended'),
            ('reopen', 'reopened'),
            ('close', 'closed'),
            ('revert', 'reverted'),
            ('adjust', 'adjusted'),
            ('correct', 'corrected')
        ]

        # Remove common question starters and convert
        removal_patterns = [
            (r'^please\s+', ''),
            (r'^if\s+possible\s*,?\s*', ''),
            (r'^can\s+any\s+', ''),
            (r'^can\s+we\s+', ''),
            (r'^can\s+this\s+be\s+', ''),
            (r'^can\s+all\s+(.+?)\s+be\s+(.+)', r'all \1 have been \2'),
        ]

        # Apply removal patterns first
        for pattern, replacement in removal_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Apply word replacements (remove periods to prevent double periods)
        for old, new in replacements:
            # Match the word and capture any trailing period
            pattern = r'\b' + re.escape(old) + r'(\.?)\b'
            # Replace with new word, keeping any original period
            text = re.sub(pattern, new + r'\1', text, flags=re.IGNORECASE)

        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]

        return text.rstrip('.')

    # Process action
    action_str = ""
    if action:
        action_processed = to_past_tense(action)
        if action_processed:
            action_str = action_processed + "."

    # Combine all parts (skip empty ones)
    parts = [part for part in [event_market_str, cause_str, action_str] if part]
    result = " ".join(parts)

    return result

def main():
    """Main Streamlit application"""

    # Custom CSS for blue theme
    st.markdown("""
    <style>
    /* Force light theme and prevent dark mode override */
    .stApp {
        background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #1d4ed8 100%) !important;
        min-height: 100vh;
    }

    /* Main app background with darker blue gradient */
    .main .block-container {
        background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #1d4ed8 100%) !important;
        min-height: 100vh;
    }

    /* Override any dark mode settings */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #1d4ed8 100%) !important;
    }

    /* Alternative solid light blue background (uncomment to use) */
    /*
    .main .block-container {
        background-color: #e8f4f8;
    }
    */

    /* Header styling */
    .stTitle {
        color: white;
        font-weight: bold;
    }

    /* Button styling - only buttons get blue color */
    .stButton > button {
        background-color: #3b82f6;
        color: white !important;
        border: none;
        border-radius: 5px;
        font-weight: bold;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background-color: #2563eb;
        color: white !important;
    }

    .stButton > button:active,
    .stButton > button:focus {
        background-color: #2563eb;
        color: white !important;
        outline: 2px solid #3b82f6;
        outline-offset: 2px;
        box-shadow: none;
    }

    /* Primary button styling */
    .stButton > button[kind="primary"] {
        background-color: #3b82f6;
        color: white !important;
    }

    .stButton > button[kind="primary"]:hover {
        background-color: #2563eb;
        color: white !important;
    }

    .stButton > button[kind="primary"]:active,
    .stButton > button[kind="primary"]:focus {
        background-color: #2563eb;
        color: white !important;
        outline: 2px solid #3b82f6;
        outline-offset: 2px;
        box-shadow: none;
    }

    /* Multiselect styling - blue color for the selected items */
    .stMultiSelect > div > div > div[data-baseweb="select"] {
        border: 1px solid #ddd;
    }

    .stMultiSelect .stMultiSelect > div > div > div[data-baseweb="select"] > div {
        border: 1px solid #ddd;
    }

    /* Selected multiselect tags get blue color */
    .stMultiSelect span[data-baseweb="tag"] {
        background-color: #3b82f6 !important;
        color: white !important;
    }

    .stMultiSelect span[data-baseweb="tag"] svg {
        fill: white !important;
    }

    /* Normal input borders - light gray */
    .stSelectbox > div > div {
        background-color: white;
        border: 1px solid #ddd;
    }

    .stTextInput > div > div > input {
        border: 1px solid #ddd;
    }

    .stTextArea > div > div > textarea {
        border: 1px solid #ddd;
    }

    /* File uploader styling - blue background with white text */
    .stFileUploader > div {
        border: 2px dashed #4a90e2;
        border-radius: 10px;
        background-color: #4a90e2 !important;
        color: white !important;
    }

    .stFileUploader > div * {
        color: white !important;
    }

    /* Override all file uploader text and icons to be white */
    .stFileUploader label, .stFileUploader p, .stFileUploader span {
        color: white !important;
    }

    /* File uploader button styling - darker blue to match theme */
    .stFileUploader button {
        background-color: #3b82f6 !important;
        color: white !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 4px !important;
    }

    .stFileUploader button:hover {
        background-color: #2563eb !important;
        border-color: #2563eb !important;
    }

    .stFileUploader button:focus {
        background-color: #2563eb !important;
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.5) !important;
    }

    /* Info and success boxes - blue theme */
    .stInfo {
        background-color: #dbeafe;
        border: 1px solid #3b82f6;
        color: #2c3e50;
    }

    .stSuccess {
        background-color: #e6f7e6;
        border: 1px solid #b3d9b3;
    }

    /* Subheader styling */
    .css-1629p8f h2, .css-1629p8f h3 {
        color: white;
    }

    /* Force all text to white color */
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: white !important;
    }

    /* Force all headings to white */
    h1, h2, h3, h4, h5, h6 {
        color: white !important;
    }

    /* Force paragraph text to white */
    p, span, div {
        color: white !important;
    }

    /* Force Streamlit specific text elements to white */
    .css-1629p8f, .css-1629p8f h1, .css-1629p8f h2, .css-1629p8f h3, .css-1629p8f h4 {
        color: white !important;
    }

    /* Force all text in main content area to white */
    .main .block-container, .main .block-container * {
        color: white !important;
    }

    /* Force sidebar text to white if applicable */
    .css-1d391kg, .css-1d391kg * {
        color: white !important;
    }

    /* Force metric labels and values to white */
    .metric-container, .metric-container * {
        color: white !important;
    }

    /* Additional text elements */
    .stSelectbox label, .stMultiSelect label, .stTextInput label, .stTextArea label {
        color: white !important;
    }

    /* Force all div text to white */
    div[data-testid="stMarkdownContainer"] {
        color: white !important;
    }

    div[data-testid="stMarkdownContainer"] * {
        color: white !important;
    }

    /* Data source button container styling */
    .stColumns > div {
        padding: 0 5px;
    }

    /* Prevent text selection highlighting and color changes */
    .stButton > button {
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }

    /* Prevent any unwanted color changes on click */
    .stButton > button * {
        color: white !important;
    }

    /* Dropdown styling - set text color to white */
    .stSelectbox > div > div p, .stMultiSelect > div > div > div > div p {
        color: white !important;
    }

    /* The actual dropdown menu */
    .stSelectbox > div > div ul, .stMultiSelect > div > div > div > div ul {
        color: white !important;
    }

    /* Dropdown text on hover */
    .stSelectbox > div > div ul li:hover, .stMultiSelect > div > div > div > div ul li:hover {
        color: white !important;
    }

    /* Date input styling - white text */
    .stDateInput > div > div > input {
        color: white !important;
    }

    /* Text input styling - white text */
    .stTextInput > div > div > input {
        color: white !important;
    }

    /* Text area styling - white text */
    .stTextArea > div > div > textarea {
        color: white !important;
    }

    </style>
    """, unsafe_allow_html=True)

    st.title("Error Logging Analysis Tool")

    # Initialize session state for data source selection
    if 'data_source' not in st.session_state:
        st.session_state.data_source = None

    # Data source selection buttons
    st.subheader("Select Data Source")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Excel Upload Original\n(one hour behind)", use_container_width=True):
            st.session_state.data_source = "excel_original"

    with col2:
        if st.button("Excel Upload (correct time, same as fieldbook)", use_container_width=True):
            st.session_state.data_source = "excel_corrected"

    with col3:
        if st.button("Global Fieldbook Paste", use_container_width=True):
            st.session_state.data_source = "fieldbook_paste"

    # Show selected data source
    if st.session_state.data_source:
        if st.session_state.data_source == "excel_original":
            st.info("Selected: Excel Upload Original (one hour behind)")
        elif st.session_state.data_source == "excel_corrected":
            st.info("Selected: Excel Upload Corrected (correct time)")
        elif st.session_state.data_source == "fieldbook_paste":
            st.info("Selected: Global Fieldbook Paste")

    # Process based on selected data source
    if st.session_state.data_source == "fieldbook_paste":
        # Fieldbook paste interface
        st.header("📋 Paste Fieldbook Data")
        st.write("Paste your fieldbook data below (tab-separated format)")

        paste_data = st.text_area(
            "Paste Data Here",
            height=200,
            help="Paste tab-separated data with columns: Bet Id, Dest, Shop, Stake, etc."
        )

        # Error description input for fieldbook paste
        st.subheader("Paste Trader Error Description (optional)")
        trader_error_raw_fieldbook = st.text_area("Paste Trader Error Description (optional)", value="", height=180, key="trader_error_raw_fieldbook")
        generated_error_description_fieldbook = ""
        if trader_error_raw_fieldbook.strip():
            generated_error_description_fieldbook = parse_trader_error(trader_error_raw_fieldbook)

        # Show Generate Analysis button regardless of whether data is pasted
        if st.button("Generate Analysis", type="primary"):
            if not paste_data.strip():
                st.warning("Please paste some data first")
            else:
                st.header("📈 Analysis Results")

                # Show generated error description if available
                if generated_error_description_fieldbook:
                    st.subheader("Generated Error Description")

                    # Create a copyable text area with copy button
                    col1, col2 = st.columns([6, 1])
                    with col1:
                        # Custom styled text area with dark text
                        st.markdown(
                            f"""
                            <div style="
                                background-color: #4a90e2;
                                color: #1a1a1a !important;
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
                            "><span style="color: #666666 !important;">{generated_error_description_fieldbook}</span></div>
                            """,
                            unsafe_allow_html=True
                        )
                    with col2:
                        # Use HTML and JavaScript for a working copy button
                        escaped_error_fieldbook = generated_error_description_fieldbook.replace('`', '\\`').replace('\n', '\\n').replace('\r', '\\r').replace('\\', '\\\\').replace("'", "\\'")

                        copy_button_html_fieldbook = f"""
                        <div style="margin-top: 25px;">
                            <button 
                                onclick="copyToClipboardFieldbook()" 
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
                        function copyToClipboardFieldbook() {{
                            const text = `{escaped_error_fieldbook}`;
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
                        components.html(copy_button_html_fieldbook, height=80)

                with st.spinner("Processing pasted data..."):
                    results_df = process_fieldbook_paste(paste_data)

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
                            'Single Bets': '',
                            'Single Stakes': '',
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
                    else:
                        st.error("No valid data found in pasted content")

    elif st.session_state.data_source in ["excel_original", "excel_corrected"]:
        # Excel upload interface
        st.header("Upload Data Files")
        uploaded_files = st.file_uploader(
            "Choose Excel files", 
            type=['xlsx', 'xls'], 
            accept_multiple_files=True,
            help="Upload one or more Excel files containing betting data"
        )

        if uploaded_files:
            # Load and process data
            df = load_excel_data(uploaded_files)

            if df is None or df.empty:
                st.error("No data found in uploaded files")
                return

            # Apply time correction if needed
            if st.session_state.data_source == "excel_corrected" and 'TimeBetStruckAt' in df.columns:
                df['TimeBetStruckAt'] = pd.to_datetime(df['TimeBetStruckAt']) + pd.Timedelta(hours=1)
                st.success(f"Successfully loaded {len(df)} records from {len(uploaded_files)} file(s) with time correction (+1 hour)")
            else:
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
            if trader_error_raw.strip():
                generated_error_description = parse_trader_error(trader_error_raw)

            # Process and display results
            st.header("📈 Analysis Results")

            if st.button("Generate Analysis", type="primary"):
                with st.spinner("Processing data..."):
                    # Build lists for process_betting_data
                    selected_markets_list = selected_markets if selected_markets else []
                    selected_selections_list = []
                    for market, selections in market_selection_map.items():
                        if selections:
                            selected_selections_list.extend(selections)

                    results_df = process_betting_data(
                        df, 
                        selected_markets_list, 
                        selected_selections_list, 
                        start_datetime, 
                        end_datetime
                    )

                # Show generated error description if available
                if generated_error_description:
                    st.subheader("Generated Error Description")

                    # Create a copyable text area with copy button
                    col1, col2 = st.columns([6, 1])
                    with col1:
                        # Use native Streamlit text area that adapts to theme
                        st.text_area(
                            "Copy Text",
                            value=generated_error_description,
                            height=120,
                            disabled=True,
                            key="copy_area_excel",
                            label_visibility="collapsed"
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
                    total_row = {
                        'Brand': 'Totals',
                        'Single Bets': '',
                        'Single Stakes': '',
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
        else:
            st.info("Please upload one or more Excel files to begin analysis")

    else:
        st.write("Please select a data source to continue.")

    # Footer
    st.markdown("---")
    st.caption("Betting Data Analysis Tool - Built with Streamlit")

if __name__ == "__main__":
    main()