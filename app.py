
import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import time

# --- Constants & Configuration ---
st.set_page_config(page_title="Lunar New Year Backtest Tool", layout="wide")

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

COLUMN_RENAME_MAP = {
    "A~F (%)": "春節前最後交易日的前30日~春節前最後交易日的前5日",
    "D~F (%)": "春節前最後交易日的前15日~春節前最後交易日的前5日",
    "A~G (%)": "春節前最後交易日的前30日~春節前最後交易日的前1日",
    "D~G (%)": "春節前最後交易日的前15日~春節前最後交易日的前1日",
    "A~H (%)": "春節前最後交易日的前30日~春節前最後交易日",
    "D~H (%)": "春節前最後交易日的前15日~春節前最後交易日",
    "A~I (%)": "春節前最後交易日的前30日~春節後開始交易日",
    "D~I (%)": "春節前最後交易日的前15日~春節後開始交易日",
    "A~J (%)": "春節前最後交易日的前30日~春節後開始交易日的後1日",
    "D~J (%)": "春節前最後交易日的前15日~春節後開始交易日的後1日",
    "A~K (%)": "春節前最後交易日的前30日~春節後開始交易日的後2日",
    "D~K (%)": "春節前最後交易日的前15日~春節後開始交易日的後2日",
    "A~L (%)": "春節前最後交易日的前30日~春節後開始交易日的後4日",
    "D~L (%)": "春節前最後交易日的前15日~春節後開始交易日的後4日"
}

# --- Functions ---

@st.cache_data
def load_stock_list(csv_path="StockList.csv"):
    """
    Parses the CSV to create a mapping of stock code to yahoo ticker suffix.
    Returns:
        dict: { '2330': '2330.TW', ... },
        list: List of display strings for dropdown e.g. "2330 (台積電)"
    """
    mapping = {}
    display_list = []
    
    if not os.path.exists(csv_path):
        return mapping, display_list
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = f.readlines()
        
        start_idx = 1 if len(lines) > 0 and "排名" in lines[0] else 0
        
        for line in lines[start_idx:]:
            parts = line.split(',')
            if len(parts) < 4:
                continue
            
            raw_code = parts[1].replace('=', '').replace('"', '').strip()
            name = parts[2].replace('"', '').strip()
            market = parts[3].replace('"', '').strip()
            
            suffix = ".TW"
            if market == "櫃":
                suffix = ".TWO"
            
            full_ticker = f"{raw_code}{suffix}"
            mapping[raw_code] = full_ticker
            display_str = f"{raw_code} - {name}"
            display_list.append(display_str)
            
    except Exception as e:
        st.error(f"Error reading stock list: {e}")
        
    return mapping, display_list

def calculate_returns(ticker):
    # Download data
    with st.spinner(f"Fetching data for {ticker}..."):
        data = yf.download(ticker, start="2015-11-01", end=datetime.now().strftime("%Y-%m-%d"), progress=False)
    
    if data.empty:
        st.warning(f"No data found for {ticker}")
        return pd.DataFrame()

    # Ensure index is datetime and sorted
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    # Use 'Adj Close'
    try:
        if isinstance(data.columns, pd.MultiIndex):
            if 'Adj Close' in data.columns.get_level_values(0):
                prices = data['Adj Close']
            else:
                prices = data['Close']
            
            if isinstance(prices, pd.DataFrame):
                prices = prices.iloc[:, 0]
        else:
             if 'Adj Close' in data.columns:
                 prices = data['Adj Close']
             else:
                 prices = data['Close']
    except Exception as e:
        st.error(f"Error processing columns: {e}")
        return pd.DataFrame()

    results = []

    # Process each year from 2025 down to 2016
    for year in range(2025, 2015, -1):
        h_date_str = CNY_DATES[year]["H"]
        i_date_str = CNY_DATES[year]["I"]
        
        valid_dates = prices.index
        
        try:
            date_h = pd.Timestamp(h_date_str)
            date_i = pd.Timestamp(i_date_str)
            
            # Snap to nearest valid trading day
            if date_h not in valid_dates:
                prev_dates = valid_dates[valid_dates <= date_h]
                if not prev_dates.empty:
                    date_h = prev_dates[-1]
            
            if date_i not in valid_dates:
                next_dates = valid_dates[valid_dates >= date_i]
                if not next_dates.empty:
                    date_i = next_dates[0]

            if date_h not in valid_dates or date_i not in valid_dates:
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

            row = {"Year": str(year)} # Year as string for cleaner display
            
            # 13-25 Returns
            calc_pairs = [
                ("A", "F"), ("D", "F"), 
                ("A", "G"), ("D", "G"),
                ("A", "H"), ("D", "H"),
                ("A", "I"), ("D", "I"), 
                ("A", "J"), ("D", "J"), 
                ("A", "K"), ("D", "K"), 
                ("A", "L"), ("D", "L")
            ]
            
            for start, end in calc_pairs:
                d_s, p_s = points[start]
                d_e, p_e = points[end]
                
                col_key = f"{start}~{end} (%)" # Intermediate key
                
                if p_s is not None and p_e is not None and not pd.isna(p_s) and not pd.isna(p_e):
                    ret = ((p_e - p_s) / p_s) * 100
                    # Standard format: 2.32 %
                    row[col_key] = f"{ret:.2f} %"
                else:
                    row[col_key] = "N/A"
            
            # Dates and Prices
            for code in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]:
                d, p = points[code]
                date_str = d.strftime('%Y-%m-%d') if d else "N/A"
                price_str = f"{p:.2f}" if (d is not None and not pd.isna(p)) else "N/A"
                row[f"Info_{code}"] = f"{date_str} ({price_str})"

            results.append(row)

        except Exception as e:
            # st.error(f"Error processing {year}: {e}")
            pass
    
    return pd.DataFrame(results)

