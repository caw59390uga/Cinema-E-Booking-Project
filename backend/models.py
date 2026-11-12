"""
models.py - DATABASE LAYER ONLY: schema, formatters, indexes, and storage-level helpers.

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

----------------------------- SPRINT 3 ADDITIONS -----------------------------
The Sprint 3 functions (movies, showrooms, showtimes, seats, promotions, pricing)
take the whole database, e.g.   models.create_showtime(db, tmdb_id, "room_01", start)

MOVIE  (collection "movies")
{ tmdb_id (unique; admin-added movies get ids from 9,000,000 up), title, description,
  poster_url, trailer_url, rating (MPAA), genre, status ("Currently Running"|"Coming Soon"),
  runtime (minutes), cast [names], director, producer, reviews [{author, content}] }
  Showtimes are NOT stored on the movie any more. They live in "showtimes".

SHOWROOM  (collection "showrooms")
{ showroomId, name, rows ["A","B",...], seatsPerRow, seatCount }
  Seat ids are generated: row letter + number, e.g. "A1", "C10".

SHOWTIME  (collection "showtimes")
{ showtimeId, tmdb_id, showroomId, startTime, endTime, createdAt }
  All datetimes are stored as UTC. API output is ISO text ending in "Z".
  Same showroom + same startTime is impossible (unique index), and overlapping
  showings in a showroom are rejected by create_showtime().

BOOKING  (collection "bookings", ONE DOCUMENT PER SEAT)
{ showtimeId, seatId, holderId, status ("held"|"booked"), orderId, createdAt, expiresAt }
  Unique index on (showtimeId, seatId): the database itself refuses a double booking.
  holderId is the userId, or a guest session id while the user is logged out.
  expiresAt is only set on held seats and has a TTL index (used for the 5 minute unlock).

PRICING  (collection "settings", one document with settingsId "pricing")
{ settingsId, prices {Adult, Child, Senior}, bookingFee, taxRate }

PROMOTION  (collection "promotions")
{ promotionId, code (unique, uppercase), discountPercent, validFrom, validUntil }
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, OperationFailure

from security import hash_password, encrypt_card

MAX_CARDS = 3

# ---- Sprint 3 constants (the backend and frontend can reuse these lists) ----
MAX_SEATS_PER_BOOKING = 8
DEFAULT_RUNTIME_MINUTES = 120
SHOWROOM_CLEANUP_MINUTES = 15        # gap kept free between two showings in one room
CUSTOM_MOVIE_ID_BASE = 9_000_000     # ids for admin-added movies (TMDB ids stay below this)
MPAA_RATINGS = ("G", "PG", "PG-13", "R", "NC-17", "NR")
MOVIE_STATUSES = ("Currently Running", "Coming Soon")
MOVIE_GENRES = ("Action", "Comedy", "Drama", "Sci-Fi", "Horror", "Romance")
TICKET_TYPES = ("Adult", "Child", "Senior")
DEFAULT_PRICING = {"prices": {"Adult": 13.50, "Child": 9.00, "Senior": 11.00},
                   "bookingFee": 2.50, "taxRate": 0.08}

# TIME HELPERS - everything is stored as UTC (pymongo hands datetimes back as naive UTC)
def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt):
    """Accepts naive (treated as UTC) or timezone-aware datetimes."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso_utc(dt):
    return None if dt is None else to_naive_utc(dt).isoformat() + "Z"


