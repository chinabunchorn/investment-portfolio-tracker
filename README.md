# Personal Wealth Dashboard & Portfolio Tracker


> **Live** https://personal-portfolio-tracker.streamlit.app
> *(The demo comes with pre-loaded sample data )*

---

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/34fef51b-9d3b-4a84-84c0-8df2bf70c17f" />
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/1607a44d-e3f5-4fef-a6e4-a3e3992c72c6" />

---
### Usage Guide

This tracker is designed for **Manual Entry** to give you full control.

1.  **Select Date:** Choose the actual transaction date.
2.  **Input Data:** Enter Ticker, Quantity, Price, and Fees exactly as shown on your Broker's trade confirmation (e.g., Dime, Binance, Streaming).
3.  **Track:** The app calculates your Average Cost, Realized/Unrealized P/L based on these inputs.

> *Tip: Inputting accurate fees helps in calculating the precise Net Profit.*

##  Key Features


### Portfolio Management
- Support for BUY and SELL.
- Track Stocks (US/Thai), ETFs, and Cryptocurrencies via `yfinance`.
- Automatically fetches live prices to calculate Net Worth.

### Performance Analysis
- Compare your portfolio  vs. **S&P 500**.
- Calculate **Max Drawdown** to see how your portfolio is compared to the market.
- Charts powered by `Matplotlib` and `Plotly`.
- fetch **P/E Ratios**, **Analyst Ratings**, and calculate **PEG Ratios** (using historical EPS growth) to spot overvalued assets.


### Data Handling
- Uses `SQLite` 
- sample data (NVDA, BTC, AAPL) on first launch for testing purposes.

---

## Tech Stack

- **Frontend/UI:** Streamlit
- **Data Manipulation:** Pandas, NumPy
- **Financial Data:** yfinance API
- **Visualization:** Plotly, Matplotlib
- **Database:** SQLite3

---

##  How to Run Locally
1. **Clone the repository**
2. pip install -r requirements.txt
3. streamlit run app.py Note: No need to set up the database manually
4. open in your browser at http://localhost:8501.
