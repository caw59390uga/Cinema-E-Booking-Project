import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

client = MongoClient(MONGO_URI)
db = client["cinema_db"]

# Collection references
movies_collection = db["movies"]
users_collection = db["users"]
theatres_collection = db["theatres"]
shows_collection = db["shows"]
promotions_collection = db["promotions"]

GENRES = {28: "Action", 35: "Comedy", 18: "Drama", 878: "Sci-Fi", 27: "Horror", 10749: "Romance"}

def seed_database():
    print("--- Starting Database Seeding ---")

    # 1. Seed Movies from TMDB (Your existing logic)
    print("Fetching movie data from TMDB...")
    now_playing_res = requests.get(f"https://api.themoviedb.org/3/movie/now_playing?api_key={TMDB_API_KEY}").json()
    upcoming_res = requests.get(f"https://api.themoviedb.org/3/movie/upcoming?api_key={TMDB_API_KEY}").json()

    now_playing_movies = now_playing_res.get('results', [])[:6]
    upcoming_movies = upcoming_res.get('results', [])[:6]

    formatted_movies = []

    def process_movies(movie_list, status_label):
        for m in movie_list:
            m_id = m['id']
            vid_res = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}/videos?api_key={TMDB_API_KEY}").json()
            vids = vid_res.get('results', [])
            trailer_key = next((v['key'] for v in vids if v['type'] == 'Trailer' and v['site'] == 'YouTube'), None)

            genre_id = m['genre_ids'][0] if m.get('genre_ids') else 28
            genre_name = GENRES.get(genre_id, "Action")

            movie_doc = {
                "tmdb_id": m_id,
                "title": m['title'],
                "description": m['overview'],
                "poster_url": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
                "trailer_url": f"https://www.youtube.com/embed/{trailer_key}" if trailer_key else "https://www.youtube.com/embed/dQw4w9WgXcQ",
                "rating": str(m.get('vote_average', 'PG-13')),
                "genre": genre_name,
                "status": status_label,
                "showtimes": ["2:00 PM", "5:00 PM", "8:00 PM"]
            }
            formatted_movies.append(movie_doc)

    process_movies(now_playing_movies, "Currently Running")
    process_movies(upcoming_movies, "Coming Soon")

    movies_collection.delete_many({})
    if formatted_movies:
        movies_collection.insert_many(formatted_movies)
        print(f"Successfully seeded {len(formatted_movies)} movies!")

    # 2. Seed Initial Users (Customers & Admins)
    users_collection.delete_many({})
    initial_users = [
        {
            "userId": "usr_cust_101",
            "userType": "Customer",
            "firstName": "Alex",
            "lastName": "Rivera",
            "email": "alex.rivera@example.com",
            "passwordHash": "$2b$10$e8u...hashedpass",
            "state": "Active",
            "mailingAddress": {
                "street": "123 College Ave", "city": "Athens", "state": "GA", "postalCode": "30601", "country": "USA"
            },
            "savedCards": [
                {
                    "cardId": "card_9901",
                    "encryptedCardNumber": "enc_4111222233334444",
                    "expirationDate": datetime(2028, 12, 1, tzinfo=timezone.utc)
                }
            ]
        },
        {
            "userId": "usr_admin_001",
            "userType": "Admin",
            "firstName": "Jordan",
            "lastName": "Lee",
            "email": "admin.jordan@cinema.com",
            "passwordHash": "$2b$10$x9k...hashedpass"
        }
    ]
    users_collection.insert_many(initial_users)
    print("Successfully seeded initial users!")

    # seed theatres and showrooms with seat layouts
    theatres_collection.delete_many({})
    initial_theatre = {
        "theatreId": "th_lux_cinema",
        "name": "Grand Luxe Cinema",
        "showrooms": [
            {
                "showroomId": "room_01",
                "name": "Screen 1 - IMAX",
                "seatCount": 4,
                "seats": [
                    { "seatId": "st_A1", "row": "A", "number": 1 },
                    { "seatId": "st_A2", "row": "A", "number": 2 },
                    { "seatId": "st_B1", "row": "B", "number": 1 },
                    { "seatId": "st_B2", "row": "B", "number": 2 }
                ]
            }
        ]
    }
    theatres_collection.insert_one(initial_theatre)
    print("Successfully seeded theatre and showroom layouts!")

    # seed Promotions
    promotions_collection.delete_many({})
    initial_promos = [
        {
            "promotionId": "promo_fall26",
            "code": "FALL20",
            "discountPercent": 20.0,
            "validFrom": datetime(2026, 10, 1, tzinfo=timezone.utc),
            "validUntil": datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
        }
    ]
    promotions_collection.insert_many(initial_promos)
    print("Successfully seeded promotions!")
    print("--- Database Seeding Complete ---")

if __name__ == '__main__':
    seed_database()