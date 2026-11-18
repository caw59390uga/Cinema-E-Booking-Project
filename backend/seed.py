"""
seed.py - wipes and reseeds cinema_db into a demo-ready state.
Run before every demo:   python seed.py

WARNING: this deletes ALL users, movies, showtimes and bookings, including anything
created during a previous demo (such as eman@gmail.my from TC1 or movies added by the
admin), which is exactly what you want before a demo.
"""
import os
import certifi
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import date, datetime, timedelta, timezone

from models import (
    new_user_doc, build_card, ensure_indexes, build_showroom, create_showtime,
    DEFAULT_RUNTIME_MINUTES, DEFAULT_PRICING
)

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["cinema_db"]

movies_collection = db["movies"]
users_collection = db["users"]
tokens_collection = db["tokens"]
showrooms_collection = db["showrooms"]
showtimes_collection = db["showtimes"]
bookings_collection = db["bookings"]
promotions_collection = db["promotions"]
settings_collection = db["settings"]
counters_collection = db["counters"]

GENRES = {28: "Action", 35: "Comedy", 18: "Drama", 878: "Sci-Fi", 27: "Horror", 10749: "Romance"}

# ---------------- DEMO CREDENTIALS (copy these into your README) ----------------
ADMIN_EMAIL, ADMIN_PW = "admin@cinema.com", "Admin!2026"
ALEX_EMAIL, ALEX_PW = "alex.rivera@example.com", "Customer!2026"   # has favorites + address
CASEY_EMAIL, CASEY_PW = "casey.morgan@example.com", "Cards!2026"   # has exactly 3 payment cards
# eman@gmail.my is NOT seeded - TC1 creates it live.

# ---------------- SHOWROOMS (at least 3, different sizes) ----------------
SHOWROOMS = [
    build_showroom("room_01", "Screen 1 - IMAX", "ABCDEF", 10),       # 60 seats
    build_showroom("room_02", "Screen 2 - Dolby", "ABCDE", 8),         # 40 seats
    build_showroom("room_03", "Screen 3 - Standard", "ABCDEFGH", 12),  # 96 seats
]

# Daily start times (local time). Spaced 3.5 hours apart so movies up to ~3h15m fit.
SLOTS = [(11, 0), (14, 30), (18, 0), (21, 30)]
DAYS_OF_SHOWTIMES = 7          # today + the next 6 days


def get_us_certification(release_dates):
    """MPAA rating (G, PG, PG-13, R, ...) from TMDB's release_dates block, or 'NR'."""
    for country in (release_dates or {}).get("results", []):
        if country.get("iso_3166_1") == "US":
            for rd in country.get("release_dates", []):
                if rd.get("certification"):
                    return rd["certification"]
    return "NR"


def build_movie_doc(listing, details, status_label):
    """
    Builds one movie document from TMDB's list entry plus its details response
    (details was requested with credits, reviews, videos and release_dates attached).
    """
    details = details or {}
    videos = (details.get("videos") or {}).get("results", [])
    trailer_key = next((v["key"] for v in videos
                        if v.get("type") == "Trailer" and v.get("site") == "YouTube"), None)
    credits = details.get("credits") or {}
    crew = credits.get("crew", [])
    directors = [c["name"] for c in crew if c.get("job") == "Director" and c.get("name")]
    producers = [c["name"] for c in crew if c.get("job") == "Producer" and c.get("name")]
    cast = [c["name"] for c in credits.get("cast", [])[:6] if c.get("name")]
    reviews = [{"author": r.get("author", ""), "content": (r.get("content") or "")[:500]}
               for r in (details.get("reviews") or {}).get("results", [])[:3]
               if (r.get("content") or "").strip()]
    genre_id = listing["genre_ids"][0] if listing.get("genre_ids") else 28
    poster = listing.get("poster_path")
    runtime = details.get("runtime")

    return {
        "tmdb_id": listing["id"],
        "title": listing["title"],
        "description": listing.get("overview", ""),
        "poster_url": f"https://image.tmdb.org/t/p/w500{poster}" if poster else "",
        "trailer_url": f"https://www.youtube.com/embed/{trailer_key}" if trailer_key
                       else "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "rating": get_us_certification(details.get("release_dates")),
        "genre": GENRES.get(genre_id, "Action"),
        "status": status_label,
        "runtime": runtime if isinstance(runtime, int) and runtime > 0 else DEFAULT_RUNTIME_MINUTES,
        "cast": cast,
        "director": directors[0] if directors else "Unknown",
        "producer": ", ".join(producers[:2]) if producers else "Unknown",
        "reviews": reviews,
    }


