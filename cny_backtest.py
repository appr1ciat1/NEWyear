
import yfinance as yf
import pandas as pd
from datetime import datetime
import sys
import os
import re

# Reference: Last Trading Day (H) and First Trading Day (I) for 2016-2025
CNY_DATES = {
    2016: {"H": "2016-02-03", "I": "2016-02-15"},
    2017: {"H": "2017-01-24", "I": "2017-02-02"},
    2018: {"H": "2018-02-12", "I": "2018-02-21"},
    2019: {"H": "2019-01-30", "I": "2019-02-11"},
    2020: {"H": "2020-01-20", "I": "2020-01-30"},
    2021: {"H": "2021-02-05", "I": "2021-02-17"},
    2022: {"H": "2022-01-26", "I": "2022-02-07"},
    2023: {"H": "2023-01-17", "I": "2023-01-30"},
    2024: {"H": "2024-02-05", "I": "2024-02-15"},
    2025: {"H": "2025-01-22", "I": "2025-02-03"},
}

def load_stock_list(csv_path="StockList.csv"):
    """
    Parses the CSV to create a mapping of stock code to yahoo ticker suffix.
    Returns a dict: { '2330': '2330.TW', ... }
    """
    mapping = {}
    if not os.path.exists(csv_path):
        return mapping
    
    try:
        # Read CSV with varying encoding just in case, usually Big5 or UTF-8 for TW data
        # The preview showed Chinese characters, let's try reading as text first to handle the `="2330"` format
        with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = f.readlines()
        
        # Skip header if present (line 1)
        start_idx = 1 if "排名" in lines[0] else 0
        
        for line in lines[start_idx:]:
            # Simple parsing to handle potential quoting like ="2330"
            parts = line.split(',')
            if len(parts) < 4:
                continue
                
            # Code is in index 1, Market in index 3 based on preview
            # format: "1",="2330","台積電","市",...
            
            raw_code = parts[1].replace('=', '').replace('"', '').strip()
            market = parts[3].replace('"', '').strip()
            
            suffix = ".TW"
            if market == "櫃":
                suffix = ".TWO"
            
            mapping[raw_code] = f"{raw_code}{suffix}"
            
    except Exception as e:
        print(f"Error reading stock list: {e}")
        
    return mapping

