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

def format_user(user):
    return {
        "user_id": user.get("userId"),
        "user_type": user.get("userType", "Customer"),
        "first_name": user.get("firstName", ""),
        "last_name": user.get("lastName", ""),
        "email": user.get("email", ""),
        "state": user.get("state", "Active"),
        "mailing_address": user.get("mailingAddress", {}),
        "saved_cards": user.get("savedCards", [])
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