def fetch_details(base, movie_id):
    """One TMDB call for everything. Returns {} if it fails, so seeding never stops."""
    try:
        res = requests.get(
            f"{base}/{movie_id}",
            params={"api_key": TMDB_API_KEY,
                    "append_to_response": "credits,reviews,videos,release_dates"},
            timeout=10)
        res.raise_for_status()
        return res.json()
    except (requests.RequestException, ValueError):
        print(f"  (could not load details for movie {movie_id}; using defaults)")
        return {}


def seed_movies():
    print("Fetching movie data from TMDB...")
    base = "https://api.themoviedb.org/3/movie"
    now_playing = requests.get(f"{base}/now_playing", params={"api_key": TMDB_API_KEY},
                               timeout=10).json().get("results", [])[:6]
    upcoming = requests.get(f"{base}/upcoming", params={"api_key": TMDB_API_KEY},
                            timeout=10).json().get("results", [])[:6]

    formatted, seen = [], set()
    # now playing first, so a movie listed in both lists stays "Currently Running"
    for listing_list, status_label in ((now_playing, "Currently Running"), (upcoming, "Coming Soon")):
        for listing in listing_list:
            if listing["id"] in seen:
                continue
            seen.add(listing["id"])
            formatted.append(build_movie_doc(listing, fetch_details(base, listing["id"]), status_label))

    movies_collection.delete_many({})
    if formatted:
        movies_collection.insert_many(formatted)
        print(f"Successfully seeded {len(formatted)} movies!")
    return formatted


def seed_users(movies):
    users_collection.delete_many({})
    tokens_collection.delete_many({})

    favorite_ids = [m["tmdb_id"] for m in movies[:2]]   # Alex favorites the first two movies

    # --- Admin ---
    admin = new_user_doc("Jordan", "Lee", ADMIN_EMAIL, "706-555-0100", ADMIN_PW,
                         promo_opt_in=False, user_type="Admin", status="Active")

    # --- Alex: verified, address, favorites, 1 card ---
    alex = new_user_doc("Alex", "Rivera", ALEX_EMAIL, "706-555-0101", ALEX_PW,
                        promo_opt_in=True, status="Active")
    alex["address"] = {"street": "123 College Ave", "city": "Athens", "state": "GA",
                       "postalCode": "30601", "country": "USA"}
    alex["favorites"] = favorite_ids
    alex["savedCards"] = [build_card("4111111111111111", "Visa", "12/28")]

    # --- Casey: verified, EXACTLY 3 cards (for TC7 - 4th card must be rejected) ---
    casey = new_user_doc("Casey", "Morgan", CASEY_EMAIL, "706-555-0102", CASEY_PW,
                         promo_opt_in=True, status="Active")
    casey["address"] = {"street": "456 Broad St", "city": "Athens", "state": "GA",
                        "postalCode": "30601", "country": "USA"}
    casey["savedCards"] = [
        build_card("4242424242424242", "Visa", "11/27"),
        build_card("5555555555554444", "Mastercard", "08/28"),
        build_card("378282246310005", "Amex", "03/29"),
    ]

    users_collection.insert_many([admin, alex, casey])
    print("Successfully seeded users (admin, alex, casey)!")


def seed_showrooms():
    showrooms_collection.delete_many({})
    showrooms_collection.insert_many([dict(room) for room in SHOWROOMS])
    print("Successfully seeded 3 showrooms: " +
          ", ".join(f"{r['name']} ({r['seatCount']} seats)" for r in SHOWROOMS))


def local_to_utc(day, hour, minute):
    """A local wall-clock time on `day` as naive UTC (uses this computer's time zone)."""
    return datetime(day.year, day.month, day.day, hour, minute).astimezone(timezone.utc).replace(tzinfo=None)