def calculate_returns(input_code, stock_mapping=None):
    # Resolve ticker
    ticker = input_code
    if stock_mapping and input_code in stock_mapping:
        ticker = stock_mapping[input_code]
    else:
        # Fallback heuristic
        if not ticker.endswith(".TW") and not ticker.endswith(".TWO"):
            ticker = f"{ticker}.TW"

    print(f"Fetching data for {ticker}...")
    
    # Download data - Use auto_adjust=True to get Adjusted Close used for returns
    # or just use 'Adj Close' column explicitly. yfinance download returns 'Adj Close' by default if not auto_adjusted.
    # explicit is better.
    data = yf.download(ticker, start="2015-11-01", end=datetime.now().strftime("%Y-%m-%d"), progress=False)
    
    if data.empty:
        print(f"No data found for {ticker}")
        return

    # Ensure index is datetime and sorted
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    # Use 'Adj Close' for standard return calculations
    # Handle MultiIndex columns if present
    # yfinance structure varies by version. Recent versions might be MultiIndex (Price, Ticker).
    
    try:
        if isinstance(data.columns, pd.MultiIndex):
            # Check if 'Adj Close' exists, otherwise fallback to 'Close'
            if 'Adj Close' in data.columns.get_level_values(0):
                prices = data['Adj Close']
            else:
                prices = data['Close']
            
            # If still MultiIndex (e.g. Ticker level), select the ticker
            if isinstance(prices, pd.DataFrame):
                prices = prices.iloc[:, 0]
        else:
             if 'Adj Close' in data.columns:
                 prices = data['Adj Close']
             else:
                 prices = data['Close']
    except Exception as e:
        print(f"Error processing columns: {e}")
        return

    results = []

    # Process each year from 2025 down to 2016
    for year in range(2025, 2015, -1):
        h_date_str = CNY_DATES[year]["H"]
        i_date_str = CNY_DATES[year]["I"]
        
        valid_dates = prices.index
        
        try:
            date_h = pd.Timestamp(h_date_str)
            date_i = pd.Timestamp(i_date_str)
            
            # Snap to nearest valid trading day if exact date missing (e.g. suspension)
            if date_h not in valid_dates:
                # Last trading day: look backwards
                prev_dates = valid_dates[valid_dates <= date_h]
                if not prev_dates.empty:
                    date_h = prev_dates[-1]
            
            if date_i not in valid_dates:
                # First trading day: look forwards
                next_dates = valid_dates[valid_dates >= date_i]
                if not next_dates.empty:
                    date_i = next_dates[0]

            if date_h not in valid_dates or date_i not in valid_dates:
                # Should verify these are actually in the index now
                continue

            h_loc = valid_dates.get_loc(date_h)
            i_loc = valid_dates.get_loc(date_i)

            def get_point(base_loc, offset_val):
                idx = base_loc + offset_val
                if 0 <= idx < len(valid_dates):
                    d = valid_dates[idx]
                    p = prices.iloc[idx]
                    return d, p
                return None, None

            # Offsets defined relative to H (Last Day) and I (First Day)
            # 1.前30日是［A］ -> H - 30
            # ...
            
            points = {}
            # Relative to H
            offsets_h = {
                "A": -30, "B": -25, "C": -20, "D": -15, "E": -10, "F": -5, "G": -1, "H": 0
            }
            for code, off in offsets_h.items():
                points[code] = get_point(h_loc, off)
            
            # Relative to I
            offsets_i = {
                "I": 0, "J": 1, "K": 2, "L": 4
            }
            for code, off in offsets_i.items():
                points[code] = get_point(i_loc, off)

            # Calculate Returns
            row = {"Year": year}
            
            # Populate Dates and Prices
            for code in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]:
                d, p = points[code]
                date_str = d.strftime('%Y-%m-%d') if d else "N/A"
                price_str = f"{p:.2f}" if (d is not None and not pd.isna(p)) else "N/A"
                row[f"Info_{code}"] = f"{date_str} ({price_str})"
                points[code] = (d, p) # Store for calcs

            # 13-25 Returns
            calc_pairs = [
                ("A", "F"), ("A", "G"), ("A", "H"), ("A", "I"), ("A", "J"), ("A", "K"), ("A", "L"),
                ("D", "G"), ("D", "H"), ("D", "I"), ("D", "J"), ("D", "K"), ("D", "L")
            ]
            
            for start, end in calc_pairs:
                d_s, p_s = points[start]
                d_e, p_e = points[end]
                col_name = f"{start}~{end} (%)"
                
                if p_s is not None and p_e is not None and not pd.isna(p_s) and not pd.isna(p_e):
                    # Standard Return: (End - Start) / Start
                    ret = ((p_e - p_s) / p_s) * 100
                    row[col_name] = round(ret, 2)
                else:
                    row[col_name] = None
            
            results.append(row)

        except Exception as e:
            print(f"Error processing {year}: {e}")
    
    res_df = pd.DataFrame(results)
    
    # Display Logic
    return_cols = [
        "A~F (%)", "A~G (%)", "A~H (%)", "A~I (%)", "A~J (%)", "A~K (%)", "A~L (%)",
        "D~G (%)", "D~H (%)", "D~I (%)", "D~J (%)", "D~K (%)", "D~L (%)"
    ]
    
    date_cols = [f"Info_{c}" for c in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]]
    
    print("\n" + "="*80)
    print(f"Results for {ticker} (Using Adjusted Close)")
    print("="*80)
    
    if not res_df.empty:
        for _, r in res_df.iterrows():
            print(f"\nYear: {r['Year']}")
            print("-" * 20)
            print("Returns (%):")
            for col in return_cols:
                val = r.get(col, 'N/A')
                print(f"  {col:<10}: {val}")
            print("-" * 20)
            print("Date (Price):")
            for col in date_cols:
                original_code = col.split('_')[1]
                val = r.get(col, 'N/A')
                print(f"  [{original_code}]: {val}")
    else:
        print("No results generated.")

if __name__ == "__main__":
    # Load mapping
    list_path = os.path.join(os.path.dirname(__file__), "StockList.csv")
    stock_map = load_stock_list(list_path)
    
    if len(sys.argv) > 1:
        user_input = sys.argv[1]
    else:
        user_input = input("Enter stock code (e.g., 2330): ").strip()
    
    calculate_returns(user_input, stock_map)

