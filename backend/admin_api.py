"""Sprint 3 administrator APIs for movie creation and non-overlapping showtimes.

These endpoints delegate validation, movie storage, and conflict detection to the
existing Sprint 3 model functions. The client cannot bypass the admin guard.
"""
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from pymongo.errors import DuplicateKeyError

from account_security import read_authenticated_user
from models import (
    MOVIE_GENRES, MPAA_RATINGS, MOVIE_STATUSES,
    create_movie, create_showtime, format_movie, format_showroom,
    list_available_showrooms, list_showrooms,
)


def _start_from_iso(raw):
    """Return (UTC datetime, error) for a future, offset-aware ISO timestamp."""
    if not isinstance(raw, str) or len(raw) > 64:
        return None, "Choose a valid date and time."
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None, "Choose a valid date and time."
    if moment.tzinfo is None or moment.utcoffset() is None:
        return None, "Date and time must include a timezone."
    moment = moment.astimezone(timezone.utc)
    if moment <= datetime.now(timezone.utc):
        return None, "Showtime must be in the future."
    return moment, None


def _movie_id(value):
    try:
        if isinstance(value, bool) or str(value).strip() != str(int(value)):
            return None
        result = int(value)
        return result if result > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def make_admin_blueprint(db):
    bp = Blueprint("admin_movies", __name__, url_prefix="/api/admin")

    @bp.before_request
    def require_admin():
        if request.method == "OPTIONS":
            return None
        current_user = read_authenticated_user(db["users"])
        if current_user is None:
            return jsonify({"error": "Please sign in as an administrator."}), 401
        if current_user.get("userType") != "Admin":
            return jsonify({"error": "Administrator permissions required."}), 403
        return None

    @bp.get("/catalog")
    def catalog():
        try:
            records = db["movies"].find({}, {"_id": 0}).sort("title", 1)
            return jsonify({
                "movies": [format_movie(movie) for movie in records],
                "genres": list(MOVIE_GENRES),
                "ratings": list(MPAA_RATINGS),
                "statuses": list(MOVIE_STATUSES),
            }), 200
        except Exception:
            current_app.logger.exception("Unable to load admin movie catalog")
            return jsonify({"error": "Unable to load movies right now."}), 500

    @bp.post("/movies")
    def add_movie():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Movie details must be a JSON object."}), 400
        try:
            movie, errors = create_movie(db, data)
            if errors:
                status = 409 if "title" in errors and "already exists" in errors["title"] else 422
                return jsonify({"error": "Please correct the highlighted fields.", "errors": errors}), status
            return jsonify({"message": "Movie added successfully.", "movie": movie}), 201
        except DuplicateKeyError:
            return jsonify({"error": "A movie with this title or ID already exists.",
                            "errors": {"title": "A matching movie is already in the catalog."}}), 409
        except Exception:
            current_app.logger.exception("Unable to create movie")
            return jsonify({"error": "Unable to add the movie right now."}), 500

    @bp.get("/showrooms")
    def all_showrooms():
        try:
            rooms = list_showrooms(db)
            return jsonify({"showrooms": [format_showroom(r) for r in rooms]}), 200
        except Exception:
            current_app.logger.exception("Unable to load showrooms")
            return jsonify({"error": "Unable to load showrooms right now."}), 500

    @bp.get("/showrooms/availability")
    def available_showrooms():
        movie_id = _movie_id(request.args.get("movie_id"))
        start, time_error = _start_from_iso(request.args.get("start_time"))
        errors = {}
        if movie_id is None:
            errors["movie_id"] = "Select a movie."
        if time_error:
            errors["start_time"] = time_error
        if errors:
            return jsonify({"error": "Select a movie and valid future time.", "errors": errors}), 422
        try:
            movie = db["movies"].find_one({"tmdb_id": movie_id}, {"_id": 0})
            if movie is None:
                return jsonify({"error": "Movie not found.", "errors": {"movie_id": "Movie not found."}}), 404
            rooms = list_available_showrooms(db, movie_id, start)
            return jsonify({"showrooms": rooms}), 200
        except Exception:
            current_app.logger.exception("Unable to check available showrooms")
            return jsonify({"error": "Unable to check room availability."}), 500

    @bp.post("/showtimes")
    def add_showtime():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Showtime details must be a JSON object."}), 400
        movie_id = _movie_id(data.get("movie_id"))
        showroom_id = data.get("showroom_id")
        start, time_error = _start_from_iso(data.get("start_time"))
        errors = {}
        if movie_id is None:
            errors["movie_id"] = "Select a movie."
        if not isinstance(showroom_id, str) or not showroom_id.strip() or len(showroom_id) > 120:
            errors["showroom_id"] = "Choose an available screen."
        if time_error:
            errors["start_time"] = time_error
        if errors:
            return jsonify({"error": "Please correct the highlighted fields.", "errors": errors}), 422
        try:
            showing, conflict = create_showtime(db, movie_id, showroom_id, start)
            if conflict:
                code = conflict.get("code", "invalid_time")
                field = {"movie_not_found": "movie_id", "showroom_not_found": "showroom_id",
                         "invalid_time": "start_time", "conflict": "showroom_id"}.get(code, "showroom_id")
                return jsonify({
                    "error": conflict.get("message", "Unable to schedule the movie."),
                    "code": code, "errors": {field: conflict.get("message", "Unavailable.")},
                    "conflict": conflict.get("conflict"),
                }), 409 if code == "conflict" else 422
            return jsonify({"message": "Showtime scheduled successfully.", "showtime": showing}), 201
        except DuplicateKeyError:
            return jsonify({"error": "This screen already has a showtime at that time.",
                            "code": "conflict", "errors": {"showroom_id": "Screen is already booked."}}), 409
        except Exception:
            current_app.logger.exception("Unable to schedule movie")
            return jsonify({"error": "Unable to schedule this movie right now."}), 500

    return bp
