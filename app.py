import asyncio
import subprocess
import shutil
import re
import os
from typing import List, Dict, Literal
from update_vercel import update_vercel_api
import aiohttp
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_compress import Compress

# ======================================================
# 🔍 ENV DETECTION
# ======================================================
def is_colab():
    try:
        import google.colab  # type: ignore
        return True
    except ImportError:
        return False

# ======================================================
# 🌐 CLOUDLFARED (COLAB ONLY)
# ======================================================
def install_cloudflared():
    if not shutil.which("cloudflared"):
        print("⏳ Installing cloudflared...")
        subprocess.run(
            [
                "curl", "-fsSL",
                "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
                "-o", "cloudflared"
            ],
            check=True
        )
        subprocess.run(["chmod", "+x", "cloudflared"], check=True)
        print("✅ cloudflared installed")
    else:
        print("✅ cloudflared already present")


def start_cloudflare_tunnel(port: int):
    print(f"🚀 Starting Cloudflare tunnel on port {port}")

    proc = subprocess.Popen(
        ["./cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    public_url = None
    for line in iter(proc.stdout.readline, ""):
        print("[cloudflared]", line.strip())
        if "trycloudflare.com" in line and not public_url:
            match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if match:
                public_url = match.group(0)
                print("\n🌍 PUBLIC URL:", public_url, "\n")
                break

    return proc, public_url

# ======================================================
# 🧠 FLASK APP
# ======================================================
app = Flask(__name__)
CORS(app)
Compress(app)

BASE_URL = "https://groww.in/v1/api/stocks_fo_data/v1"

COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "x-app-id": "growwWeb",
    "x-device-type": "desktop",
    "x-platform": "web",
}

def build_latest_price_url(exchange: Literal["NSE", "BSE"]) -> str:
    return f"{BASE_URL}/tr_live_prices/exchange/{exchange}/segment/FNO/latest_prices_batch"


def build_chart_url(exchange: Literal["NSE", "BSE"], symbol: str) -> str:
    return f"{BASE_URL}/charting_service/delayed/chart/exchange/{exchange}/segment/FNO/{symbol}"


async def async_post(url: str, headers: Dict, payload):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def async_get(url: str, headers: Dict, params: Dict):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

# ======================================================
# ROUTES
# ======================================================
@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "env": "colab" if is_colab() else "local",
        "endpoints": {
            "latest_price": "/api/latest-price",
            "chart_data": "/api/chart-data"
        }
    })


@app.route("/api/latest-price", methods=["POST"])
def latest_price():
    data = request.get_json(force=True)

    symbols = data.get("symbols")
    exchange = data.get("exchange", "BSE")

    if not symbols:
        return jsonify({"error": "symbols required"}), 400

    url = build_latest_price_url(exchange)
    result = asyncio.run(async_post(url, COMMON_HEADERS, symbols))
    return jsonify(result)


@app.route("/api/chart-data", methods=["GET", "POST"])
def chart_data():
    data = request.get_json(silent=True) or request.args

    symbol = data.get("symbol")
    start_ms = data.get("start_ms")
    end_ms = data.get("end_ms")
    exchange = data.get("exchange", "NSE")
    interval = int(data.get("interval_minutes", 1))

    if not all([symbol, start_ms, end_ms]):
        return jsonify({"error": "symbol, start_ms, end_ms required"}), 400

    url = build_chart_url(exchange, symbol)
    params = {
        "startTimeInMillis": int(start_ms),
        "endTimeInMillis": int(end_ms),
        "intervalInMinutes": interval,
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        "x-app-id": "growwWeb",
        "x-device-type": "charts",
        "x-platform": "web",
    }

    result = asyncio.run(async_get(url, headers, params))
    return jsonify(result)

# ======================================================
# 🚀 MAIN
# ======================================================
if __name__ == "__main__":
    PORT = 5000

    if is_colab():
        install_cloudflared()
        tunnel_proc, public_url = start_cloudflare_tunnel(PORT)

        if public_url:
            print("🔗 Public URL:", public_url)

            # 🔥 SEND PUT REQUEST TO VERCEL
            update_vercel_api(
                public_url=public_url,
            )
        print("🔗 Access API via:", public_url)

    app.run(host="0.0.0.0", port=PORT, debug=True)
