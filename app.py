import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(page_title="Portfolio Tracker", layout="wide")
st.title("Wealth Dashboard")

DB_NAME = 'portfolio.db'

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
     //(P/L)
    """
    if df.empty:
        return pd.DataFrame(), 0.0, 0.0, 0.0 
    

    trades = df[df['type'].isin(['BUY', 'SELL'])].copy()
    

    trades['cost_amount'] = trades['quantity'] * trades['price']
    trades.loc[trades['type'] == 'SELL', 'quantity'] *= -1
    trades.loc[trades['type'] == 'SELL', 'cost_amount'] *= -1
    
    summary = trades.groupby('ticker').agg({
        'quantity': 'sum',
        'cost_amount': 'sum'
    }).reset_index()
    
    holdings = summary[summary['quantity'] > 0.00001].copy()
    
    live_fx = get_current_fx_rate()
    
    current_prices = []
    market_values = []
    pnl_values = []
    pnl_percents = []
    
    for index, row in holdings.iterrows():
        ticker = row['ticker']
        qty = row['quantity']
        total_cost = row['cost_amount']
        
        try:
            stock = yf.Ticker(ticker)
            history = stock.history(period="1d")
            if not history.empty:
                current_price = history['Close'].iloc[-1]
            else:
                current_price = 0
        except:
            current_price = 0
            
        market_value = qty * current_price
        
        unrealized_pnl = market_value - total_cost
        pnl_percent = (unrealized_pnl / total_cost * 100) if total_cost != 0 else 0
        
        current_prices.append(current_price)
        market_values.append(market_value)
        pnl_values.append(unrealized_pnl)
        pnl_percents.append(pnl_percent)

    holdings['Current Price'] = current_prices
    holdings['Market Value'] = market_values
    holdings['Cost Basis'] = holdings['cost_amount']
    holdings['Unrealized P/L'] = pnl_values
    holdings['% P/L'] = pnl_percents
    
    total_portfolio_val_thb = holdings['Market Value'].sum() * live_fx
    total_cost_thb = holdings['Cost Basis'].sum() * live_fx
    total_pnl_thb = total_portfolio_val_thb - total_cost_thb
    
    return holdings, total_portfolio_val_thb, total_cost_thb, total_pnl_thb

with st.sidebar:
    st.header("New Transaction")
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


raw_df = load_data()

tab1, tab2 = st.tabs(["Dashboard", "Raw Data"])

with tab1:
    if raw_df.empty:
        st.info("add your first transaction.")
    else:
        holdings_df, total_value, total_cost, total_pnl = calculate_portfolio(raw_df)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Portfolio Value", f"฿{total_value:,.0f}")
        col2.metric("Total Cost", f"฿{total_cost:,.0f}")
        col3.metric("Unrealized P/L", f"฿{total_pnl:,.0f}", 
                    delta=f"{(total_pnl/total_cost*100):.2f}%" if total_cost!=0 else "0%")
        col4.metric("FX Rate", f"฿{live_fx:.2f}")
        
        st.divider()
        
        col_chart, col_table = st.columns([1, 1.5]) 
        
        with col_chart:
            st.subheader("Asset Allocation")
            if not holdings_df.empty:
                fig, ax = plt.subplots()
                ax.pie(holdings_df['Market Value'], labels=holdings_df['ticker'], autopct='%1.1f%%', startangle=90)
                ax.axis('equal')
                fig.patch.set_alpha(0) 
                st.pyplot(fig)
            else:
                st.write("No active holdings.")

        with col_table:
            st.subheader("Current Holdings")
            
            if holdings_df.empty:
                st.write("No assets found.")
            else:
                for index, row in holdings_df.iterrows():
                    ticker = row['ticker']
                    qty = row['quantity']
                    current_price = row['Current Price']
                    market_val = row['Market Value']
                    cost_basis = row['Cost Basis']
                    pnl = row['Unrealized P/L']
                    pnl_pct = row['% P/L']
                    
                    if pnl >= 0:
                        icon = ""
                        color_class = "green" 
                    else:
                        icon = ""
                        color_class = "red"

                    label = f"{icon} **{ticker}** | ${market_val:,.2f} ({pnl_pct:+.2f}%)"
                    
                    with st.expander(label):
                        c1, c2, c3 = st.columns(3)
                        
                        avg_cost = cost_basis / qty if qty != 0 else 0
                        
                        c1.metric("Quantity", f"{qty:,.4f}")
                        c2.metric("Avg Cost", f"${avg_cost:,.2f}")
                        c3.metric("Current Price", f"${current_price:,.2f}")
                        
                        st.divider()
                        
                        c4, c5 = st.columns([2, 1])
                        c4.metric("Total P/L ($)", f"${pnl:,.2f}", delta=f"{pnl_pct:.2f}%")
                        c5.caption(f"Total Cost: ${cost_basis:,.2f}")

with tab2:
    st.subheader("Transaction History")
    st.dataframe(raw_df, use_container_width=True)