def seed_showtimes(movies):
    """Every Currently Running movie gets showings in all 3 rooms for the next week."""
    showtimes_collection.delete_many({})
    running = [m for m in movies if m["status"] == "Currently Running"]
    if not running:
        print("No Currently Running movies, so no showtimes were created.")
        return
    created = skipped = 0
    today = date.today()
    # Hand out the running movies in rotation so every one of them gets showtimes
    # (3 rooms x 4 slots x 7 days = 84 showings, enough for up to 84 movies).
    next_movie = 0
    for d in range(DAYS_OF_SHOWTIMES):
        day = today + timedelta(days=d)
        for s, (hour, minute) in enumerate(SLOTS):
            for r, room in enumerate(SHOWROOMS):
                movie = running[next_movie % len(running)]
                next_movie += 1
                _, error = create_showtime(db, movie["tmdb_id"], room["showroomId"],
                                           local_to_utc(day, hour, minute))
                if error:
                    skipped += 1
                else:
                    created += 1
    print(f"Successfully seeded {created} showtimes ({skipped} skipped for conflicts)!")


def seed_bookings():
    """Some seats already taken on tomorrow's first Screen 1 showing, so the seat map has booked seats."""
    bookings_collection.delete_many({})
    tomorrow = date.today() + timedelta(days=1)
    show = showtimes_collection.find_one(
        {"showroomId": "room_01", "startTime": {"$gte": local_to_utc(tomorrow, 0, 0)}},
        sort=[("startTime", 1)])
    if not show:
        return None
    taken = ["A1", "A2", "A3", "A4", "C5", "C6", "D5", "D6"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bookings_collection.insert_many([
        {"showtimeId": show["showtimeId"], "seatId": seat, "holderId": "usr_seed_booked",
         "status": "booked", "orderId": "ord_seed_001", "createdAt": now}
        for seat in taken])
    print(f"Successfully seeded {len(taken)} booked seats on a Screen 1 showing!")
    return show


def seed_pricing():
    settings_collection.delete_many({})
    settings_collection.insert_one({"settingsId": "pricing", **DEFAULT_PRICING})
    print("Successfully seeded ticket prices and booking fee!")


def seed_promotions():
    promotions_collection.delete_many({})
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    promotions_collection.insert_one({
        "promotionId": "promo_save20",
        "code": "SAVE20",
        "discountPercent": 20.0,
        "validFrom": now,
        "validUntil": now + timedelta(days=30)
    })
    print("Successfully seeded promotions!")


def seed_database():
    print("--- Starting Database Seeding ---")
    # clear first so the unique indexes build cleanly
    for name in ("users", "movies", "showrooms", "showtimes", "bookings",
                 "promotions", "settings", "counters", "tokens"):
        db[name].delete_many({})
    # collections from the earlier sprints that nothing uses any more
    db.drop_collection("theatres")
    db.drop_collection("shows")
    ensure_indexes(db)

    movies = seed_movies()
    seed_users(movies)
    seed_showrooms()
    seed_showtimes(movies)
    booked_show = seed_bookings()
    seed_pricing()
    seed_promotions()

    tomorrow = date.today() + timedelta(days=1)
    free_day = date.today() + timedelta(days=DAYS_OF_SHOWTIMES + 1)
    print("--- Database Seeding Complete ---")
    print(f"Admin:  {ADMIN_EMAIL} / {ADMIN_PW}")
    print(f"Alex:   {ALEX_EMAIL} / {ALEX_PW}   (favorites, address, 1 card)")
    print(f"Casey:  {CASEY_EMAIL} / {CASEY_PW}   (3 cards)")
    print("--- Sprint 3 demo hints ---")
    print(f"Conflict test: add any movie to Screen 1 on {tomorrow:%b %d} at 11:00 AM -> must be rejected")
    print(f"Success test:  add any movie to any screen on {free_day:%b %d} at 7:00 PM -> must work")
    if booked_show:
        print("Seat map test: tomorrow's first Screen 1 showing has A1-A4, C5-C6, D5-D6 already booked")


if __name__ == "__main__":
    seed_database()
