# DERIV AI PRO — starter build

Read-only Streamlit dashboard for Deriv historical tick data and last-digit frequency analysis.

## Run locally
```bash
py -m venv .venv
.venv\\Scripts\\activate
py -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy
Upload `app.py`, `requirements.txt`, and `README.md` to GitHub, then deploy the repository using Streamlit Community Cloud.

## Deriv connection
This version uses Deriv's public market-data WebSocket endpoint:
`wss://api.derivws.com/trading/v1/options/ws/public`

No App ID or API token is required for public market data.

## Limitations
- Historical tick retrieval only; no order placement.
- Historical frequencies are descriptive statistics, not reliable predictions.
- Verify market symbols available to your account.
- Do not put passwords or API tokens in GitHub.
