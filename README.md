# DERIV AI PRO — Version 2

## Features
- Dynamically loads all active symbols returned by Deriv.
- Retrieves historical ticks from Deriv's public WebSocket API.
- Displays last-digit counts and percentages.
- Tests Over, Under, Matches, Differs, Even and Odd against the next historical tick.
- Compares the six strategies by historical hit rate.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment
Deploy the repository on Streamlit Community Cloud with `app.py` as the main file.

## Data and limitations
Uses the public, unauthenticated endpoint:
`wss://api.derivws.com/trading/v1/options/ws/public`

No API token or App ID is required for public market data. The backtest is a simple one-step historical digit hit-rate test. It does not model contract payouts, fees, slippage, execution or profitability. It does not predict future ticks and does not place trades.
