def format_movie(movie):
    """Formats a MongoDB document into clean JSON for the frontend."""
    return {
        "tmdb_id": movie.get("tmdb_id"),
        "title": movie.get("title", ""),
        "description": movie.get("description", ""),
        "poster_url": movie.get("poster_url", ""),
        "trailer_url": movie.get("trailer_url", ""),
        "rating": movie.get("rating", "N/A"),
        "genre": movie.get("genre", "Unspecified"),
        "status": movie.get("status", "Currently Running"),
        "showtimes": movie.get("showtimes", [])
    }