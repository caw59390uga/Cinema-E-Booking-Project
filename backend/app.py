import os
import re
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone
from models import format_movie, format_user, format_theatre, format_promotion

load_dotenv()

app = Flask(__name__)
CORS(app)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["cinema_db"]
movies_collection = db["movies"]
users_collection = db["users"]
theatres_collection = db["theatres"]
promotions_collection = db["promotions"]

@app.route('/api/movies', methods=['GET'])
def get_movies():
    try:
        status_filter = request.args.get('status')
        query = {}
        if status_filter:
            query["status"] = {"$regex": f"^{status_filter}$", "$options": "i"}
            
        movies = list(movies_collection.find(query, {"_id": 0}))
        return jsonify([format_movie(m) for m in movies]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/movies/search', methods=['GET'])
def search_movies():
    try:
        title_query = request.args.get('title', '').strip()
        if not title_query:
            return jsonify([]), 200

        query = {"title": {"$regex": title_query, "$options": "i"}}
        movies = list(movies_collection.find(query, {"_id": 0}))
        return jsonify([format_movie(m) for m in movies]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/movies/filter', methods=['GET'])
def filter_movies():
    try:
        genre_query = request.args.get('genre', '').strip()
        if not genre_query:
            return jsonify([]), 200

        query = {"genre": {"$regex": f"^{genre_query}$", "$options": "i"}}
        movies = list(movies_collection.find(query, {"_id": 0}))
        return jsonify([format_movie(m) for m in movies]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/movies/<int:tmdb_id>', methods=['GET'])
def get_movie_by_id(tmdb_id):
    try:
        movie = movies_collection.find_one({"tmdb_id": tmdb_id}, {"_id": 0})
        if not movie:
            return jsonify({"error": "Movie not found"}), 404

        return jsonify(format_movie(movie)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# GET /api/users/demo - a clearly labeled, seeded sample profile.
# Do not expose saved payment cards, addresses, or arbitrary user accounts without login.
@app.route('/api/users/demo', methods=['GET'])
def get_demo_profile():
    try:
        demo = users_collection.find_one({
            'userId': 'usr_cust_101',
            'email': 'alex.rivera@example.com'
        }, {'_id': 0})
        if demo is None:
            return jsonify({'error': 'Sample account not found. No user is signed in.'}), 404
        formatted = format_user(demo)
        return jsonify({
            'demo': True,
            'user': {key: formatted.get(key) for key in (
                'user_id', 'user_type', 'first_name', 'last_name', 'email', 'state'
            )}
        }), 200
    except Exception:
        app.logger.exception('Could not load demo profile')
        return jsonify({'error': 'Unable to load profile'}), 500


@app.route('/api/theatres', methods=['GET'])
def get_theatres():
    try:
        theatres = list(theatres_collection.find({}, {'_id': 0}))
        return jsonify([format_theatre(theatre) for theatre in theatres]), 200
    except Exception:
        app.logger.exception('Could not load theatres')
        return jsonify({'error': 'Unable to load theatres'}), 500


def public_promotion(document):
    promotion = format_promotion(document)
    for key in ('valid_from', 'valid_until'):
        value = promotion.get(key)
        if isinstance(value, datetime):
            promotion[key] = value.isoformat()
    return promotion


def active_promotion(document, now=None):
    now = now or datetime.now(timezone.utc)
    start, end = document.get('validFrom'), document.get('validUntil')
    for value in (start, end):
        if value is None or not isinstance(value, datetime):
            return False
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return start <= now <= end


@app.route('/api/promotions', methods=['GET'])
def get_promotions():
    try:
        documents = promotions_collection.find({}, {'_id': 0})
        return jsonify([public_promotion(p) for p in documents if active_promotion(p)]), 200
    except Exception:
        app.logger.exception('Could not load promotions')
        return jsonify({'error': 'Unable to load promotions'}), 500


@app.route('/api/promotions/validate', methods=['GET'])
def validate_promotion():
    code = request.args.get('code', '').strip()
    if not code or len(code) > 80:
        return jsonify({'error': 'Enter a valid promotion code'}), 400
    try:
        promotion = promotions_collection.find_one(
            {'code': {'$regex': '^' + re.escape(code) + '$', '$options': 'i'}},
            {'_id': 0}
        )
        if not promotion or not active_promotion(promotion):
            return jsonify({'error': 'Promotion is invalid or expired'}), 404
        discount = float(promotion.get('discountPercent', 0))
        if not 0 <= discount <= 100:
            return jsonify({'error': 'Promotion discount is invalid'}), 400
        return jsonify(public_promotion(promotion)), 200
    except Exception:
        app.logger.exception('Could not validate promotion')
        return jsonify({'error': 'Unable to validate promotion'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
