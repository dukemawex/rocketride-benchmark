# Run the RocketRide side locally (5 minutes)

Milo can't reach RocketRide's execution WebSocket (blocked from its environment, HTTP 403), so this one piece runs on your machine. Everything else is already done in the repo.

## Steps
```bash
# 1. Get the fork + updates
git clone https://github.com/dukemawex/rocketride-benchmark.git   # or: git pull
cd rocketride-benchmark

# 2. Python 3.11+ venv (the SDK needs 3.11+)
python3.11 -m venv .rrvenv && source .rrvenv/bin/activate
pip install rocketride

# 3. Your credentials
export ROCKETRIDE_URI=https://api.rocketride.ai
export ROCKETRIDE_AUTH=rr_your_token_here     # the token you already have

# 4. Run it
python extended/run_rocketride.py
```

## What to send back
The script prints a JSON block between `>>> PASTE FROM HERE >>>` and `<<< PASTE TO HERE <<<`.
Copy that whole block into the chat and Milo finishes the report.

## If it errors
- **connect failed / handshake timeout** on your machine too → likely a corporate/VPN firewall; try a home network.
- **auth / access denied** → regenerate the token in the dashboard, re-export, re-run.
- Anything else → paste the error text and Milo will debug it.
