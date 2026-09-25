import os
import certifi
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from models import format_movie

load_dotenv()

app = Flask(__name__)
CORS(app)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["cinema_db"]
movies_collection = db["movies"]

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
