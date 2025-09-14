# 📊 AI-Powered Daily Portfolio Update Bot

Get daily updates about your Groww portfolio with AI-generated insights delivered straight to your terminal or WhatsApp.

At **7:00 PM (Mon–Fri)**, the bot:
- Fetches your holdings from **Groww** using your API Key & Secret
- Gets ~30-word news/industry insights for each stock from **Perplexity AI**
- Sends a formatted summary via **WhatsApp (Twilio)** or prints in terminal

---

## 🚀 Features
- 🔐 Secure use of Groww API (API Key + Secret with TOTP)
- 🤖 AI-powered summaries via Perplexity
- 📱 Optional WhatsApp delivery (Twilio)
- 🕖 Scheduler built-in (Mon–Fri at 7 PM IST)

---

## 🛠️ Setup Instructions

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/groww-portfolio-bot.git
cd groww-portfolio-bot
