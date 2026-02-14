# MEXC Fair Price Bot

A powerful Telegram bot that monitors the spread between **Market Price (Last Price)** and **Fair Price** on the MEXC Futures market.

When a significant deviation is detected, the bot automatically sends a formatted alert with a generated price chart to your Telegram channel.

---

## 📸 Example Alert

```
⚠️ FAIR PRICE ALERT | 🟢 LONG

───◇───────────────
🔖 Token: BTC
📊 Last Price: $67200.00
⚖️ Fair Price:  $67200.20
📈 Spread:      +0.10%

📦 Volume 24h: $299.60M
⏰ Time:       15:56:09 UTC+3
───◇───────────────
😎 @LBScalp
📉 @aslgw
```

The bot also attaches a chart with highlighted **Last Price** and **Fair Price** levels.

---

## ✨ Features

- 📊 **Monitors all USDT perpetual contracts** on MEXC Futures  
- ⚡ **Instant spread detection**  
- 📈 **Automatic price chart generation** (last 30 candles)  
- 🎨 Clean and well-formatted Telegram messages  
- 🔗 Inline buttons with links to channel and MEXC  
- 🎯 Configurable spread threshold  
- 🚫 Anti-spam protection (**Cooldown system**)  
- 📱 Symbol filtering support  

---

## 🛠 Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/ylevelu/fair_price_parser.git
cd fair_price_parser
```

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Configure Environment Variables

Create a `.env` file in the root directory:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=@your_channel_username
```

### 4️⃣ Run the Bot

```bash
python main.py
```

---

## ⚙️ Configuration

You can modify parameters at the top of `fair_price_bot.py`:

```python
# ========== SETTINGS ==========
SPREAD_THRESHOLD = 0.1     # Trigger threshold in % (0.1 = 0.1%)
COOLDOWN = 60              # Seconds between alerts per symbol
MIN_VOLUME_USD = 0         # Minimum 24h volume (0 = disabled)
INTERVAL = 10              # API polling interval (seconds)
SHOW_MOVEMENTS = True      # Show console logs
SYMBOL_FILTER = ""         # Filter by symbol (e.g. "STOCK")
```

---

## 📦 Requirements

```
requests
python-dotenv
colorama
matplotlib
numpy
```

Or install everything with one command:

```bash
pip install requests python-dotenv colorama matplotlib numpy
```

---

## 🚀 Quick Start

1. Get a bot token from **@BotFather**
2. Create a Telegram channel
3. Add your bot as an administrator
4. Configure the `.env` file
5. Run the bot:

```bash
python main.py
```

---

## 📁 Project Structure

```
mexc-fair-price-bot/
├── main.py
├── .env                # DO NOT commit
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 🎯 How It Works

1. The bot polls the MEXC Futures API every **N seconds**
2. For each contract, it calculates the spread:

```
(lastPrice - fairPrice) / fairPrice * 100
```

3. If:
   - Spread exceeds the defined threshold
   - 24h volume meets requirements
   - Cooldown has expired

   Then the bot:
   - Fetches historical candle data
   - Generates a price chart
   - Sends an alert with the chart to Telegram

4. If chart generation fails, a text-only alert is sent instead.

---

## 🖼 Chart Includes

- 📈 Price line (last 30 candles)
- 🟡 Orange line — **Last Price**
- 🟢 Green line — **Fair Price**
- 📊 Volume histogram

---

## ⚠️ Troubleshooting

**Bot does not send charts**  
→ Check your internet connection and MEXC API availability.

**"Parameter error" for some tokens**  
→ The bot automatically tries alternative symbol formats (e.g., `SIRENUSDT`, `SIRENUSDC`).

---

## 👨‍💻 Author

**LBScalp**  
Telegram: https://t.me/LBScalp, https://t.me/aslgw

---

## 🤝 Support

For questions:  
Telegram: https://t.me/aslgw
