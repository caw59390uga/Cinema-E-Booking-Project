import os
import certifi
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv

from models import (
    format_movie, format_user, create_user, get_user_by_email, get_user_by_id,
    set_address, add_card, delete_card, add_favorite, remove_favorite,
    get_favorite_movies, ensure_indexes
)
from security import (
    hash_password, verify_password, generate_token, hash_token
)
from account_security import (
    registration as secure_registration, resend_verification as secure_resend,
    verify_registration as secure_verify, forgot_password as secure_forgot,
    reset_password as secure_reset, change_password as secure_change_password,
    require_owner, read_authenticated_user, make_access_token
)

load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["cinema_db"]

movies_collection = db["movies"]
users_collection = db["users"]
tokens_collection = db["tokens"]

# Ensure DB indexes exist on startup
ensure_indexes(db)


# ==========================================
# 1. MOVIE ENDPOINTS (SPRINT 1)
# ==========================================

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


# ==========================================
# 2. AUTHENTICATION & REGISTRATION (SPRINT 2)
# ==========================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    return secure_registration(users_collection, tokens_collection)


@app.route('/api/auth/verify', methods=['GET', 'POST'])
def verify_account():
    return secure_verify(users_collection, tokens_collection)


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '')
    password = data.get('password', '')
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({'error': 'Invalid email or password.'}), 401
    user = get_user_by_email(users_collection, email)
    if not user or not verify_password(password, user.get('passwordHash', '')):
        return jsonify({'error': 'Invalid email or password.'}), 401
    if user.get('status') == 'Inactive':
        return jsonify({'error': 'Account is not verified. Please check your email to verify your account.'}), 403
    if user.get('status') != 'Active':
        return jsonify({'error': 'Account access is not available.'}), 403
    try:
        token = make_access_token(user)
    except RuntimeError:
        return jsonify({'error': 'Account service configuration is incomplete.'}), 503
    return jsonify({'message': 'Login successful', 'user': format_user(user),
                    'access_token': token, 'token_type': 'Bearer',
                    'expires_in': 43200}), 200


@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    return secure_forgot(users_collection, tokens_collection)


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    return secure_reset(users_collection, tokens_collection)


# ==========================================
# 3. PROFILE MANAGEMENT (TC7, TC8, TC9, TC10)
# ==========================================

