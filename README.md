# Beer Analysis Telegram Bot

This Telegram bot analyzes photos of beer and provides information about the beer, including:
- Beer name and description
- User reviews and ratings
- Price-to-quality ratio

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GOOGLE_CLOUD_CREDENTIALS=path_to_your_google_cloud_credentials.json
```

4. Run the bot:
```bash
python bot.py
```

## Features
- Image recognition for beer labels
- Beer information retrieval
- User reviews and ratings
- Price-to-quality analysis

## Requirements
- Python 3.8+
- Telegram Bot Token
- Google Cloud Vision API credentials 