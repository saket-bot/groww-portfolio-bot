"""
main.py

Daily Portfolio Update agent
 - Get Groww access token using apiKey + apiSecret (TOTP)
 - Fetch holdings from Groww
 - For each holding:
     • SYMBOL | Qty: X | Avg: ₹Y.YY
       ~25-word summary from Perplexity
 - Send via WhatsApp (Twilio) OR print if Twilio not configured
 - Runs automatically Mon–Fri at 7:00 PM IST
"""

import os
import json
import logging
import time
import pyotp
from datetime import datetime
from dotenv import load_dotenv
from growwapi import GrowwAPI
import requests
from twilio.rest import Client
import schedule
import pytz

# ---------- Load config ----------
load_dotenv()

GROWW_API_KEY = os.getenv("GROWW_API_KEY")
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
WHATSAPP_TO = os.getenv("WHATSAPP_TO")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------- Groww helpers ----------
def get_groww_access_token(api_key: str, api_secret: str) -> str:
    totp = pyotp.TOTP(api_secret).now()
    logger.info("Generated TOTP.")
    access_token = GrowwAPI.get_access_token(api_key, totp)
    if not access_token:
        raise RuntimeError("Failed to retrieve access_token from Groww SDK.")
    return access_token


def fetch_holdings(access_token: str) -> dict:
    url = "https://api.groww.in/v1/holdings/user"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-API-VERSION": "1.0",
        "Accept": "application/json",
    }
    r = requests.get(url, headers=headers, timeout=12)
    r.raise_for_status()
    return r.json()


# ---------- Perplexity helpers ----------
def ask_perplexity_for_insight(ticker: str) -> str:
    if not PERPLEXITY_API_KEY:
        return ""

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    prompt = (
        f"Write a concise, investor-friendly ~30-word summary about recent news, developments or industry trends related to {ticker}. "
        "Keep it factual, neutral, and end with a period. Include citations if available."
    )

    payload = {
        "model": "sonar-pro",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 160,
        "temperature": 0.2,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=18)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Perplexity API call failed for %s: %s", ticker, e)
        return ""

    data = resp.json()
    text = ""
    choices = data.get("choices", [])
    if choices and isinstance(choices, list):
        choice = choices[0]
        if choice.get("message", {}).get("content"):
            text = choice["message"]["content"]
        elif choice.get("text"):
            text = choice["text"]

    text = " ".join(text.split()).strip()
    if not text.endswith("."):
        text += "."
    return text


# ---------- Message composition ----------
def compose_portfolio_message(holdings_json: dict) -> str:
    lines = []
    lines.append("📊 Daily Portfolio Update\n")

    holdings_list = None
    if isinstance(holdings_json, dict):
        holdings_list = holdings_json.get("payload", {}).get("holdings") \
                        or holdings_json.get("data", {}).get("holdings") \
                        or holdings_json.get("holdings")
    if not isinstance(holdings_list, list):
        if isinstance(holdings_json.get("payload"), list):
            holdings_list = holdings_json.get("payload")
    if not isinstance(holdings_list, list):
        logger.warning("Unexpected holdings JSON shape; cannot find holdings list.")
        return "No holdings found."

    for h in holdings_list:
        symbol = h.get("trading_symbol") or h.get("symbol") or h.get("ticker") or "Unknown"
        qty = h.get("quantity") or h.get("qty") or 0
        avg_price = h.get("average_price") or h.get("avg_price") or 0.0
        try:
            avg_price = float(avg_price)
        except Exception:
            avg_price = 0.0

        lines.append(f"• {symbol.upper()} | Qty: {qty} | Avg: ₹{avg_price:.2f}")

        insight = ask_perplexity_for_insight(symbol)
        if insight:
            lines.append(f"  {insight}")
        else:
            lines.append("  (No update available)")

        lines.append("")

    return "\n".join(lines).strip()


# ---------- Twilio / output ----------
def send_whatsapp(body: str):
    if TWILIO_SID and TWILIO_AUTH and TWILIO_FROM and WHATSAPP_TO:
        try:
            client = Client(TWILIO_SID, TWILIO_AUTH)
            msg = client.messages.create(from_=TWILIO_FROM, to=WHATSAPP_TO, body=body)
            logger.info("WhatsApp message sent. SID: %s", msg.sid)
            return msg.sid
        except Exception as e:
            logger.error("Twilio send failed: %s", e)
            print(body)
            return None
    else:
        print(body)
        return None


# ---------- Main job ----------
def run():
    logger.info("Starting scheduled run.")
    try:
        token = get_groww_access_token(GROWW_API_KEY, GROWW_API_SECRET)
        holdings_json = fetch_holdings(token)
        message = compose_portfolio_message(holdings_json)
        logger.info("Composed message: %s", message[:500])
        send_whatsapp(message)
    except Exception as e:
        logger.exception("Run failed: %s", e)


# ---------- Scheduler ----------
if __name__ == "__main__":
    tz = pytz.timezone("Asia/Kolkata")

    def job():
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        logger.info("Triggering job at %s", now)
        run()

    # Schedule Mon–Fri at 19:00 IST
    schedule.every().monday.at("19:00").do(job)
    schedule.every().tuesday.at("19:00").do(job)
    schedule.every().wednesday.at("19:00").do(job)
    schedule.every().thursday.at("19:00").do(job)
    schedule.every().friday.at("19:00").do(job)

    logger.info("Scheduler started. Waiting for jobs...")
    while True:
        schedule.run_pending()
        time.sleep(30)
