# 🎲 Discord Gambling Bot 🎮

A sleek Discord bot gambling module with coinflip and economy features!

## ✨ Features

- **🪙 Interactive Coinflip** - Bet virtual currency with slick button controls
- **💰 MongoDB Integration** - Persistent storage for player balances
- **📊 Stats Tracking** - See your gambling performance over time
- **🔄 Play Again** - Quick rematch option

## 🚀 Quick Setup

1. **Add to your bot:**
   ```python
   # In your bot's main file
   await bot.load_extension("gambling")
   ```

2. **Set up MongoDB:**
   ```
   # In gambling.py, update this line:
   MONGO_URI = "your_mongodb_connection_string"
   ```

3. **Install dependencies:**
   ```
   pip install pymongo==3.8 motor discord.py
   ```

4. **Run your bot!**

## 💬 Commands

- `!cf` - Start a coinflip game with interactive buttons
  - Select heads/tails and enter your bet amount
  - Win double your bet or lose it all!

## 🛠️ Configuration

All config options are at the top of `gambling.py`:

```python
# MongoDB connection
MONGO_URI = "mongodb://username:password@host:port/database"

# Customize emojis
HEADS_EMOJI = "🪙"
TAILS_EMOJI = "💰" 

# Media
HEADS_GIF = "https://i.imgur.com/HavOS7J.gif"
TAILS_GIF = "https://i.imgur.com/XnAHCmz.gif"
```

## 📝 Integration Notes

- Uses hybrid commands for slash command support
- Requires a wallet.py module for economy functions
- All gambling stats are stored in MongoDB

---
