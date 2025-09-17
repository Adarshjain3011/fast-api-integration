from fastapi import FastAPI
import requests
import gzip
import brotli
import json

# Create FastAPI app
app = FastAPI()

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}

# Path parameter
@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}

@app.get("/option-chain/{symbol}/{expiry}")
def fetch_option_chain(symbol: str = "NIFTY", expiry: str = None):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/option-chain"
    })

    # Initial request to set cookies
    try:
        session.get("https://www.nseindia.com/option-chain", timeout=10)
    except Exception:
        pass

    # expiry = "16-Sep-2025"

    # url = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}"
    # if expiry:
    #     url += f"&expiry={expiry}"

    print("symbol value is :",symbol)

    url=f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol.upper()}&expiry={expiry}"

    resp = session.get(url, timeout=15)

    if resp.status_code != 200:
        raise Exception(
            f"HTTP {resp.status_code} while fetching {symbol}. "
            f"Response starts with: {resp.text[:100]}"
        )

    # ✅ Try JSON first
    try:
        return resp.json()
    except Exception:
        pass

    # ✅ Handle gzip
    if resp.headers.get("Content-Encoding") == "gzip":
        try:
            return json.loads(gzip.decompress(resp.content).decode("utf-8"))
        except Exception as e:
            raise Exception(f"Failed to decompress gzip response for {symbol}: {e}")

    # ✅ Handle brotli
    if resp.headers.get("Content-Encoding") == "br":
        try:
            return json.loads(brotli.decompress(resp.content).decode("utf-8"))
        except Exception as e:
            raise Exception(f"Failed to decompress brotli response for {symbol}: {e}")

    # ✅ If HTML, raise clean error
    if "html" in resp.headers.get("content-type", "").lower():
        raise Exception(
            f"NSE returned HTML instead of JSON for {symbol}. "
            f"Probably blocked or throttled. Response: {resp.text[:120]}"
        )

    raise Exception(f"Unknown response format for {symbol}. Headers: {resp.headers}")
