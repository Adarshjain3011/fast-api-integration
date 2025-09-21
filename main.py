from fastapi import FastAPI, Query
import requests
import gzip
import brotli
import json
from datetime import datetime, timedelta
import threading
import time

# Create FastAPI app
app = FastAPI()

# NSE URLs
CONTRACT_INFO_URL = "https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}"
OPTION_CHAIN_URL = "https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}&expiry={expiry}"

# Symbols to track
SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]

# Cache for expiry dates
expiries_cache = {}
last_refresh_time = None
refresh_interval = timedelta(hours=12)  # auto-refresh every 12 hours

# Create NSE session with headers
def get_nse_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/option-chain"
    })
    try:
        session.get("https://www.nseindia.com/option-chain", timeout=10)
    except Exception:
        pass
    return session

# Fetch all expiries for all indices
def refresh_expiries():
    global expiries_cache, last_refresh_time
    session = get_nse_session()
    temp_cache = {}
    for symbol in SYMBOLS:
        url = CONTRACT_INFO_URL.format(symbol=symbol)
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                expiries = data.get("expiryDates", [])
                temp_cache[symbol] = expiries
        except Exception:
            temp_cache[symbol] = []
    expiries_cache = temp_cache
    last_refresh_time = datetime.now()
    print(f"[{datetime.now()}] Expiry cache refreshed.")

# Pick nearest expiry
def get_nearest_expiry(symbol):
    today = datetime.today().date()
    expiries = expiries_cache.get(symbol, [])
    if not expiries:
        return None
    parsed = [datetime.strptime(e, "%d-%b-%Y").date() for e in expiries]
    nearest = min(parsed, key=lambda d: (d - today).days if d >= today else 99999)
    return nearest.strftime("%d-%b-%Y")

# Background thread to refresh expiries periodically
def auto_refresh_cache():
    while True:
        time.sleep(3600)  # check every hour
        if not last_refresh_time or datetime.now() - last_refresh_time > refresh_interval:
            refresh_expiries()

# Startup event: load expiry cache
@app.on_event("startup")
def startup_event():
    refresh_expiries()
    # Start background thread
    thread = threading.Thread(target=auto_refresh_cache, daemon=True)
    thread.start()

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}

# Refresh and view expiries
@app.get("/expiries")
def get_all_expiries():
    return expiries_cache

# Option chain endpoint (auto-pick nearest expiry if not provided)
@app.get("/option-chain/{symbol}")
def fetch_option_chain(symbol: str, expiry: str = Query(None, description="Expiry like 25-Sep-2025")):

    print("option chain endpoint called : ")
    session = get_nse_session()
    symbol = symbol.upper()

    # If no expiry provided, get nearest one
    if expiry is None:
        expiry = get_nearest_expiry(symbol)
        if not expiry:
            refresh_expiries()
            expiry = get_nearest_expiry(symbol)
        if not expiry:
            return {"error": f"No expiry found for {symbol}"}

    url = OPTION_CHAIN_URL.format(symbol=symbol, expiry=expiry)

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to fetch option chain: {e}"}

    # Try JSON first
    try:
        
        return resp.json()
    except Exception:
        pass

    # Handle gzip
    if resp.headers.get("Content-Encoding") == "gzip":
        return json.loads(gzip.decompress(resp.content).decode("utf-8"))

    # Handle brotli
    if resp.headers.get("Content-Encoding") == "br":
        return json.loads(brotli.decompress(resp.content).decode("utf-8"))

    return {"error": "Unknown response format", "headers": dict(resp.headers)}




