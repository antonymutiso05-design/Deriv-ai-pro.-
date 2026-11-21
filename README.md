# Deriv Digit Analyser (Python and Streamlit)

Analyses the last digit of live Deriv ticks, generates BUY or WAIT signals, backtests them, and records paper trades in SQLite. It uses public market data only. There is no API token and no real trading.

## Files
- `app.py`: Streamlit dashboard with Live, Backtest and Paper trade history tabs
- `deriv_client.py`: Deriv WebSocket feed (background thread) and the paper-trading bot
- `analysis.py`: digit statistics, signal rule, backtest and variant scan
- `db.py`: SQLite trade history (`deriv_trades.db`, created on first run)
- `requirements.txt`, `.gitignore`

## Run on your HP laptop (Windows)
1. Install Python 3.10 or newer from python.org and tick "Add Python to PATH".
2. Open a terminal in this folder and run:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. Your browser opens at `http://localhost:8501`.

To view it on your Android phone, keep the laptop running on the same Wi-Fi and open the "Network URL" that Streamlit prints.

## Put it on GitHub
1. Create a new repository.
2. Upload all files in this folder, including `.gitignore`, to the repository root.
3. The `.gitignore` keeps your local trade database out of the repository.

## How to use it
1. Pick a market, a strategy (Over 2 and Under 8 are common) and a window.
2. Watch the Live tab. The signal says BUY when the recent win rate is far enough from the expected rate (the Z threshold).
3. Turn on the paper-trading bot in the sidebar. It places a fake trade on the tick after each BUY and logs the result.
4. Use the Backtest tab to replay the rule on 5,000 past ticks, and the variant scan to see how many rules look good by luck.

## Important
Deriv's Volatility indices are random number generators. Digits are independent, so past digits do not change the next one, and Deriv pays less than fair odds. Expect paper trades to win at the theoretical rate and lose the house margin over time. Test everything on paper first and do not add real-money execution unless you have clear evidence of an edge on fresh data.