@app.route('/api/users/<user_id>', methods=['GET'])
def get_profile(user_id):
    user = get_user_by_id(users_collection, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(format_user(user)), 200


@app.route('/api/users/<user_id>/profile', methods=['PUT'])
def update_profile(user_id):
    """Updates profile details. Sends email notification on change."""
    data = request.json or {}

    # Allow only shape-checked fields. The email address is deliberately read-only.
    if 'address' in data:
        if not isinstance(data['address'], dict):
            return jsonify({'error': 'Address must be an object.'}), 400
        allowed = ('street','city','state','postalCode','country')
        if any(not isinstance(data['address'].get(k,''), str) or len(data['address'].get(k,'')) > 120 for k in allowed):
            return jsonify({'error': 'Address fields must contain up to 120 characters.'}), 400
    for k in ('first_name','last_name','phone'):
        if k in data and (not isinstance(data[k], str) or len(data[k]) > 120):
            return jsonify({'error': f'Invalid {k}.'}), 400
    if 'promo_opt_in' in data and not isinstance(data['promo_opt_in'], bool):
        return jsonify({'error': 'Invalid promotional preference.'}), 400
    user = get_user_by_id(users_collection, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    updates = {}
    if "first_name" in data:
        updates["firstName"] = data["first_name"].strip()
    if "last_name" in data:
        updates["lastName"] = data["last_name"].strip()
    if "phone" in data:
        updates["phone"] = data["phone"].strip()
    if "promo_opt_in" in data:
        updates["promoOptIn"] = bool(data["promo_opt_in"])

    # Update address if provided
    if "address" in data:
        set_address(users_collection, user_id, data["address"])

    if updates:
        users_collection.update_one({"userId": user_id}, {"$set": updates})

    print(f"\n[EMAIL NOTIFICATION]: Profile updated for user {user.get('email')}\n")
    
    updated_user = get_user_by_id(users_collection, user_id)
    return jsonify({"message": "Profile updated successfully.", "user": format_user(updated_user)}), 200


@app.route('/api/users/<user_id>/cards', methods=['POST'])
def add_user_card(user_id):
    """TC7: Adds payment card. Enforces max limit of 3 cards."""
    data = request.json or {}
    card_number = data.get("card_number")
    card_type = data.get("card_type", "Visa")
    expiration_date = data.get("expiration_date")

    if not card_number or not expiration_date:
        return jsonify({"error": "Card number and expiration date required"}), 400
    if not isinstance(card_number, str) or not isinstance(expiration_date, str):
        return jsonify({'error': 'Card number and expiry must be text.'}), 400
    import re as _re
    from datetime import datetime as _dt
    match = _re.fullmatch(r'(0[1-9]|1[0-2])/(\d{2})', expiration_date)
    if not match:
        return jsonify({'error': 'Expiry must be MM/YY.'}), 400
    exp_year = 2000 + int(match.group(2)); exp_month = int(match.group(1))
    today = _dt.now()
    if (exp_year, exp_month) < (today.year, today.month):
        return jsonify({'error': 'Card has expired.'}), 400
    if card_type not in ('Visa','Mastercard','Amex','Discover'):
        return jsonify({'error': 'Unsupported card type.'}), 400

    try:
        success = add_card(users_collection, user_id, card_number, card_type, expiration_date)
        if not success:
            return jsonify({"error": "Cannot add card. Maximum limit of 3 payment cards reached."}), 400
        
        updated_user = get_user_by_id(users_collection, user_id)
        return jsonify({"message": "Card added successfully.", "user": format_user(updated_user)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/users/<user_id>/cards/<card_id>', methods=['DELETE'])
def remove_user_card(user_id, card_id):
    success = delete_card(users_collection, user_id, card_id)
    if not success:
        return jsonify({"error": "Card not found or could not be removed"}), 400
    
    updated_user = get_user_by_id(users_collection, user_id)
    return jsonify({"message": "Card removed successfully.", "user": format_user(updated_user)}), 200


# ==========================================
# 4. FAVORITES MANAGEMENT (TC8, TC9)
# ==========================================

@app.route('/api/users/<user_id>/favorites', methods=['GET'])
def get_favorites(user_id):
    favs = get_favorite_movies(users_collection, movies_collection, user_id)
    return jsonify(favs), 200


@app.route('/api/users/<user_id>/favorites', methods=['POST'])
def add_fav(user_id):
    """TC8: Add movie to favorites"""
    data = request.json or {}
    tmdb_id = data.get("tmdb_id")
    if not tmdb_id:
        return jsonify({"error": "tmdb_id required"}), 400

    add_favorite(users_collection, user_id, tmdb_id)
    return jsonify({"message": "Movie added to favorites."}), 200


@app.route('/api/users/<user_id>/favorites/<int:tmdb_id>', methods=['DELETE'])
def remove_fav(user_id, tmdb_id):
    remove_favorite(users_collection, user_id, tmdb_id)
    return jsonify({"message": "Movie removed from favorites."}), 200



# Account pages / secure profile contract. Keep these routes available for the
# teammate's router and useAuth hook to use once their work lands.
@app.before_request
def protect_private_user_routes():
    if request.method == "OPTIONS":
        return None
    protected = {
        'get_profile', 'update_profile', 'add_user_card', 'remove_user_card',
        'get_favorites', 'add_fav', 'remove_fav', 'change_account_password'
    }
    if request.endpoint in protected:
        user_id = (request.view_args or {}).get('user_id')
        return require_owner(users_collection, user_id)


@app.route('/api/auth/me', methods=['GET'])
def account_me():
    user = read_authenticated_user(users_collection)
    if user is None:
        return jsonify({'error': 'Sign in to view your profile.'}), 401
    return jsonify({'user': format_user(user)}), 200


@app.route('/api/auth/resend-verification', methods=['POST'])
def account_resend_verification():
    return secure_resend(users_collection, tokens_collection)


@app.route('/api/users/<user_id>/change-password', methods=['POST'])
def change_account_password(user_id):
    return secure_change_password(users_collection, user_id)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
