import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
# import pytesseract # Удаляем или комментируем эту строку
from PIL import Image
import io
import re
import requests
import json
import base64
from rapidfuzz import fuzz, process
from flask import Flask, request

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен бота и ключ OCR из переменных окружения
# Убедитесь, что вы добавили TELEGRAM_BOT_TOKEN и OCR_SPACE_API_KEY
# в переменные окружения на Vercel
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY', 'YOUR_OCR_SPACE_API_KEY') # Замените \'YOUR_OCR_SPACE_API_KEY\' на более безопасное значение по умолчанию или уберите его
RATINGS_FILE = 'ratings.json'

# Simple context class for manual handler calls
class SimpleContext:
    def __init__(self, bot: Bot):
        self.bot = bot

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Привет! Я бот для анализа пива. Отправь мне фотографию пива, '
        'и я расскажу тебе о нем подробнее!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Отправь мне фотографию пива, и я предоставлю информацию о нем, '
        'включая название, отзывы, рейтинг и соотношение цена/качество.'
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos."""
    try:
        # Get the photo file
        photo = await update.message.photo[-1].get_file()
        
        # Download the photo
        photo_bytes = await photo.download_as_bytearray()
        
        # Используем OCR.Space вместо pytesseract
        text = ocr_space_recognize(photo_bytes)
        print(f"[DEBUG] Распознанный текст (OCR.Space): {repr(text)}")
        
        if not text.strip():
            await update.message.reply_text(
                "Извините, не удалось распознать текст на этикетках пива. "
                "Пожалуйста, убедитесь, что фото четкое и этикетки хорошо видна."
            )
            return
        
        # Get the detected text
        beer_name = text.strip()
        
        # Here you would typically make an API call to a beer database
        # For now, we'll use a mock response
        beer_info = get_beer_info(beer_name)
        # Обновляем рейтинг с учётом пользовательских оценок
        beer_info['rating'] = get_avg_rating(beer_info['name'], beer_info['rating'])
        
        # Format and send the response
        response_text = format_beer_info(beer_info)
        # Кнопка для оценки
        keyboard = [
            [InlineKeyboardButton("Оценить", callback_data=f"rate_{beer_info['name']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(response_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await update.message.reply_text(
            "Извините, произошла ошибка при обработке фотографии. "
            "Пожалуйста, попробуйте еще раз."
        )

async def rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith('rate_'):
        beer_name = query.data[5:]
        # Кнопки с оценками 1-10
        keyboard = [
            [InlineKeyboardButton(str(i), callback_data=f"setrate_{beer_name}_{i}") for i in range(1, 6)],
            [InlineKeyboardButton(str(i), callback_data=f"setrate_{beer_name}_{i}") for i in range(6, 11)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    elif query.data.startswith('setrate_'):
        _, beer_name, rating = query.data.split('_')
        save_rating(beer_name, int(rating))
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"Спасибо! Ваша оценка {rating}/10 учтена для {beer_name}.")

async def webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a button to open the Telegram Mini App (Web App)."""
    keyboard = [
        [InlineKeyboardButton("Открыть мини-приложение", web_app={"url": "https://frontend-telegram-webapp.vercel.app/"})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Запусти мини-приложение:", reply_markup=reply_markup)

async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = update.effective_message.web_app_data.data
        payload = json.loads(data)

        if payload.get('action') == 'rate':
            beer_name = payload.get('beer')
            rating = int(payload.get('rating'))
            save_rating(beer_name, rating)
            # We might want to send a message back to the web app here instead of chat
            # await update.effective_message.reply_text(f'Ваша оценка {rating}/10 для "{beer_name}" сохранена!')
            # Close web app or send a confirmation message to the web app
            # update.effective_message.web_app_data.web_app.close()
            pass # Process rating, possibly send silent confirmation or update web app UI
        
        elif payload.get('action') == 'process_photo' and payload.get('image_base64'):
            image_base64 = payload.get('image_base64')
            try:
                image_bytes = base64.b64decode(image_base64)
                
                # Process the image bytes (OCR and get beer info)
                text = ocr_space_recognize(image_bytes)
                print(f"[DEBUG] Распознанный текст (OCR.Space) from web app: {repr(text)}")

                beer_info = {}
                if text.strip():
                     beer_info = get_beer_info(text)
                     # Update rating with user ratings (if applicable and you want this in web app info)
                     beer_info['rating'] = get_avg_rating(beer_info.get('name', ''), beer_info.get('rating', 0))
                else:
                    beer_info = {"name": "-", "description": "Не удалось распознать текст.", "rating": "-", "reviews": [], "price_quality_ratio": "-"}

                # Format the info (can be simplified for JSON response to web app)
                # Instead of formatting as text, prepare data structure for web app
                # For now, let's send a message to the chat as a quick way to see the result
                response_text = format_beer_info(beer_info)
                await update.effective_message.reply_text(response_text)

                # In a real scenario, you would send this data back to the web app
                # update.effective_message.web_app_data.web_app.send_data(json.dumps(beer_info))

            except Exception as photo_e:
                logger.error(f"Error processing photo from web app: {photo_e}")
                await update.effective_message.reply_text("Извините, произошла ошибка при обработке фотографии из мини-приложения.")

    except Exception as e:
        logger.error(f"Error in webapp_data_handler: {e}")
        await update.effective_message.reply_text('Ошибка при обработке данных из мини-приложения.')

def normalize(text):
    return re.sub(r'[^a-zA-Zа-яА-Я0-9 ]', '', text.lower())

def clean_name(name):
    # Удаляем лишние слова и символы, которые не влияют на идентификацию бренда/названия
    name = name.lower()
    # Удаляем слова 'пиво', 'напиток пивной', 'темное', 'светлое', 'безалкогольное', 'полусухой', 'вишневый', 'оригинал', 'premium', 'draught', 'lager', 'hell', 'blonde', 'blanche', 'pale', 'extra', 'original', 'fresh', 'rouge', 'nastro', 'azzurro', 'sport', 'port', 'weissbier', 'ipa', 'эль', 'стаут', 'бланш', 'пилзнер', 'американский', 'европейский', 'немецкий', 'бельгийский', 'индийский', 'фруктовый', 'красное', 'светлый', 'темный', 'банка', 'стеклянная бутылка', 'бутылка', 'банка', 'фильтрованное', 'нефильтрованное', 'да', 'нет', 'импорт', 'вкусовое', 'безалкогольный', 'безалкогольное', 'мл', 'л'
    words_to_remove = r'(пиво|напиток пивной|темное|светлое|безалкогольное|полусухой|вишневый|оригинал|premium|draught|lager|hell|blonde|blanche|pale|extra|original|fresh|rouge|nastro|azzurro|sport|port|weissbier|ipa|эль|стаут|бланш|пилзнер|американский|европейский|немецкий|бельгийский|индийский|фруктовый|красное|светлый|темный|банка|стеклянная бутылка|бутылка|фильтрованное|нефильтрованное|да|нет|импорт|вкусовое|безалкогольный|безалкогольное|мл|л)'
    name = re.sub(words_to_remove, '', name)
    # Удаляем числа (объемы)
    name = re.sub(r'\d+[.,]?\d*', '', name)
    # Удаляем лишние запятые, пробелы
    name = re.sub(r'[\s,]+', ' ', name)
    return name.strip()

def get_beer_info(beer_text: str) -> dict:
    """
    Поиск наиболее похожего пива в базе по строкам распознанного текста (fuzzy search, с нормализацией и очисткой названий).
    """
    with open('beer_db.json', encoding='utf-8') as f:
        beers = json.load(f)
    beer_names = [beer['name'] for beer in beers]
    norm_beer_names = [clean_name(name) for name in beer_names]
    best_score = 0
    best_idx = None
    best_line = None
    for line in beer_text.splitlines():
        line = line.strip()
        if not line:
            continue
        norm_line = clean_name(line)
        match, score, idx = process.extractOne(norm_line, norm_beer_names, scorer=fuzz.token_sort_ratio)
        print(f"[DEBUG] Fuzzy match: '{line}' -> '{beer_names[idx]}' (score={score})")
        if score > best_score:
            best_score = score
            best_idx = idx
            best_line = line
    if best_score > 30 and best_idx is not None:
        beer = beers[best_idx]
        return {
            "name": beer['name'],
            "description": beer['description'],
            "rating": beer['rating'],
            "reviews": [
                "Отличное пиво с насыщенным вкусом",
                "Хорошее соотношение цена/качество",
                "Рекомендую попробовать"
            ],
            "price_quality_ratio": "Высокое"
        }
    else:
        return {
            "name": beer_text.strip().splitlines()[0] if beer_text.strip().splitlines() else beer_text.strip(),
            "description": "Пиво не найдено в базе. Попробуйте другое фото или название.",
            "rating": "-",
            "reviews": [],
            "price_quality_ratio": "-"
        }

def escape_markdown_v2(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters (char-by-char)."""
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

def format_beer_info(beer_info: dict) -> str:
    """Формирует подробное сообщение о пиве с MarkdownV2."""
    lines = [f"🍺 *{escape_markdown_v2(beer_info.get('name', '-'))}*"]
    if beer_info.get('brand'):
        lines.append(f"🏷 *Бренд:* {escape_markdown_v2(beer_info['brand'])}")
    if beer_info.get('country'):
        lines.append(f"🌍 *Страна:* {escape_markdown_v2(beer_info['country'])}")
    if beer_info.get('abv'):
        lines.append(f"💪 *Крепость:* {escape_markdown_v2(str(beer_info['abv']))}%")
    if beer_info.get('style'):
        lines.append(f"🍻 *Сорт:* {escape_markdown_v2(beer_info['style'])}")
    if beer_info.get('color'):
        lines.append(f"🎨 *Цвет:* {escape_markdown_v2(beer_info['color'])}")
    if beer_info.get('volume'):
        lines.append(f"🧃 *Объем:* {escape_markdown_v2(str(beer_info['volume']))} мл")
    if beer_info.get('package'):
        lines.append(f"📦 *Упаковка:* {escape_markdown_v2(beer_info['package'])}")
    if beer_info.get('filtration'):
        lines.append(f"🧊 *Фильтрация:* {escape_markdown_v2(beer_info['filtration'])}")
    if beer_info.get('imported'):
        lines.append(f"🌐 *Импорт:* {escape_markdown_v2(beer_info['imported'])}")
    if beer_info.get('flavored'):
        lines.append(f"🍯 *Вкусовое:* {escape_markdown_v2(beer_info['flavored'])}")
    lines.append(f"\n📝 *Описание:*\n{escape_markdown_v2(beer_info.get('description', '-'))}")
    lines.append(f"\n⭐ *Рейтинг:* {beer_info.get('rating', '-')} /10")
    return '\n'.join(lines)

def ocr_space_recognize(image_bytes: bytes) -> str:
    """Send image to OCR.Space API and return recognized text."""
    url = 'https://api.ocr.space/parse/image'
    payload = {
        'apikey': OCR_SPACE_API_KEY,
        'language': 'eng',
        'isOverlayRequired': False
    }
    files = {'file': ('image.jpg', image_bytes)}
    response = requests.post(url, data=payload, files=files)
    result = response.json()
    if result.get('IsErroredOnProcessing'):
        return ''
    parsed_results = result.get('ParsedResults')
    if parsed_results and len(parsed_results) > 0:
        return parsed_results[0].get('ParsedText', '')
    return ''

def save_rating(beer_name: str, rating: int):
    if os.path.exists(RATINGS_FILE):
        with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
            ratings = json.load(f)
    else:
        ratings = {}
    if beer_name not in ratings:
        ratings[beer_name] = []
    ratings[beer_name].append(rating)
    with open(RATINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(ratings, f, ensure_ascii=False, indent=2)

def get_avg_rating(beer_name: str, base_rating: float) -> float:
    if os.path.exists(RATINGS_FILE):
        with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
            ratings = json.load(f)
        if beer_name in ratings and ratings[beer_name]:
            all_ratings = ratings[beer_name]
            return round((sum(all_ratings) + base_rating) / (len(all_ratings) + 1), 2)
    return base_rating

# Инициализация Flask приложения
app = Flask(__name__)

# Маршрут для приема вебхуков от Telegram
# Vercel будет направлять POST запросы на этот маршрут, как указано в vercel.json
@app.route('/', methods=['POST'])
async def webhook():
    logger.info("Webhook received!")
    # Получаем JSON данные из запроса
    data = request.get_json(force=True)
    # Создаем объект Update из JSON данных
    bot = Bot(BOT_TOKEN)
    update = Update.de_json(data, bot) # Pass the bot instance to the Update object
    
    # Create a bot instance within the webhook function
    context = SimpleContext(bot=bot) # Use our custom context class

    try:
        if update.message:
            if update.message.text:
                text = update.message.text.lower()
                if text == '/start':
                    await start(update, context)
                elif text == '/help':
                    await help_command(update, context)
                elif text == '/webapp':
                    await webapp_command(update, context)
                else: # Добавляем обработку для всех остальных текстовых сообщений
                    await update.message.reply_text("Я могу обрабатывать только команды /start, /help, /webapp, или фотографии пива.")
            elif update.message.photo:
                await handle_photo(update, context)
            # Add other message types handlers here (e.g., update.message.document)
        elif update.callback_query:
            await rate_callback(update, context)
        elif update.effective_message and update.effective_message.web_app_data:
             await webapp_data_handler(update, context)
        # Add other update types handlers here (e.g., update.inline_query)
        
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        # Optional: send an error message back to the user
        # if update.effective_message:
        #     await update.effective_message.reply_text("Произошла ошибка при обработке вашего запроса.")

    # Возвращаем ответ 'ok' Telegram
    return 'ok'

# New route for photo uploads from the mini app
@app.route('/upload_photo', methods=['POST'])
async def upload_photo():
    logger.info("Photo upload request received!")
    try:
        # Get the photo file from the request
        if 'photo' not in request.files:
            logger.error("No photo file in request.")
            return json.dumps({"status": "error", "message": "No photo file provided."}), 400

        file = request.files['photo']
        if file.filename == '':
            logger.error("No selected file.")
            return json.dumps({"status": "error", "message": "No selected file."}), 400

        # Get user_id from form data
        user_id = request.form.get('user_id')
        if not user_id:
             logger.error("No user_id in form data.")
             return json.dumps({"status": "error", "message": "User ID not provided."}), 400
        
        # Read file bytes
        image_bytes = file.read()

        # Use existing photo processing logic
        text = ocr_space_recognize(image_bytes)
        print(f"[DEBUG] Распознанный текст (OCR.Space) from upload: {repr(text)}")

        beer_info = {}
        if text.strip():
            beer_info = get_beer_info(text)
            # Update rating with user ratings (if applicable)
            beer_info['rating'] = get_avg_rating(beer_info.get('name', ''), beer_info.get('rating', '-')) # Pass default value for get_avg_rating
        else:
             beer_info = {"name": "-", "description": "Не удалось распознать текст.", "rating": "-", "reviews": [], "price_quality_ratio": "-"}

        # Send result back to the user in chat
        bot = Bot(BOT_TOKEN) # Create a bot instance
        response_text = format_beer_info(beer_info)
        # You might want to add inline keyboard for rating here too
        try:
             await bot.send_message(chat_id=user_id, text=response_text, parse_mode='MarkdownV2')
        except Exception as send_e:
             logger.error(f"Error sending message to user {user_id}: {send_e}")
             return json.dumps({"status": "error", "message": "Failed to send message to Telegram chat."}), 500

        return json.dumps({"status": "success", "message": "Photo processed and info sent to chat."}), 200

    except Exception as e:
        logger.error(f"Error processing uploaded photo: {e}")
        return json.dumps({"status": "error", "message": "Internal server error during photo processing."}), 500 