def format_movie(movie, showtimes=None):
    """
    Formats a MongoDB document into clean JSON for the frontend.
    `showtimes` is a list of format_showtime() results (see showtimes_by_movie);
    leave it out and the movie simply has no showtimes yet.
    """
    return {
        "tmdb_id": movie.get("tmdb_id"),
        "title": movie.get("title", ""),
        "description": movie.get("description", ""),
        "poster_url": movie.get("poster_url", ""),
        "trailer_url": movie.get("trailer_url", ""),
        "rating": movie.get("rating", "NR"),
        "genre": movie.get("genre", "Unspecified"),
        "status": movie.get("status", "Currently Running"),
        "runtime": movie.get("runtime", DEFAULT_RUNTIME_MINUTES),
        "cast": movie.get("cast", []),
        "director": movie.get("director", ""),
        "producer": movie.get("producer", ""),
        "reviews": movie.get("reviews", []),
        "showtimes": showtimes if showtimes is not None else []
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


def format_showroom(showroom):
    return {
        "showroom_id": showroom.get("showroomId"),
        "name": showroom.get("name", ""),
        "rows": showroom.get("rows", []),
        "seats_per_row": showroom.get("seatsPerRow", 0),
        "seat_count": showroom.get("seatCount", 0)
    }


def format_showtime(showtime, showroom=None, movie=None):
    """showroom / movie are optional documents used to add names to the output."""
    out = {
        "showtime_id": showtime.get("showtimeId"),
        "tmdb_id": showtime.get("tmdb_id"),
        "showroom_id": showtime.get("showroomId"),
        "start_time": iso_utc(showtime.get("startTime")),
        "end_time": iso_utc(showtime.get("endTime"))
    }
    if showroom is not None:
        out["showroom_name"] = showroom.get("name", "")
    if movie is not None:
        out["movie_title"] = movie.get("title", "")
    return out


def format_promotion(promo):
    return {
        "promotion_id": promo.get("promotionId"),
        "code": promo.get("code", ""),
        "discount_percent": promo.get("discountPercent", 0.0),
        "valid_from": iso_utc(promo.get("validFrom")),
        "valid_until": iso_utc(promo.get("validUntil"))
    }


# INDEXES (call once at startup / from seed)
def ensure_indexes(db):
    db["users"].create_index("email", unique=True)
    db["users"].create_index("userId", unique=True)
    db["tokens"].create_index("tokenHash")
    # TTL index: Mongo deletes expired tokens automatically
    db["tokens"].create_index("expiresAt", expireAfterSeconds=0)

    # ---- Sprint 3 ----
    try:
        db["movies"].create_index("tmdb_id", unique=True)
    except OperationFailure:
        # An old database can hold duplicate movies. Don't crash the server over it.
        print("WARNING: duplicate movies found, so the unique tmdb_id index was not "
              "created. Run `python seed.py` to rebuild the data.")
    db["movies"].create_index("status")
    db["showrooms"].create_index("showroomId", unique=True)
    db["showtimes"].create_index("showtimeId", unique=True)
    # Same showroom + same start time can never exist twice (hard backstop for conflicts)
    db["showtimes"].create_index([("showroomId", 1), ("startTime", 1)], unique=True)
    db["showtimes"].create_index([("tmdb_id", 1), ("startTime", 1)])
    # One document per seat per showing: the database refuses double bookings
    db["bookings"].create_index([("showtimeId", 1), ("seatId", 1)], unique=True)
    db["bookings"].create_index([("showtimeId", 1), ("holderId", 1)])
    # Held seats carry expiresAt and vanish by themselves; booked seats have no expiresAt
    db["bookings"].create_index("expiresAt", expireAfterSeconds=0)
    db["promotions"].create_index("code", unique=True)
    db["settings"].create_index("settingsId", unique=True)


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

# =====================================================================
# ===========================  SPRINT 3  ==============================
# =====================================================================

# ---------------------------------------------------------------------
# MOVIES (admin "Add Movie")
# ---------------------------------------------------------------------
_URL_RE = re.compile(r"^https?://\S+$")


def _clean_list(value):
    """Accepts a list or a comma/newline separated string and returns a list of strings."""
    if isinstance(value, str):
        value = re.split(r"[,\n]", value)
    if not isinstance(value, (list, tuple)):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _clean_reviews(value):
    """Accepts a list of strings or {author, content} dicts, or one text block."""
    if isinstance(value, str):
        value = [v for v in value.split("\n") if v.strip()]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for r in value:
        if isinstance(r, dict):
            text = str(r.get("content", "")).strip()
            if text:
                out.append({"author": str(r.get("author", "")).strip(), "content": text})
        elif str(r).strip():
            out.append({"author": "", "content": str(r).strip()})
    return out


def check_movie_fields(data):
    """
    Returns a dict {field: message} describing everything wrong with an Add Movie
    form (empty dict = fine). The backend can show these next to each field.
    """
    errors = {}
    title = str(data.get("title", "")).strip()
    if not title:
        errors["title"] = "Title is required."
    elif len(title) > 200:
        errors["title"] = "Title must be 200 characters or fewer."
    if data.get("genre") not in MOVIE_GENRES:
        errors["genre"] = "Choose a category: " + ", ".join(MOVIE_GENRES) + "."
    if data.get("rating") not in MPAA_RATINGS:
        errors["rating"] = "Choose an MPAA rating: " + ", ".join(MPAA_RATINGS) + "."
    if data.get("status") not in MOVIE_STATUSES:
        errors["status"] = "Status must be Currently Running or Coming Soon."
    synopsis = str(data.get("description", "")).strip()
    if not synopsis:
        errors["description"] = "Synopsis is required."
    elif len(synopsis) > 3000:
        errors["description"] = "Synopsis must be 3000 characters or fewer."
    if not _clean_list(data.get("cast")):
        errors["cast"] = "Enter at least one cast member."
    for field, label in (("director", "Director"), ("producer", "Producer")):
        value = str(data.get(field, "")).strip()
        if not value:
            errors[field] = f"{label} is required."
        elif len(value) > 200:
            errors[field] = f"{label} must be 200 characters or fewer."
    for field, label in (("poster_url", "Poster image"), ("trailer_url", "Trailer video")):
        if not _URL_RE.match(str(data.get(field, "")).strip()):
            errors[field] = f"{label} must be a web address starting with http:// or https://"
    runtime = data.get("runtime", DEFAULT_RUNTIME_MINUTES)
    if isinstance(runtime, bool) or not isinstance(runtime, int) or not 30 <= runtime <= 400:
        errors["runtime"] = "Runtime must be a whole number of minutes between 30 and 400."
    return errors


def next_movie_id(db):
    """Atomic counter, so two admins adding movies at once never share an id."""
    counter = db["counters"].find_one_and_update(
        {"_id": "movie_id"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=ReturnDocument.AFTER)
    return CUSTOM_MOVIE_ID_BASE + counter["seq"]


def create_movie(db, data):
    """
    Stores an admin-added movie. Returns (movie_json, None) on success or
    (None, {field: message}) when the form is invalid or the title already exists.
    """
    errors = check_movie_fields(data)
    if errors:
        return None, errors
    title = str(data["title"]).strip()
    if db["movies"].find_one({"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}}):
        return None, {"title": "A movie with this title already exists."}
    doc = {
        "tmdb_id": next_movie_id(db),
        "title": title,
        "description": str(data["description"]).strip(),
        "poster_url": str(data["poster_url"]).strip(),
        "trailer_url": str(data["trailer_url"]).strip(),
        "rating": data["rating"],
        "genre": data["genre"],
        "status": data["status"],
        "runtime": data.get("runtime", DEFAULT_RUNTIME_MINUTES),
        "cast": _clean_list(data["cast"]),
        "director": str(data["director"]).strip(),
        "producer": str(data["producer"]).strip(),
        "reviews": _clean_reviews(data.get("reviews", [])),
    }
    db["movies"].insert_one(doc)
    return format_movie(doc), None


def _movie_runtime(movie):
    runtime = movie.get("runtime")
    return runtime if isinstance(runtime, int) and runtime > 0 else DEFAULT_RUNTIME_MINUTES


# ---------------------------------------------------------------------
# SHOWROOMS
# ---------------------------------------------------------------------
def build_showroom(showroom_id, name, rows, seats_per_row):
    rows = list(rows)
    return {"showroomId": showroom_id, "name": name, "rows": rows,
            "seatsPerRow": seats_per_row, "seatCount": len(rows) * seats_per_row}


def seat_ids_for(showroom):
    """Every seat id in a showroom, in order: A1, A2 ... B1, B2 ..."""
    return [f"{row}{n}" for row in showroom["rows"]
            for n in range(1, showroom["seatsPerRow"] + 1)]


def get_showroom(db, showroom_id):
    return db["showrooms"].find_one({"showroomId": showroom_id}, {"_id": 0})


def list_showrooms(db):
    return [format_showroom(s) for s in db["showrooms"].find({}, {"_id": 0}).sort("showroomId", 1)]


# ---------------------------------------------------------------------
# SHOWTIMES (admin scheduling + showtime visibility for users)
# ---------------------------------------------------------------------
def find_conflict(db, showroom_id, start_time, end_time, ignore_showtime_id=None):
    """
    Returns an existing showtime in this showroom that overlaps [start, end]
    (including the cleanup gap), or None when the room is free.
    """
    gap = timedelta(minutes=SHOWROOM_CLEANUP_MINUTES)
    start, end = to_naive_utc(start_time), to_naive_utc(end_time)
    query = {"showroomId": showroom_id,
             "startTime": {"$lt": end + gap},
             "endTime": {"$gt": start - gap}}
    if ignore_showtime_id:
        query["showtimeId"] = {"$ne": ignore_showtime_id}
    return db["showtimes"].find_one(query, {"_id": 0})


def create_showtime(db, tmdb_id, showroom_id, start_time):
    """
    Schedules a movie in a showroom. The end time comes from the movie's runtime.
    Returns (showtime_json, None) on success or (None, {"code", "message", ...}).
    Error codes: movie_not_found, showroom_not_found, invalid_time, conflict.
    """
    movie = db["movies"].find_one({"tmdb_id": tmdb_id}, {"_id": 0})
    if not movie:
        return None, {"code": "movie_not_found", "message": "Movie not found."}
    showroom = get_showroom(db, showroom_id)
    if not showroom:
        return None, {"code": "showroom_not_found", "message": "Showroom not found."}
    if not isinstance(start_time, datetime):
        return None, {"code": "invalid_time", "message": "A valid date and time is required."}

    start = to_naive_utc(start_time)
    end = start + timedelta(minutes=_movie_runtime(movie))

    def conflict_error(existing):
        return {"code": "conflict",
                "message": f"{showroom['name']} is already booked at that time.",
                "conflict": format_showtime(existing, showroom)}

    existing = find_conflict(db, showroom_id, start, end)
    if existing:
        return None, conflict_error(existing)

    doc = {"showtimeId": f"show_{uuid.uuid4().hex[:10]}", "tmdb_id": tmdb_id,
           "showroomId": showroom_id, "startTime": start, "endTime": end,
           "createdAt": utcnow()}
    try:
        db["showtimes"].insert_one(doc)
    except DuplicateKeyError:
        # Someone scheduled the exact same slot between our check and our insert.
        return None, conflict_error(db["showtimes"].find_one(
            {"showroomId": showroom_id, "startTime": start}, {"_id": 0}) or doc)
    return format_showtime(doc, showroom, movie), None


def list_available_showrooms(db, tmdb_id, start_time):
    """
    For the admin form: every showroom with "available": True/False for this movie
    at this start time, so the UI can grey out the rooms that would conflict.
    """
    movie = db["movies"].find_one({"tmdb_id": tmdb_id}, {"_id": 0})
    if not movie:
        return []
    start = to_naive_utc(start_time)
    end = start + timedelta(minutes=_movie_runtime(movie))
    out = []
    for room in db["showrooms"].find({}, {"_id": 0}).sort("showroomId", 1):
        item = format_showroom(room)
        item["available"] = find_conflict(db, room["showroomId"], start, end) is None
        out.append(item)
    return out


def showtimes_by_movie(db, tmdb_ids, include_past=False):
    """
    One query for many movies: {tmdb_id: [format_showtime, ...]} sorted by start.
    Past showings are left out unless include_past is True.
    """
    query = {"tmdb_id": {"$in": list(tmdb_ids)}}
    if not include_past:
        query["startTime"] = {"$gte": utcnow()}
    rooms = {r["showroomId"]: r for r in db["showrooms"].find({}, {"_id": 0})}
    grouped = {}
    for st in db["showtimes"].find(query, {"_id": 0}).sort("startTime", 1):
        grouped.setdefault(st["tmdb_id"], []).append(
            format_showtime(st, rooms.get(st["showroomId"])))
    return grouped


def list_showtimes_for_movie(db, tmdb_id, include_past=False):
    return showtimes_by_movie(db, [tmdb_id], include_past).get(tmdb_id, [])


def get_showtime(db, showtime_id):
    st = db["showtimes"].find_one({"showtimeId": showtime_id}, {"_id": 0})
    if not st:
        return None
    return format_showtime(st, get_showroom(db, st["showroomId"]),
                           db["movies"].find_one({"tmdb_id": st["tmdb_id"]}, {"_id": 0}))


# ---------------------------------------------------------------------
# SEATS (seat map, holding seats for a session, booking)
# ---------------------------------------------------------------------
def purge_expired_holds(db, showtime_id=None):
    """TTL cleanup runs about once a minute; this makes expiry exact when it matters."""
    query = {"status": "held", "expiresAt": {"$lte": utcnow()}}
    if showtime_id:
        query["showtimeId"] = showtime_id
    return db["bookings"].delete_many(query).deleted_count


def get_seat_map(db, showtime_id, holder_id=None):
    """
    Everything the seat-selection page needs, or None if the showtime doesn't exist.
    Seat status is "available", "booked" (taken by someone else) or "selected"
    (held by this holder_id).
    """
    st = db["showtimes"].find_one({"showtimeId": showtime_id}, {"_id": 0})
    if not st:
        return None
    showroom = get_showroom(db, st["showroomId"])
    movie = db["movies"].find_one({"tmdb_id": st["tmdb_id"]}, {"_id": 0})
    purge_expired_holds(db, showtime_id)
    taken = {b["seatId"]: b for b in db["bookings"].find({"showtimeId": showtime_id}, {"_id": 0})}

    seats = []
    for row in showroom["rows"]:
        for n in range(1, showroom["seatsPerRow"] + 1):
            seat_id = f"{row}{n}"
            b = taken.get(seat_id)
            if b is None:
                status = "available"
            elif b["status"] == "held" and holder_id and b["holderId"] == holder_id:
                status = "selected"
            else:
                status = "booked"
            seats.append({"seat_id": seat_id, "row": row, "number": n, "status": status})
    return {
        "showtime": format_showtime(st, showroom, movie),
        "showroom": format_showroom(showroom),
        "seats": seats,
        "available_count": sum(1 for s in seats if s["status"] == "available"),
        "booked_count": sum(1 for s in seats if s["status"] == "booked")
    }


def hold_seats(db, showtime_id, holder_id, seat_ids, hold_minutes=None):
    """
    Reserves exactly `seat_ids` for this holder (their earlier holds on this showing are
    replaced). All-or-nothing: if any seat is taken, nothing changes.
    hold_minutes=None keeps the hold until released (Sprint 3); pass 5 for the final demo.

    Returns {"ok": True, "seats": [...]} or {"ok": False, "reason": ..., "seats": [...]}
    Reasons: no_seats, too_many, showtime_not_found, showtime_started, invalid_seat, seats_taken.
    """
    seat_ids = list(dict.fromkeys(str(s).strip().upper() for s in seat_ids))
    if not seat_ids:
        return {"ok": False, "reason": "no_seats", "seats": []}
    if len(seat_ids) > MAX_SEATS_PER_BOOKING:
        return {"ok": False, "reason": "too_many", "seats": []}
    st = db["showtimes"].find_one({"showtimeId": showtime_id}, {"_id": 0})
    if not st:
        return {"ok": False, "reason": "showtime_not_found", "seats": []}
    if st["startTime"] <= utcnow():
        return {"ok": False, "reason": "showtime_started", "seats": []}
    valid = set(seat_ids_for(get_showroom(db, st["showroomId"])))
    invalid = [s for s in seat_ids if s not in valid]
    if invalid:
        return {"ok": False, "reason": "invalid_seat", "seats": invalid}

    bookings = db["bookings"]
    purge_expired_holds(db, showtime_id)
    mine = {"showtimeId": showtime_id, "holderId": holder_id, "status": "held"}
    existing = {b["seatId"] for b in bookings.find(mine, {"_id": 0, "seatId": 1})}
    expires = utcnow() + timedelta(minutes=hold_minutes) if hold_minutes else None

    inserted, taken = [], []
    for seat_id in seat_ids:
        if seat_id in existing:
            continue
        doc = {"showtimeId": showtime_id, "seatId": seat_id, "holderId": holder_id,
               "status": "held", "orderId": None, "createdAt": utcnow()}
        if expires:
            doc["expiresAt"] = expires
        try:
            inserted.append(bookings.insert_one(doc).inserted_id)
        except DuplicateKeyError:
            taken.append(seat_id)
    if taken:
        if inserted:
            bookings.delete_many({"_id": {"$in": inserted}})   # undo: all or nothing
        return {"ok": False, "reason": "seats_taken", "seats": taken}

    release = list(existing - set(seat_ids))
    if release:
        bookings.delete_many({**mine, "seatId": {"$in": release}})
    if expires and existing:
        bookings.update_many({**mine, "seatId": {"$in": list(existing & set(seat_ids))}},
                             {"$set": {"expiresAt": expires}})
    return {"ok": True, "seats": seat_ids}


def release_holds(db, showtime_id, holder_id, seat_ids=None):
    """Frees held seats (all of this holder's, or just `seat_ids`). Returns how many."""
    query = {"showtimeId": showtime_id, "holderId": holder_id, "status": "held"}
    if seat_ids is not None:
        query["seatId"] = {"$in": list(seat_ids)}
    return db["bookings"].delete_many(query).deleted_count


def transfer_holds(db, showtime_id, from_holder_id, to_holder_id):
    """
    Guests pick seats under a session id. When they log in at checkout, call this so
    the same seats now belong to their user id. Returns how many seats moved.
    """
    r = db["bookings"].update_many(
        {"showtimeId": showtime_id, "holderId": from_holder_id, "status": "held"},
        {"$set": {"holderId": to_holder_id}})
    return r.modified_count


def mark_booked(db, showtime_id, holder_id, order_id):
    """(Final demo) turns a holder's held seats into permanent bookings. Returns how many."""
    r = db["bookings"].update_many(
        {"showtimeId": showtime_id, "holderId": holder_id, "status": "held"},
        {"$set": {"status": "booked", "orderId": order_id}, "$unset": {"expiresAt": ""}})
    return r.modified_count


# ---------------------------------------------------------------------
# PRICING
# ---------------------------------------------------------------------
def get_pricing(db):
    """Ticket prices by age category, the booking fee and the tax rate."""
    doc = db["settings"].find_one({"settingsId": "pricing"}, {"_id": 0}) or {}
    return {
        "prices": {**DEFAULT_PRICING["prices"], **doc.get("prices", {})},
        "booking_fee": doc.get("bookingFee", DEFAULT_PRICING["bookingFee"]),
        "tax_rate": doc.get("taxRate", DEFAULT_PRICING["taxRate"])
    }


# ---------------------------------------------------------------------
# PROMOTIONS (bonus)
# ---------------------------------------------------------------------
def create_promotion(db, code, discount_percent, valid_from, valid_until):
    """
    Stores a promotion. Raises ValueError for bad input; returns None if the code
    already exists.
    """
    code = str(code).strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,20}", code):
        raise ValueError("Code must be 3-20 letters, numbers, dashes or underscores.")
    if isinstance(discount_percent, bool) or not isinstance(discount_percent, (int, float)) \
            or not 0 < discount_percent <= 100:
        raise ValueError("Discount must be a number greater than 0 and at most 100.")
    if not isinstance(valid_from, datetime) or not isinstance(valid_until, datetime):
        raise ValueError("Start and end dates are required.")
    start, end = to_naive_utc(valid_from), to_naive_utc(valid_until)
    if end <= start:
        raise ValueError("The end date must be after the start date.")
    doc = {"promotionId": f"promo_{uuid.uuid4().hex[:8]}", "code": code,
           "discountPercent": float(discount_percent), "validFrom": start, "validUntil": end}
    try:
        db["promotions"].insert_one(doc)
    except DuplicateKeyError:
        return None
    return format_promotion(doc)


def get_promo_subscribers(db):
    """Active users who opted in to promotions. The only people a promo email may go to."""
    users = db["users"].find({"promoOptIn": True, "status": "Active"},
                             {"_id": 0, "email": 1, "firstName": 1})
    return [{"email": u["email"], "first_name": u.get("firstName", "")} for u in users]
