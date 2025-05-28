# Team Setup Instructions

## Quick Start Guide

### Option 1: Local Installation (Recommended for Teams)

1. **Download all files** from this project folder
2. **Create a new folder** on your computer (e.g., "BettingAnalysisTool")
3. **Copy these files** into your new folder:
   - `app.py` (main application)
   - `README.md` (documentation)
   - `package_requirements.txt` (dependencies list)
   - `setup_instructions.md` (this file)

4. **Install Python** (if not already installed):
   - Download from [python.org](https://python.org)
   - Choose Python 3.11 or newer

5. **Open command prompt/terminal** in your folder and run:
   ```bash
   pip install streamlit pandas openpyxl numpy
   ```

6. **Start the application**:
   ```bash
   streamlit run app.py
   ```

7. **Access the app**: Your browser will automatically open to `http://localhost:8501`

### Option 2: Share Folder Access

You can also:
- Create a shared network drive folder
- Place all files in the shared folder
- Each team member can run the app locally from the shared location

## Team Collaboration

### File Sharing
- Keep your Excel data files in a separate "data" subfolder
- Each team member can upload their own files
- Results can be exported or screenshotted for sharing

### Consistent Usage
- Use the same filtering criteria across team members for consistent results
- Document your analysis parameters for reproducibility

## Troubleshooting

### Common Issues:
1. **"streamlit command not found"**: Make sure Python and pip are properly installed
2. **Import errors**: Run the pip install command again
3. **Port already in use**: Close other Streamlit apps or use `streamlit run app.py --server.port 8502`

### Getting Help:
- Check the README.md for detailed usage instructions
- Ensure your Excel files have the required columns
- Verify date/time formats in your data

## Security Notes
- This tool runs locally on your machine
- No data is sent to external servers
- Excel files are processed locally and securely