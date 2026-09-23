import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

client = MongoClient(MONGO_URI)
db = client["cinema_db"]
movies_collection = db["movies"]

GENRES = {28: "Action", 35: "Comedy", 18: "Drama", 878: "Sci-Fi", 27: "Horror", 10749: "Romance"}

def fetch_and_seed():
    print("Fetching movie data from TMDb...")
    
    # fetch Now Playing and Upcoming movies from TMDb
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

    # clear collection and insert newly seeded movies
    movies_collection.delete_many({})
    if formatted_movies:
        movies_collection.insert_many(formatted_movies)
        print(f"Successfully seeded database with {len(formatted_movies)} movies!")

if __name__ == "__main__":
    fetch_and_seed()