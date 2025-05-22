from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RATINGS_FILE = 'ratings.json'

app = Flask(__name__)
# Configure CORS to allow requests from the frontend domain
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://frontend-telegram-webapp.vercel.app",
            "http://localhost:3000"  # For local development
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Получить средний рейтинг по названию пива
def get_avg_rating(beer_name):
    if os.path.exists(RATINGS_FILE):
        with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
            ratings = json.load(f)
        if beer_name in ratings and ratings[beer_name]:
            all_ratings = ratings[beer_name]
            return round(sum(all_ratings) / len(all_ratings), 2)
    return None

# Добавить новую оценку
def save_rating(beer_name, rating):
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

@app.route('/rating', methods=['GET'])
def get_rating():
    beer_name = request.args.get('beer')
    if not beer_name:
        return jsonify({'error': 'beer param required'}), 400
    avg = get_avg_rating(beer_name)
    return jsonify({'beer': beer_name, 'avg_rating': avg})

@app.route('/rating', methods=['POST'])
def post_rating():
    data = request.get_json()
    beer_name = data.get('beer')
    rating = data.get('rating')
    if not beer_name or not isinstance(rating, int):
        return jsonify({'error': 'beer and int rating required'}), 400
    save_rating(beer_name, rating)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    # Only use debug mode in development
    debug = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug) 