@st.cache_data(ttl=3600)
def batch_calculate_returns(stock_map):
    tickers_map = {v: k for k, v in stock_map.items()} 
    tickers_list = list(stock_map.values())
    
    start_date = "2015-11-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    status_text = st.empty()
    bar = st.progress(0)
    status_text.text("正在下載所有股票數據... (這可能需要幾分鐘)")
    
    try:
        data = yf.download(tickers_list, start=start_date, end=end_date, progress=False, threads=True)
    except Exception as e:
        st.error(f"Batch download failed: {e}")
        return pd.DataFrame()
        
    bar.progress(30)
    status_text.text("正在計算各股績效...")

    prices_df = pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        if 'Adj Close' in data.columns.get_level_values(0):
            prices_df = data['Adj Close']
        else:
            prices_df = data['Close']
    else:
        prices_df = data

    if not isinstance(prices_df.index, pd.DatetimeIndex):
         prices_df.index = pd.to_datetime(prices_df.index)
    prices_df = prices_df.sort_index()

    final_stats = []
    processed_count = 0
    total_tickers = len(tickers_list)
    valid_dates = prices_df.index
    
    year_indices = {}
    for year in range(2025, 2015, -1):
        h_str = CNY_DATES[year]["H"]
        i_str = CNY_DATES[year]["I"]
        d_h = pd.Timestamp(h_str)
        d_i = pd.Timestamp(i_str)
        
        if d_h not in valid_dates:
            prev = valid_dates[valid_dates <= d_h]
            if not prev.empty: d_h = prev[-1]
        
        if d_i not in valid_dates:
            nxt = valid_dates[valid_dates >= d_i]
            if not nxt.empty: d_i = nxt[0]
            
        if d_h in valid_dates and d_i in valid_dates:
             h_loc = valid_dates.get_loc(d_h)
             i_loc = valid_dates.get_loc(d_i)
             year_indices[year] = (h_loc, i_loc)

    for ticker in prices_df.columns:
        series = prices_df[ticker]
        metric_values = {
            "A~F (%)": [], "D~F (%)": [],
            "A~H (%)": [], "D~H (%)": [],
            "A~I (%)": [], "D~I (%)": [],
            "A~J (%)": [], "D~J (%)": [],
            "A~L (%)": [], "D~L (%)": [] 
        }
        
        for year, (h_loc, i_loc) in year_indices.items():
            def get_p(base_loc, off):
                idx = base_loc + off
                if 0 <= idx < len(series):
                    return series.iloc[idx]
                return None

            try:
                p_A = get_p(h_loc, -30)
                p_D = get_p(h_loc, -15)
                p_F = get_p(h_loc, -5)
                p_H = get_p(h_loc, 0)
                p_I = get_p(i_loc, 0)
                p_J = get_p(i_loc, 1)
                p_L = get_p(i_loc, 4)
                
                pairs = [
                    ("A~F (%)", p_A, p_F), ("D~F (%)", p_D, p_F),
                    ("A~H (%)", p_A, p_H), ("D~H (%)", p_D, p_H),
                    ("A~I (%)", p_A, p_I), ("D~I (%)", p_D, p_I),
                    ("A~J (%)", p_A, p_J), ("D~J (%)", p_D, p_J),
                    ("A~L (%)", p_A, p_L), ("D~L (%)", p_D, p_L),
                ]
                
                for key, start, end in pairs:
                    if start is not None and end is not None and not pd.isna(start) and not pd.isna(end) and start != 0:
                        ret = (end - start) / start * 100
                        metric_values[key].append(ret)
            except Exception:
                continue
                
        if any(len(v) > 0 for v in metric_values.values()):
            raw_code = tickers_map.get(ticker, ticker)
            row = {"Code": raw_code}
            for k, v in metric_values.items():
                if v:
                    avg_ret = sum(v) / len(v)
                    row[k] = avg_ret
                else:
                    row[k] = None
            final_stats.append(row)
        
        processed_count += 1
        if processed_count % 10 == 0:
            prog = 30 + int((processed_count / total_tickers) * 70)
            bar.progress(min(prog, 100))

    bar.progress(100)
    status_text.text("計算完成")
    time.sleep(1)
    status_text.empty()
    bar.empty()
    
    return pd.DataFrame(final_stats)

