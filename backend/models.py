"""
Business rules (login logic, password rules, reset/verification flow, what a profile
edit is allowed to change, email notifications) belong to the backend routes in app.py.

Every function takes the Mongo collection as an argument, e.g.
    models.add_card(users_collection, user_id, "4111111111111111", "Visa", "12/28")

USER DOCUMENT SHAPE
{
  userId, userType ("Customer"|"Admin"), firstName, lastName,
  email (lowercase, UNIQUE), phone, passwordHash,
  status ("Inactive"|"Active"|"Suspended"), promoOptIn (bool),
  address: {street, city, state, postalCode, country} | None,     # max 1
  savedCards: [{cardId, cardType, last4, encryptedCardNumber, expirationDate}],  # max 3
  favorites: [tmdb_id, ...],
  createdAt
}
TOKEN DOCUMENT SHAPE (collection "tokens"; the verify/reset logic is the backend's job)
{ tokenHash, userId, type ("verify"|"reset"), expiresAt, used }
"""
import re
import uuid
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from security import hash_password, encrypt_card

MAX_CARDS = 3

def format_movie(movie):
    """Formats a MongoDB document into clean JSON for the frontend."""
    return {
        "tmdb_id": movie.get("tmdb_id"),
        "title": movie.get("title", ""),
        "description": movie.get("description", ""),
        "poster_url": movie.get("poster_url", ""),
        "trailer_url": movie.get("trailer_url", ""),
        "rating": movie.get("rating", "NR"),
        "genre": movie.get("genre", "Unspecified"),
        "status": movie.get("status", "Currently Running"),
        "showtimes": movie.get("showtimes", [])
    }


def format_card(card):
    """Safe card view: only the last 4 digits ever leave the backend."""
    return {
        "card_id": card.get("cardId"),
        "card_type": card.get("cardType", ""),
        "last4": card.get("last4", ""),
        "expiration_date": card.get("expirationDate", "")
    }


def format_user(user):
    return {
        "user_id": user.get("userId"),
        "user_type": user.get("userType", "Customer"),
        "first_name": user.get("firstName", ""),
        "last_name": user.get("lastName", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "status": user.get("status", "Inactive"),
        "promo_opt_in": user.get("promoOptIn", False),
        "address": user.get("address"),
        "saved_cards": [format_card(c) for c in user.get("savedCards", [])],
        "favorites": user.get("favorites", [])
    }


def format_theatre(theatre):
    return {
        "theatre_id": theatre.get("theatreId"),
        "name": theatre.get("name", ""),
        "showrooms": theatre.get("showrooms", [])
    }


def format_promotion(promo):
    return {
        "promotion_id": promo.get("promotionId"),
        "code": promo.get("code", ""),
        "discount_percent": promo.get("discountPercent", 0.0),
        "valid_from": promo.get("validFrom"),
        "valid_until": promo.get("validUntil")
    }


# INDEXES (call once at startup / from seed)
def ensure_indexes(db):
    db["users"].create_index("email", unique=True)
    db["users"].create_index("userId", unique=True)
    db["tokens"].create_index("tokenHash")
    # TTL index: Mongo deletes expired tokens automatically
    db["tokens"].create_index("expiresAt", expireAfterSeconds=0)


# USERS (storage only)
def new_user_doc(first_name, last_name, email, phone, password,
                 promo_opt_in=False, user_type="Customer", status="Inactive"):
    """Builds a user document. The password is hashed here, never stored raw."""
    return {
        "userId": f"usr_{uuid.uuid4().hex[:12]}",
        "userType": user_type,
        "firstName": first_name.strip(),
        "lastName": last_name.strip(),
        "email": email.strip().lower(),
        "phone": phone.strip(),
        "passwordHash": hash_password(password),
        "status": status,                 # new registrations are Inactive until verified
        "promoOptIn": bool(promo_opt_in),
        "address": None,
        "savedCards": [],
        "favorites": [],
        "createdAt": datetime.now(timezone.utc)
    }


def create_user(users, first_name, last_name, email, phone, password, promo_opt_in=False):
    """Inserts a new Inactive customer. Returns the doc, or None if the email already exists."""
    doc = new_user_doc(first_name, last_name, email, phone, password, promo_opt_in)
    try:
        users.insert_one(doc)
    except DuplicateKeyError:
        return None
    return doc


def get_user_by_email(users, email):
    return users.find_one({"email": email.strip().lower()}, {"_id": 0})


def get_user_by_id(users, user_id):
    return users.find_one({"userId": user_id}, {"_id": 0})


# ADDRESS (max ONE - it's a single embedded object)
def set_address(users, user_id, address):
    clean = {k: str(address.get(k, "")).strip()
             for k in ("street", "city", "state", "postalCode", "country")}
    r = users.update_one({"userId": user_id}, {"$set": {"address": clean}})
    return r.matched_count == 1


def delete_address(users, user_id):
    r = users.update_one({"userId": user_id}, {"$set": {"address": None}})
    return r.matched_count == 1


# PAYMENT CARDS (max THREE, enforced atomically in the database)
def build_card(card_number, card_type, expiration_date):
    """Builds a card subdocument. Number is encrypted; only last4 is kept in the clear."""
    digits = re.sub(r"\D", "", card_number)
    if not 13 <= len(digits) <= 19:
        raise ValueError("Card number must be 13-19 digits.")
    return {
        "cardId": f"card_{uuid.uuid4().hex[:10]}",
        "cardType": card_type,
        "last4": digits[-4:],
        "encryptedCardNumber": encrypt_card(digits),
        "expirationDate": expiration_date          # "MM/YY"
    }


def add_card(users, user_id, card_number, card_type, expiration_date):
    """
    Adds a card only if the user has fewer than 3 (one atomic update, so two
    simultaneous requests can't sneak in a 4th). Returns True/False.
    NEVER accept or store the CVV.
    """
    card = build_card(card_number, card_type, expiration_date)
    r = users.update_one(
        {"userId": user_id, f"savedCards.{MAX_CARDS - 1}": {"$exists": False}},
        {"$push": {"savedCards": card}})
    return r.modified_count == 1        # False => limit reached (or user not found)


def update_card(users, user_id, card_id, expiration_date=None, card_type=None):
    updates = {}
    if expiration_date:
        updates["savedCards.$.expirationDate"] = expiration_date
    if card_type:
        updates["savedCards.$.cardType"] = card_type
    if not updates:
        return False
    r = users.update_one({"userId": user_id, "savedCards.cardId": card_id},
                         {"$set": updates})
    return r.matched_count == 1


def delete_card(users, user_id, card_id):
    r = users.update_one({"userId": user_id},
                         {"$pull": {"savedCards": {"cardId": card_id}}})
    return r.modified_count == 1


# FAVORITES
def add_favorite(users, user_id, tmdb_id):
    """$addToSet means a movie can never be favorited twice."""
    r = users.update_one({"userId": user_id}, {"$addToSet": {"favorites": tmdb_id}})
    return r.matched_count == 1


def remove_favorite(users, user_id, tmdb_id):
    r = users.update_one({"userId": user_id}, {"$pull": {"favorites": tmdb_id}})
    return r.matched_count == 1


def get_favorite_movies(users, movies, user_id):
    user = get_user_by_id(users, user_id)
    if not user:
        return []
    found = movies.find({"tmdb_id": {"$in": user.get("favorites", [])}}, {"_id": 0})
    return [format_movie(m) for m in found]