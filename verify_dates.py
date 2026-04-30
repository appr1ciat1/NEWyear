
import yfinance as yf
import pandas as pd

def find_cny_dates():
    # Fetch TSMC data
    print("Fetching data...")
    df = yf.download("2330.TW", start="2016-01-01", end="2026-05-01")
    
    years = range(2016, 2026)
    cny_dates = {}

    for year in years:
        # Filter for Jan/Feb
        subset = df.loc[f"{year}-01-01":f"{year}-03-01"]
        
        # Calculate gap between consecutive trading days
        # We look for the largest gap in Jan/Feb (CNY is the longest holiday)
        dates = subset.index.to_series()
        diffs = dates.diff().dt.days
        
        # Find the max gap
        # The gap starts after the 'Last Trading Day' (H) and ends at 'First Trading Day' (I)
        # diff is (current_date - prev_date). So if diff is large, prev_date is H, current_date is I.
        
        # We need to ignore weekends (gap of 3 days usually). CNY gap is usually > 5 days.
        max_gap_idx = diffs.argmax()
        max_gap_days = diffs.iloc[max_gap_idx]
        
        first_trading_day = dates.iloc[max_gap_idx]
        last_trading_day = dates.iloc[max_gap_idx - 1]
        
        print(f"Year {year}: Last Trading Day (H): {last_trading_day.date()}, First Trading Day (I): {first_trading_day.date()}, Gap: {max_gap_days} days")

if __name__ == "__main__":
    find_cny_dates()