# --- Main App ---

st.title("台灣股市春節前後漲跌幅回測工具")

# Sidebar for inputs
with st.sidebar:
    st.header("功能選擇")
    stock_map, display_list = load_stock_list()
    
    # Helper to get name
    def get_stock_name(code):
        for s in display_list:
            if s.startswith(code):
                return s.split(" - ")[1]
        return ""

    mode = st.radio("模式", ["個別查詢 (Individual)", "排行榜 (Ranking 10)"])
    
    if mode == "個別查詢 (Individual)":
        st.subheader("查詢設定")
        input_mode = st.radio("輸入方式", ["列表選擇 (Top 300)", "手動輸入代碼"])
        
        ticker = None
        if input_mode == "列表選擇 (Top 300)":
            selected_item = st.selectbox("選擇股票", display_list)
            if selected_item:
                code = selected_item.split(" - ")[0]
                ticker = stock_map.get(code, f"{code}.TW")
        else:
            user_code = st.text_input("輸入股票代碼 (例如 2330)", "2330")
            ticker = stock_map.get(user_code, f"{user_code}.TW")
            
        st.info(f"查詢標的: {ticker}")
        run_btn = st.button("開始回測")
        
    else:
        st.subheader("排行榜設定")
        st.info("將計算所有列表股票的平均漲跌幅 (2016-2025)，並列出前 50 名。")
        rank_btn = st.button("生成/更新 排行榜")

# Main Content
if mode == "個別查詢 (Individual)":
    if run_btn and ticker:
        df_res = calculate_returns(ticker)
        
        if not df_res.empty:
            # Rename columns using the map
            df_display = df_res.rename(columns=COLUMN_RENAME_MAP)
            
            # --- NEW: Summary Table (Pivot View) ---
            st.subheader("統計彙整 (Summary Table)")
            
            # 1. Prepare data for pivot
            # Key order defining the sort order of rows
            key_order = [
                "A~F (%)", "D~F (%)",
                "A~G (%)", "D~G (%)",
                "A~H (%)", "D~H (%)",
                "A~I (%)", "D~I (%)", 
                "A~J (%)", "D~J (%)", 
                "A~K (%)", "D~K (%)", 
                "A~L (%)", "D~L (%)"
            ]
            
            # Filter valid keys that actually exist in df_res
            valid_keys = [k for k in key_order if k in df_res.columns]
            
            try:
                # Set index to Year
                df_pivot_source = df_res.set_index("Year")[valid_keys]
                
                # Transpose: Rows (Years) -> Cols, Cols (Metrics) -> Rows
                df_summary = df_pivot_source.T
                
                # Map index to Chinese
                df_summary.index = df_summary.index.map(COLUMN_RENAME_MAP)
                df_summary.index.name = "統計區間"

                # Reindex to enforce the desired order of rows
                ordered_mapped_names = [COLUMN_RENAME_MAP[k] for k in key_order if k in COLUMN_RENAME_MAP and k in valid_keys]
                df_summary = df_summary.reindex(ordered_mapped_names)
                
                st.dataframe(df_summary, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error creating summary table: {e}")

            st.divider()

            # Display Year by Year
            st.subheader(f"{ticker} 詳細數據 (Yearly Details)")
            
            for index, row in df_display.iterrows():
                with st.expander(f"{row['Year']} 年數據", expanded=False):
                    
                    st.markdown("### 漲跌幅分析")
                    
                    # Split content into two groups
                    group_30_data = {}
                    group_15_data = {}
                    
                    # Define a specific order for display within the expander
                    display_order_A = [
                        "A~F (%)", "A~G (%)", "A~H (%)", "A~I (%)", "A~J (%)", "A~K (%)", "A~L (%)"
                    ]
                    display_order_D = [
                        "D~F (%)", "D~G (%)", "D~H (%)", "D~I (%)", "D~J (%)", "D~K (%)", "D~L (%)"
                    ]

                    for key in display_order_A:
                        label = COLUMN_RENAME_MAP.get(key, key) # Use mapped name, fallback to key
                        val = row.get(label, "N/A")
                        group_30_data[label] = val
                    
                    for key in display_order_D:
                        label = COLUMN_RENAME_MAP.get(key, key) # Use mapped name, fallback to key
                        val = row.get(label, "N/A")
                        group_15_data[label] = val
                    
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        st.markdown("**前 30 日起算**")
                        df_30 = pd.DataFrame(list(group_30_data.items()), columns=["區間", "漲跌幅"])
                        st.dataframe(df_30, hide_index=True, use_container_width=True)
                    
                    with c2:
                        st.markdown("**前 15 日起算**")
                        df_15 = pd.DataFrame(list(group_15_data.items()), columns=["區間", "漲跌幅"])
                        st.dataframe(df_15, hide_index=True, use_container_width=True)
                    
                    st.divider()
                    
                    # Date Info Section
                    st.markdown("**日期與股價 (Date & Price)**")
                    cols = st.columns(3)
                    date_keys = [f"Info_{c}" for c in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]]
                    
                    for i, d_key in enumerate(date_keys):
                        original_code = d_key.split('_')[1]
                        val = row.get(d_key, "N/A")
                        with cols[i % 3]:
                            st.write(f"**[{original_code}]**: {val}")

        else:
            st.write("無數據顯示")

