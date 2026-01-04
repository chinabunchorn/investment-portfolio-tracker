import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
import numpy as np
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
    
@st.cache_data(ttl=3600*24)
def get_stock_sector(ticker):
    if ticker in ["THB", "USD"]: return "Cash & Equiv."
    
    if ticker.endswith("-USD"): return "Crypto"
    
    try:
        stock = yf.Ticker(ticker)
        sector = stock.info.get('sector', 'Others')
       
        if sector == "Others":
            quote_type = stock.info.get('quoteType', '')
            if quote_type == 'ETF':
                return "ETF / Fund"
                
        return sector
    except:
        return "Others"
    
@st.cache_data(ttl=300)
def get_market_movers():

    tickers = [
        "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", 
        "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL", "META",
        "AMD", "PLTR", "COIN", "MSTR", "SMCI", "ARM", "AVGO", "NFLX", "ASML", "INTC",
        "BRK-B", "JPM", "LLY", "NVO", "TSM" ,"OKLO", "CRWD","DUOL","RBLX","SNOW"
    ]
    
    data = []
    
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d") 
            
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_price = hist['Close'].iloc[-1]
                change = curr_price - prev_close
                pct_change = (change / prev_close) * 100
                
                asset_type = "Crypto" if "-USD" in t else "Stock 🇺🇸"
                
                data.append({
                    "Ticker": t,
                    "Price": curr_price,
                    "Change $": change,
                    "% Change": pct_change,
                    "Type": asset_type
                })
        except:
            continue
            
    df = pd.DataFrame(data)
    
    if not df.empty:
        df = df.sort_values(by="% Change", ascending=False)
        
    return df

def classify_asset(ticker, platform):
    if platform in ["Binance"]: 
        return "Crypto"
    
    if ticker.endswith("-USD"): 
        return "Crypto"
        
    if ticker in ["THB", "USD"]: 
        return "Cash "
        
    return "Stock"

