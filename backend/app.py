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
    """TC1: Create user account (Inactive status, sends verification token)"""
    data = request.json or {}
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    email = data.get("email")
    phone = data.get("phone", "")
    password = data.get("password")
    promo_opt_in = data.get("promo_opt_in", False)

    if not all([first_name, last_name, email, password]):
        return jsonify({"error": "Missing required registration fields"}), 400

    user_doc = create_user(users_collection, first_name, last_name, email, phone, password, promo_opt_in)
    if not user_doc:
        return jsonify({"error": "An account with this email already exists"}), 400

    # Generate verification token
    raw_token = generate_token()
    token_doc = {
        "tokenHash": hash_token(raw_token),
        "userId": user_doc["userId"],
        "type": "verify",
        "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
        "used": False
    }
    tokens_collection.insert_one(token_doc)

    print(f"\n[DEMO EMAIL VERIFICATION LINK]: http://127.0.0.1:5000/api/auth/verify?token={raw_token}\n")

    return jsonify({
        "message": "Account created successfully! Please check your email to verify your account.",
        "user_id": user_doc["userId"],
        "status": "Inactive",
        "demo_verify_token": raw_token
    }), 201


@app.route('/api/auth/verify', methods=['GET', 'POST'])
def verify_account():
    """TC3: Verify account using token"""
    token = request.args.get('token') or (request.json or {}).get('token')
    if not token:
        return jsonify({"error": "Token is required"}), 400

    token_hash = hash_token(token)
    token_record = tokens_collection.find_one({"tokenHash": token_hash, "type": "verify", "used": False})

    if not token_record:
        return jsonify({"error": "Invalid or expired verification token"}), 400

    # Activate User
    users_collection.update_one({"userId": token_record["userId"]}, {"$set": {"status": "Active"}})
    tokens_collection.update_one({"_id": token_record["_id"]}, {"$set": {"used": True}})

    return jsonify({"message": "Account successfully verified! You may now log in."}), 200


@app.route('/api/auth/login', methods=['POST'])
def login():
    """TC2, TC4, TC5, TC6: Login handler for Verified, Unverified, and Admin accounts"""
    data = request.json or {}
    email = data.get("email", "")
    password = data.get("password", "")

    user = get_user_by_email(users_collection, email)
    if not user or not verify_password(password, user.get("passwordHash", "")):
        return jsonify({"error": "Invalid email or password."}), 401

    # TC2 check: Unverified account
    if user.get("status") == "Inactive":
        return jsonify({"error": "Account is not verified. Please check your email to verify your account."}), 403

    if user.get("status") == "Suspended":
        return jsonify({"error": "Your account has been suspended."}), 403

    # TC4/TC6: Successful Login
    return jsonify({
        "message": "Login successful",
        "user": format_user(user)
    }), 200


@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json or {}
    email = data.get("email", "")
    user = get_user_by_email(users_collection, email)
    if not user:
        return jsonify({"message": "If the account exists, a reset link has been generated."}), 200

    raw_token = generate_token()
    tokens_collection.insert_one({
        "tokenHash": hash_token(raw_token),
        "userId": user["userId"],
        "type": "reset",
        "expiresAt": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False
    })

    print(f"\n[DEMO PASSWORD RESET LINK]: http://127.0.0.1:5000/api/auth/reset-password?token={raw_token}\n")
    return jsonify({"message": "Password reset token generated.", "demo_reset_token": raw_token}), 200


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.json or {}
    token = data.get("token")
    new_password = data.get("new_password")

    if not token or not new_password:
        return jsonify({"error": "Token and new password required"}), 400

    token_hash = hash_token(token)
    token_record = tokens_collection.find_one({"tokenHash": token_hash, "type": "reset", "used": False})

    if not token_record:
        return jsonify({"error": "Invalid or expired reset token"}), 400

    new_hash = hash_password(new_password)
    users_collection.update_one({"userId": token_record["userId"]}, {"$set": {"passwordHash": new_hash}})
    tokens_collection.update_one({"_id": token_record["_id"]}, {"$set": {"used": True}})

    return jsonify({"message": "Password successfully reset."}), 200


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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
