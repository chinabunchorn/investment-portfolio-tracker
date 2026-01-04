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
    
def calculate_portfolio(df):
    if df.empty:
        return pd.DataFrame(), 0.0, 0.0, 0.0

    df = df.sort_values('date')
    
    portfolio = {} 

    for index, row in df.iterrows():
        ticker = row['ticker']
        tx_type = row['type']
        
        if tx_type not in ['BUY', 'SELL']: continue
            
        if ticker not in portfolio:
            portfolio[ticker] = {
                'qty': 0.0, 
                'total_cost': 0.0, 
                'platform': row['platform']
            }
        
        if tx_type == 'BUY':
            buy_cost = row['quantity'] * row['price']
            portfolio[ticker]['qty'] += row['quantity']
            portfolio[ticker]['total_cost'] += buy_cost
            portfolio[ticker]['platform'] = row['platform'] 
            
        elif tx_type == 'SELL':
            current_qty = portfolio[ticker]['qty']
            if current_qty > 0:
                avg_cost_per_share = portfolio[ticker]['total_cost'] / current_qty
                
                cost_removed = avg_cost_per_share * row['quantity']
                
                portfolio[ticker]['qty'] -= row['quantity']
                portfolio[ticker]['total_cost'] -= cost_removed
            else:
                pass

    data = []
    for ticker, values in portfolio.items():
        if values['qty'] > 0.00001:
            data.append({
                'ticker': ticker,
                'quantity': values['qty'],
                'cost_amount': values['total_cost'], 
                'platform': values['platform']
            })
            
    if not data:
         return pd.DataFrame(), 0.0, 0.0, 0.0

    holdings = pd.DataFrame(data)
    
    live_fx = get_current_fx_rate()
    
    current_prices = []
    market_values = []
    pnl_values = []
    pnl_percents = []
    asset_categories = [] 
    asset_sectors = []
    
    for index, row in holdings.iterrows():
        ticker = row['ticker']
        qty = row['quantity']
        total_cost = row['cost_amount']
        
        this_category = classify_asset(ticker, row['platform'])
        this_sector = get_stock_sector(ticker)
        
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
        asset_categories.append(this_category)
        asset_sectors.append(this_sector)

    holdings['Current Price'] = current_prices
    holdings['Market Value'] = market_values
    holdings['Cost Basis'] = holdings['cost_amount']
    holdings['Unrealized P/L'] = pnl_values
    holdings['% P/L'] = pnl_percents
    holdings['Category'] = asset_categories 
    holdings['Sector'] = asset_sectors
    
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

tab1,tab2 ,tab3 = st.tabs(["Dashboard", "Market Movers", "Raw Data"])

with tab1:
    if raw_df.empty:
        st.info("add your first transaction.")
    else:
        holdings_df, total_value, total_cost, total_pnl = calculate_portfolio(raw_df)
        
  
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Portfolio Value", f"฿{total_value:,.0f}")
        m2.metric("Total Cost", f"฿{total_cost:,.0f}")
        m3.metric("Unrealized P/L", f"฿{total_pnl:,.0f}", 
                    delta=f"{(total_pnl/total_cost*100):.2f}%" if total_cost!=0 else "0%")
        m4.metric("FX Rate", f"฿{live_fx:.2f}")
        
        st.divider()

        st.subheader(" Asset Allocation")
        
        c_chart1, c_chart2, c_chart3 = st.columns(3)
        
        with c_chart1:
            st.caption("By Ticker")
            if not holdings_df.empty:
                fig, ax = plt.subplots(figsize=(6, 6))
                ax.pie(holdings_df['Market Value'], labels=holdings_df['ticker'], 
                       autopct='%1.1f%%', startangle=90, 
                       textprops={'fontsize': 12, 'color': 'white'})
                ax.axis('equal')
                fig.patch.set_alpha(0)
                st.pyplot(fig, use_container_width=True)

        with c_chart2:
            st.caption("By Risk Class")
            if 'Category' in holdings_df.columns:
                class_df = holdings_df.groupby('Category')['Market Value'].sum()
                fig2, ax2 = plt.subplots(figsize=(6, 6))
                ax2.pie(class_df, labels=class_df.index, 
                        autopct='%1.1f%%', startangle=90,
                        textprops={'fontsize': 12, 'color': 'white'})
                ax2.axis('equal')
                fig2.patch.set_alpha(0)
                st.pyplot(fig2, use_container_width=True)

        with c_chart3:
            st.caption("By Sector (Industry)")
            if 'Sector' in holdings_df.columns:
                sector_df = holdings_df.groupby('Sector')['Market Value'].sum()
                
                fig3, ax3 = plt.subplots(figsize=(6, 6))
                
                wedges, texts, autotexts = ax3.pie(
                    sector_df, 
                    labels=None, 
                    autopct='%1.1f%%', 
                    startangle=90,
                    pctdistance=0.85, 
                    textprops={'fontsize': 10, 'color': 'white'}
                )
                
               
                centre_circle = plt.Circle((0,0), 0.70, fc='#0E1117') 
                fig3.gca().add_artist(centre_circle)
                
                ax3.axis('equal')
                
                ax3.legend(wedges, sector_df.index,
                          title="Sectors",
                          loc="upper center",
                          bbox_to_anchor=(0.5, 0), 
                          ncol=2, 
                          frameon=False, 
                          labelcolor='white') 
                
                fig3.patch.set_alpha(0)
                st.pyplot(fig3, use_container_width=True)

        st.divider()

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


                label = f"**{ticker}** | ฿{market_val:,.2f} ({pnl_pct:+.2f}%)"

                with st.expander(label):
                    c1, c2, c3 = st.columns(3)
                    avg_cost = cost_basis / qty if qty != 0 else 0
                    
                    c1.metric("Quantity", f"{qty:,.4f}")
                    c2.metric("Avg Cost", f"${avg_cost:,.2f}")
                    c3.metric("Current Price", f"${current_price:,.2f}")
                    
                    st.divider()
                    
                    c4, c5 = st.columns([2, 1])
                    c4.metric("Total P/L", f"฿{pnl:,.2f}", delta=f"{pnl_pct:.2f}%")
                    c5.caption(f"Total Cost: ฿{cost_basis:,.2f}")

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
    st.subheader("Transaction History")
    st.dataframe(raw_df, use_container_width=True)