@st.cache_data(ttl=3600*12)
def get_performance_chart(transactions_df):
    if transactions_df.empty:
        return pd.DataFrame()

    start_date = pd.to_datetime(transactions_df['date']).min()
    end_date = datetime.today()
    all_dates = pd.date_range(start=start_date, end=end_date)
    
    tickers = transactions_df['ticker'].unique()
    daily_qty = pd.DataFrame(0.0, index=all_dates, columns=tickers)
    daily_flows = pd.Series(0.0, index=all_dates) 
    
    sorted_tx = transactions_df.sort_values('date')
    for idx, row in sorted_tx.iterrows():
        d = pd.to_datetime(row['date'])
        t = row['ticker']
        q = row['quantity']
        
        if row['type'] == 'BUY':
            cost = (q * row['price']) + row['fee']
            if d in daily_qty.index:
                daily_qty.loc[d:, t] += q
                daily_flows.loc[d] += cost
                
        elif row['type'] == 'SELL':
            proceeds = (q * row['price']) - row['fee'] 
            if d in daily_qty.index:
                daily_qty.loc[d:, t] -= q
                daily_flows.loc[d] -= proceeds 

    all_symbols = list(tickers) + ['^GSPC']
    try:
        data = yf.download(all_symbols, start=start_date, progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            price_data = data['Close']
        else:
            price_data = data['Close'] if 'Close' in data else data

        if price_data.index.tz is not None:
            price_data.index = price_data.index.tz_localize(None)
            
        price_data = price_data.reindex(all_dates).fillna(method='ffill')
        
    except Exception as e:
        return pd.DataFrame()

    portfolio_val = pd.Series(0.0, index=all_dates)
    for t in tickers:
        if t in price_data.columns:
            portfolio_val += daily_qty[t] * price_data[t]
            
    daily_returns = pd.Series(0.0, index=all_dates)
    
    for i in range(1, len(all_dates)):
        today = all_dates[i]
        yesterday = all_dates[i-1]
        
        val_today = portfolio_val.loc[today]
        val_yesterday = portfolio_val.loc[yesterday]
        flow_today = daily_flows.loc[today]
        
        if val_yesterday > 0:
            ret = (val_today - flow_today) / val_yesterday - 1
            daily_returns.loc[today] = ret

    my_port_cum = (1 + daily_returns).cumprod() * 100
    
    if '^GSPC' in price_data.columns:
        sp500_ret = price_data['^GSPC'].pct_change().fillna(0)
        sp500_cum = (1 + sp500_ret).cumprod() * 100
    else:
        sp500_cum = pd.Series(100, index=all_dates) 

    return pd.DataFrame({
        'My Portfolio': my_port_cum,
        'S&P 500': sp500_cum
    })


    
def calculate_portfolio(df):
    if df.empty:
        return pd.DataFrame(), 0.0, 0.0, 0.0, 0.0

    df = df.sort_values('date')
    
    portfolio = {} 
    total_realized_pnl = 0.0 

    for index, row in df.iterrows():
        ticker = row['ticker']
        tx_type = row['type']
        qty = row['quantity']
        price = row['price']
        fee = row['fee']
        
        if tx_type not in ['BUY', 'SELL']: 
            continue
            
        if ticker not in portfolio:
            portfolio[ticker] = {'qty': 0.0, 'total_cost': 0.0, 'platform': row['platform']}
        
        if tx_type == 'BUY':
            cost_with_fee = (qty * price) + fee
            portfolio[ticker]['qty'] += qty
            portfolio[ticker]['total_cost'] += cost_with_fee
            portfolio[ticker]['platform'] = row['platform']
            
        elif tx_type == 'SELL':
            current_qty = portfolio[ticker]['qty']
            if current_qty > 0:
                avg_cost_per_share = portfolio[ticker]['total_cost'] / current_qty
                cost_of_shares_sold = avg_cost_per_share * qty
                sell_proceeds = (qty * price) - fee
                
                trade_pnl = sell_proceeds - cost_of_shares_sold
                
                total_realized_pnl += (trade_pnl * row['fx_rate']) 
                
                portfolio[ticker]['qty'] -= qty
                portfolio[ticker]['total_cost'] -= cost_of_shares_sold 

    data = []
    for ticker, values in portfolio.items():
        if values['qty'] > 0.000001: 
            data.append({
                'ticker': ticker,
                'quantity': values['qty'],
                'cost_amount': values['total_cost'], 
                'platform': values['platform'],
                'type': 'Asset'
            })
            
    if not data:
         return pd.DataFrame(), 0.0, 0.0, 0.0, total_realized_pnl

    holdings = pd.DataFrame(data)
    
    return holdings, 0, 0, 0, total_realized_pnl

with st.sidebar:
    st.header("New Transaction")
    tx_type = st.radio("Type", ["BUY", "SELL"])
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
                st.caption(f"Auto-converted '{raw_ticker}' to '{ticker}' for price fetching")

            col1, col2 = st.columns(2)
            with col1: 
                qty = st.number_input("Quantity", min_value=0.0, format="%.4f")
            with col2: 
                price = st.number_input("Price per Share", min_value=0.0, format="%.2f")
            
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

tab1,tab2 ,tab3, tab4 = st.tabs(["Dashboard", "Market Movers", "Performance Chart", "Transactions"])
with tab1:
    if raw_df.empty:
        st.info("Please add your first transaction.")
    else:
        holdings_df, _, _, _, total_realized = calculate_portfolio(raw_df)
        
        if not holdings_df.empty:
            
            current_prices = []
            market_values = []
            pnl_values = []
            pnl_percents = []
            asset_sectors = []
            
            for index, row in holdings_df.iterrows():
                ticker = row['ticker']
                qty = row['quantity']
                cost_basis = row['cost_amount']
                
                this_sector = get_stock_sector(ticker)
                
                try:
                    stock = yf.Ticker(ticker)
                    history = stock.history(period="1d")
                    current_price = history['Close'].iloc[-1] if not history.empty else 0
                except:
                    current_price = 0
                
                if ticker.endswith("-USD") or not ticker.endswith(".BK"): 
                     price_in_thb = current_price * live_fx
                else:
                     price_in_thb = current_price

                market_value = qty * price_in_thb
               
                
                cost_basis_thb = cost_basis * live_fx 
                
                unrealized_pnl = market_value - cost_basis_thb
                pnl_percent = (unrealized_pnl / cost_basis_thb * 100) if cost_basis_thb != 0 else 0

                current_prices.append(current_price)
                market_values.append(market_value)
                pnl_values.append(unrealized_pnl)
                pnl_percents.append(pnl_percent)
                asset_sectors.append(this_sector)

            holdings_df['Current Price'] = current_prices
            holdings_df['Market Value'] = market_values
            holdings_df['Unrealized P/L'] = pnl_values
            holdings_df['% P/L'] = pnl_percents
            holdings_df['Sector'] = asset_sectors
            
            total_value = holdings_df['Market Value'].sum()
            total_cost_thb = (holdings_df['cost_amount'] * live_fx).sum() 
            total_unrealized_pnl = total_value - total_cost_thb
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Portfolio Value", f"฿{total_value:,.0f}")
            m2.metric("Total Cost", f"฿{total_cost_thb:,.0f}")
            m3.metric("Unrealized P/L", f"฿{total_unrealized_pnl:,.0f}", 
                      delta=f"{(total_unrealized_pnl/total_cost_thb*100):.2f}%" if total_cost_thb!=0 else "0%")
            m4.metric("Realized P/L", f"฿{total_realized:,.0f}",
                      delta_color="normal" if total_realized >= 0 else "inverse")
            m5.metric("FX Rate", f"฿{live_fx:.2f}")
            
            st.divider()

            st.subheader("Asset Allocation")
            c1, c2 = st.columns(2)
            with c1:
                fig, ax = plt.subplots(figsize=(6, 6))
                ax.pie(holdings_df['Market Value'], labels=holdings_df['ticker'], autopct='%1.1f%%', textprops={'color':"white"})
                fig.patch.set_alpha(0)
                st.pyplot(fig, use_container_width=True)
            
            with c2:
                if 'Sector' in holdings_df.columns:
                    sector_df = holdings_df.groupby('Sector')['Market Value'].sum()
                    fig2, ax2 = plt.subplots(figsize=(6, 6))
                    ax2.pie(sector_df, labels=sector_df.index, autopct='%1.1f%%', textprops={'color':"white"})
                    fig2.patch.set_alpha(0)
                    st.pyplot(fig2, use_container_width=True)

            st.divider()

            st.subheader("Current Holdings")
            for index, row in holdings_df.iterrows():
                with st.expander(f"{row['ticker']} | ฿{row['Market Value']:,.0f}"):
                     c1, c2, c3 = st.columns(3)
                     c1.metric("Qty", f"{row['quantity']:,.4f}")
                     c2.metric("Avg Cost ($)", f"${row['cost_amount']/row['quantity']:,.2f}")
                     c3.metric("Price ($)", f"${row['Current Price']:,.2f}")
                     st.metric("P/L (THB)", f"฿{row['Unrealized P/L']:,.0f}", delta=f"{row['% P/L']:.2f}%")
        else:
            st.info("No active stock holdings found.")

with tab2:
    st.subheader("Market Movers (Top Tech & Crypto)")
    st.caption("last updated from Yahoo Finance watchlist")
    
    movers_df = get_market_movers()
    
    if not movers_df.empty:
        col_gain, col_lose = st.columns(2)
        
        with col_gain:
            st.success("Top 5 Gainers")
            top_gainers = movers_df.head(5)
            for i, row in top_gainers.iterrows():
                st.metric(
                    label=f"{row['Ticker']} ({row['Type']})",
                    value=f"${row['Price']:,.2f}",
                    delta=f"+{row['% Change']:.2f}%"
                )
        
        with col_lose:
            st.error("Top 5 Losers")
            top_losers = movers_df.tail(5).sort_values(by="% Change", ascending=True) 
            for i, row in top_losers.iterrows():
                st.metric(
                    label=f"{row['Ticker']} ({row['Type']})",
                    value=f"${row['Price']:,.2f}",
                    delta=f"{row['% Change']:.2f}%" 
                )
        
        st.divider()
        st.subheader("Full Watchlist Ranking")
        
        st.dataframe(
            movers_df,
            use_container_width=True,
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "Change $": st.column_config.NumberColumn(format="$%.2f"),
                "% Change": st.column_config.NumberColumn(format="%.2f%%"),
            },
            hide_index=True
        )
    else:
        st.warning("Fetching market data failed. Please try again later.")                   

