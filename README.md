
# DERIV AI PRO — starter build

A read-only Streamlit dashboard that retrieves Deriv tick history and analyses last-digit frequencies and basic digit-contract sample rates.

## Run on your Windows laptop

1. Install Python 3.10 or newer.
2. Extract this ZIP.
3. Open Command Prompt in the extracted folder.
4. Run:

```bash
py -m venv .venv
.venv\\Scripts\\activate
py -m pip install -r requirements.txt
streamlit run app.py
```

5. In the browser, enter your Deriv App ID and fetch tick history.

## Run on Android / use on both devices

For access from both devices, deploy the project to a trusted Streamlit hosting service or your own server, then open the deployed HTTPS address on Android and laptop. This starter is not yet a native Android app.

## Deriv App ID

Create an application in your Deriv account/API settings and use its App ID. This first version uses public historical tick data and does not request an account token or trading permissions.

Official developer docs: https://developers.deriv.com/

## Current limitations

- Read-only historical tick retrieval; no order placement.
- The symbol list is a starter list. Some symbols may not be available on every account or region.
- The dashboard reports historical sample frequencies, not predictive probabilities.
- No AI model is included yet. We should first validate data handling and build a proper out-of-sample backtest.
- Never share your Deriv password, API token, or account credentials. Do not enable trading permissions for this read-only prototype.

## Next development milestones

1. Verify live market symbol availability.
2. Add live WebSocket tick streaming and configurable rolling windows.
3. Add payout-aware expected-value calculations and out-of-sample backtesting.
4. Add demo-only trade execution with strict loss limits, after separate confirmation.
