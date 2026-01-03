import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime

# --- Configuration ---
st.set_page_config(page_title="Portfolio Tracker", layout="wide")
st.title("🚀 My Wealth Dashboard")

DB_NAME = 'portfolio.db'

# --- Backend Logic ---
def run_query(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

def load_data():
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql("SELECT * FROM transactions ORDER BY date DESC", conn)

def get_current_fx_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        data = ticker.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
        return 34.0
    except:
        return 34.0

def calculate_portfolio(df):
    """
    Core Logic: Converts raw transactions into 'Current Holdings'
    Returns: DataFrame of assets with current market value in THB
    """
    if df.empty:
        return pd.DataFrame(), 0.0

    # 1. Calculate Asset Holdings (Shares)
    # Filter only BUY/SELL
    trades = df[df['type'].isin(['BUY', 'SELL'])].copy()
    
    # Make SELL quantity negative
    trades.loc[trades['type'] == 'SELL', 'quantity'] *= -1
    
    # Group by Ticker to find Net Quantity
    holdings = trades.groupby('ticker')['quantity'].sum().reset_index()
    
    # Remove assets we no longer hold (Qty approx 0)
    holdings = holdings[holdings['quantity'] > 0.00001]
    
    # 2. Get Real-time Prices & Convert to THB
    live_fx = get_current_fx_rate()
    total_portfolio_value_thb = 0
    
    current_prices = []
    market_values_thb = []
    
    for index, row in holdings.iterrows():
        ticker = row['ticker']
        qty = row['quantity']
        
        # Fetch Live Price
        try:
            # Assume tickers with '-' are Crypto/Forex, others are US Stocks
            stock = yf.Ticker(ticker)
            history = stock.history(period="1d")
            if not history.empty:
                current_price = history['Close'].iloc[-1]
            else:
                current_price = 0 # Fallback
        except:
            current_price = 0
            
        # Determine Currency (Simple Logic for MVP: If ticker is AAPL -> USD)
        # In a full app, we would look up the asset's currency from a master table.
        # Here, let's assume everything fetched via YF is USD for simplicity, unless it's THB.
        is_usd = True # Assumption for MVP
        
        # Calculate Value
        val_usd = qty * current_price
        val_thb = val_usd * live_fx if is_usd else val_usd
        
        current_prices.append(current_price)
        market_values_thb.append(val_thb)
        total_portfolio_value_thb += val_thb

    holdings['Current Price ($)'] = current_prices
    holdings['Value (THB)'] = market_values_thb
    
    return holdings, total_portfolio_value_thb

# --- Sidebar: Data Entry (Same as before) ---
with st.sidebar:
    st.header("📝 New Transaction")
    tx_type = st.radio("Type", ["BUY", "SELL", "DEPOSIT", "WITHDRAW", "DIVIDEND"])
    live_fx = get_current_fx_rate()

    with st.form("transaction_form", clear_on_submit=True):
        ticker = ""
        qty = 0.0
        price = 0.0
        fee = 0.0
        wht = 0.0
        currency = "USD"
        fx_rate = live_fx
        notes = ""
        tx_date = st.date_input("Date", datetime.today())
        
        if tx_type in ["BUY", "SELL"]:
            st.caption(f"--- {tx_type} Details ---")
            platform = st.selectbox("Platform", ["Dime", "Binance", "Streaming", "Other"])
            
            raw_ticker = st.text_input("Ticker Symbol", placeholder="e.g. NVDA, BTC").upper()
            
            crypto_map = {
                "BTC": "BTC-USD",
                "ETH": "ETH-USD",
                "SOL": "SOL-USD",
                "DOGE": "DOGE-USD",
                "XRP": "XRP-USD",
                "BNB": "BNB-USD",
                "ADA": "ADA-USD"
            }
            ticker = crypto_map.get(raw_ticker, raw_ticker)
            
            if ticker != raw_ticker:
                st.caption(f"💡 Auto-converted '{raw_ticker}' to '{ticker}' for price fetching")

            col1, col2 = st.columns(2)
            with col1: 
                qty = st.number_input("Quantity", min_value=0.0, format="%.4f")
            with col2: 
                price = st.number_input("Price ($)", min_value=0.0, format="%.2f")
            
            fee = st.number_input("Fee ($)", min_value=0.0, format="%.2f")
            
            with st.expander("Advanced: Currency & FX"):
                currency = st.selectbox("Currency", ["USD", "THB"])
                fx_rate = st.number_input("FX Rate", value=live_fx, format="%.2f")
                
        elif tx_type in ["DEPOSIT", "WITHDRAW"]:
            st.caption(f"--- Cash Flow ---")
            platform = st.selectbox("Wallet", ["Dime", "Binance", "Bank"])
            target_curr = st.selectbox("Currency", ["USD", "THB"])
            ticker = target_curr 
            currency = target_curr
            total_amt = st.number_input("Amount", min_value=0.0, format="%.2f")
            qty = total_amt
            price = 1.0 
            fx_rate = st.number_input("Applied FX", value=live_fx if target_curr == 'USD' else 1.0)

        elif tx_type == "DIVIDEND":
            platform = st.selectbox("Platform", ["Dime", "Binance"])
            ticker = st.text_input("Ticker", placeholder="MSFT").upper()
            price = st.number_input("Net Payout ($)", min_value=0.0)
            wht = st.number_input("WHT ($)", min_value=0.0)
            qty = 1.0

        submitted = st.form_submit_button(f"Save {tx_type}")
        if submitted:
            if tx_type in ["BUY", "SELL"] and not ticker:
                 st.error("Ticker Required!")
            else:
                 try:
                    sql = '''INSERT INTO transactions (date, type, platform, ticker, quantity, price, fee, currency, fx_rate, wht, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)'''
                    run_query(sql, (tx_date, tx_type, platform, ticker, qty, price, fee, currency, fx_rate, wht, notes))
                    st.success("Saved!")
                    st.rerun()
                 except Exception as e:
                    st.error(f"Error: {e}")

# --- MAIN PAGE: THE DASHBOARD ---

# Load Data
raw_df = load_data()

# Create Tabs
tab1, tab2 = st.tabs(["📊 Dashboard", "📝 Raw Data"])

with tab1:
    if raw_df.empty:
        st.info("👋 Welcome! Please add your first transaction in the sidebar.")
    else:
        # 1. Calculate Data
        holdings_df, total_value = calculate_portfolio(raw_df)
        
        # 2. Key Metrics (Top Row)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Portfolio Value", f"฿{total_value:,.2f}")
        col2.metric("FX Rate (USD/THB)", f"฿{live_fx:.2f}")
        col3.metric("Active Assets", len(holdings_df))
        
        st.divider()
        
        # 3. Charts & Tables (Middle)
        col_chart, col_table = st.columns([1, 1])
        
        with col_chart:
            st.subheader("Asset Allocation")
            if not holdings_df.empty:
                # Matplotlib Pie Chart
                fig, ax = plt.subplots()
                ax.pie(holdings_df['Value (THB)'], labels=holdings_df['ticker'], autopct='%1.1f%%', startangle=90)
                ax.axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.
                # Transparent background for dark mode theme
                fig.patch.set_alpha(0) 
                st.pyplot(fig)
            else:
                st.write("No active holdings.")

        with col_table:
            st.subheader("Current Holdings")
            st.dataframe(
                holdings_df, 
                column_config={
                    "Current Price ($)": st.column_config.NumberColumn(format="$%.2f"),
                    "Value (THB)": st.column_config.NumberColumn(format="฿%.2f"),
                },
                hide_index=True
            )

with tab2:
    st.subheader("Transaction History")
    st.dataframe(raw_df, use_container_width=True)