with tab3:
    st.subheader("Portfolio Performance vs S&P 500")
    st.caption("Normalized to 100 (Time-Weighted Return)")

    if not raw_df.empty:
        with st.spinner("Crunching numbers... (downloading history)"):
            perf_df = get_performance_chart(raw_df)
        
        if not perf_df.empty:
            st.line_chart(perf_df, color=["#00FF00", "#FF4B4B"]) 
            
            total_return = perf_df['My Portfolio'].iloc[-1] - 100
            market_return = perf_df['S&P 500'].iloc[-1] - 100
            
            c1, c2 = st.columns(2)
            c1.metric("My Return (Time-Weighted)", f"{total_return:+.2f}%")
            c2.metric("S&P 500 Return", f"{market_return:+.2f}%", 
                    delta=f"{total_return - market_return:+.2f}% vs Market")
        else:
            st.warning("Not enough data to calculate performance.")
    else:
        st.info("No transactions found.")

with st.expander("Debug Data"):
    st.write("Portfolio Values:", perf_df.head())

with st.sidebar:
    st.divider()
    st.caption("Danger Zone")
    if st.button("Reset All Data (Clear DB)"):
        try:
            import os
            if os.path.exists(DB_NAME):
                os.remove(DB_NAME)
                st.success("Database deleted! Please refresh page.")
            else:
                st.warning("Database not found.")
        except Exception as e:
            st.error(f"Error: {e}")

with tab4:
    st.subheader("Transaction History")
    
    st.dataframe(raw_df, use_container_width=True)
    
    st.divider()
    
    st.subheader("Manage Data (Delete)")
    st.caption("Enter the Transaction ID to delete the record.")
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        tx_id_to_delete = st.number_input("Transaction ID to Delete", min_value=0, step=1, value=0)
    
    with c2:
        st.write("") 
        st.write("")
        if st.button("Delete Transaction", type="primary"):
            if tx_id_to_delete > 0:
                try:
                    run_query("DELETE FROM transactions WHERE id = ?", (tx_id_to_delete,))
                    st.success(f"Deleted Transaction ID: {tx_id_to_delete} Successfully!")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting: {e}")
            else:
                st.warning("Please enter a valid ID greater than 0")
