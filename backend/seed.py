"""
seed.py - wipes and reseeds cinema_db into a demo-ready state.
Run before every demo:   python seed.py

WARNING: this deletes ALL users (including any created during a previous demo,
such as eman@gmail.my from TC1), which is exactly what you want before a demo.
"""
import os
import certifi
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

from models import new_user_doc, build_card, ensure_indexes

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["cinema_db"]

movies_collection = db["movies"]
users_collection = db["users"]
tokens_collection = db["tokens"]
theatres_collection = db["theatres"]
shows_collection = db["shows"]
promotions_collection = db["promotions"]

GENRES = {28: "Action", 35: "Comedy", 18: "Drama", 878: "Sci-Fi", 27: "Horror", 10749: "Romance"}

# ---------------- DEMO CREDENTIALS (copy these into your README) ----------------
ADMIN_EMAIL, ADMIN_PW = "admin@cinema.com", "Admin!2026"
ALEX_EMAIL, ALEX_PW = "alex.rivera@example.com", "Customer!2026"   # has favorite + address; use for TC5 wrong password
CASEY_EMAIL, CASEY_PW = "casey.morgan@example.com", "Cards!2026"   # has exactly 3 payment cards
# eman@gmail.my is NOT seeded - TC1 creates it live.


def get_us_certification(tmdb_id):
    """Returns the MPAA rating (G, PG, PG-13, R, ...) from TMDB, or 'NR' if unavailable."""
    try:
        res = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}/release_dates?api_key={TMDB_API_KEY}",
            timeout=10).json()
        for country in res.get("results", []):
            if country.get("iso_3166_1") == "US":
                for rd in country.get("release_dates", []):
                    if rd.get("certification"):
                        return rd["certification"]
    except requests.RequestException:
        pass
    return "NR"


def seed_movies():
    print("Fetching movie data from TMDB...")
    base = "https://api.themoviedb.org/3/movie"
    now_playing = requests.get(f"{base}/now_playing?api_key={TMDB_API_KEY}", timeout=10).json().get("results", [])[:6]
    upcoming = requests.get(f"{base}/upcoming?api_key={TMDB_API_KEY}", timeout=10).json().get("results", [])[:6]

    formatted = []

    def process(movie_list, status_label):
        for m in movie_list:
            m_id = m["id"]
            vids = requests.get(f"{base}/{m_id}/videos?api_key={TMDB_API_KEY}", timeout=10).json().get("results", [])
            trailer_key = next((v["key"] for v in vids if v["type"] == "Trailer" and v["site"] == "YouTube"), None)

            genre_id = m["genre_ids"][0] if m.get("genre_ids") else 28
            poster = m.get("poster_path")

            formatted.append({
                "tmdb_id": m_id,
                "title": m["title"],
                "description": m.get("overview", ""),
                "poster_url": f"https://image.tmdb.org/t/p/w500{poster}" if poster else "",
                "trailer_url": f"https://www.youtube.com/embed/{trailer_key}" if trailer_key
                               else "https://www.youtube.com/embed/dQw4w9WgXcQ",
                "rating": get_us_certification(m_id),          # MPAA code, per the spec
                "genre": GENRES.get(genre_id, "Action"),
                "status": status_label,
                "showtimes": ["2:00 PM", "5:00 PM", "8:00 PM"]
            })

    process(now_playing, "Currently Running")
    process(upcoming, "Coming Soon")

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


def seed_theatre():
    theatres_collection.delete_many({})
    theatres_collection.insert_one({
        "theatreId": "th_lux_cinema",
        "name": "Grand Luxe Cinema",
        "showrooms": [
            {
                "showroomId": "room_01",
                "name": "Screen 1 - IMAX",
                "seatCount": 4,
                "seats": [
                    {"seatId": "st_A1", "row": "A", "number": 1},
                    {"seatId": "st_A2", "row": "A", "number": 2},
                    {"seatId": "st_B1", "row": "B", "number": 1},
                    {"seatId": "st_B2", "row": "B", "number": 2}
                ]
            }
        ]
    })
    print("Successfully seeded theatre and showroom layouts!")


def seed_promotions():
    promotions_collection.delete_many({})
    promotions_collection.insert_one({
        "promotionId": "promo_fall26",
        "code": "FALL20",
        "discountPercent": 20.0,
        "validFrom": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "validUntil": datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    })
    print("Successfully seeded promotions!")


def seed_database():
    print("--- Starting Database Seeding ---")
    users_collection.delete_many({})       # clear first so the unique index builds cleanly
    ensure_indexes(db)
    movies = seed_movies()
    seed_users(movies)
    seed_theatre()
    seed_promotions()
    print("--- Database Seeding Complete ---")
    print(f"Admin:  {ADMIN_EMAIL} / {ADMIN_PW}")
    print(f"Alex:   {ALEX_EMAIL} / {ALEX_PW}   (favorites, address, 1 card)")
    print(f"Casey:  {CASEY_EMAIL} / {CASEY_PW}   (3 cards)")


if __name__ == "__main__":
    seed_database()