elif mode == "排行榜 (Ranking 10)":
    if rank_btn:
        df_rank = batch_calculate_returns(stock_map)
        st.session_state['df_rank'] = df_rank # Store in session to persist across selects
    
    if 'df_rank' in st.session_state and not st.session_state['df_rank'].empty:
        df_all = st.session_state['df_rank']
        
        st.subheader("春節前後漲跌幅排行榜 (Top 50)")
        
        # Selector for the 10 Lists
        # Map user friendly names to internal keys
        rank_options = {
            "春節前最後交易日的前30日~春節前最後交易日的前5日": "A~F (%)",
            "春節前最後交易日的前15日~春節前最後交易日的前5日": "D~F (%)",
            "春節前最後交易日的前30日~春節前最後交易日": "A~H (%)",
            "春節前最後交易日的前15日~春節前最後交易日": "D~H (%)",
            "春節前最後交易日的前30日~春節後開始交易日": "A~I (%)",
            "春節前最後交易日的前15日~春節後開始交易日": "D~I (%)",
            "春節前最後交易日的前30日~春節後開始交易日的後1日": "A~J (%)",
            "春節前最後交易日的前15日~春節後開始交易日的後1日": "D~J (%)",
            "春節前最後交易日的前30日~春節後開始交易日的後4日": "A~L (%)",
            "春節前最後交易日的前15日~春節後開始交易日的後4日": "D~L (%)",
        }
        
        selected_label = st.selectbox("選擇統計區間 (依平均漲幅排序)", list(rank_options.keys()))
        selected_col = rank_options[selected_label]
        
        if selected_col in df_all.columns:
            # Sort descending
            df_sorted = df_all.sort_values(by=selected_col, ascending=False).head(50)
            
            # Format logic
            # Add Name column if missing
            # We have 'Code' in df_all
            df_display_rank = df_sorted[["Code", selected_col]].copy()
            df_display_rank["Stock Name"] = df_display_rank["Code"].apply(lambda c: get_stock_name(c))
            
            # Reorder
            df_display_rank = df_display_rank[["Code", "Stock Name", selected_col]]
            df_display_rank.columns = ["代碼", "名稱", "平均漲幅 (%)"]
            
            # Format float
            df_display_rank["平均漲幅 (%)"] = df_display_rank["平均漲幅 (%)"].apply(lambda x: f"{x:.2f}" if x is not None else "N/A")
            
            # Reset index to start at 1
            df_display_rank.reset_index(drop=True, inplace=True)
            df_display_rank.index = df_display_rank.index + 1
            
            st.table(df_display_rank)
        else:
            st.warning("該區間無數據")
    else:
        st.info("請點擊「生成/更新 排行榜」開始計算。")
