"""Sprint 3 User & Booking APIs.

Implements showtime inspection, seat map retrieval, seat holding, pricing,
hold transfer upon login, and the login-guarded checkout order summary.
"""
from flask import Blueprint, current_app, jsonify, request

from account_security import read_authenticated_user
from models import (
    get_pricing, get_seat_map, get_showtime,
    hold_seats, release_holds, transfer_holds,
)


def make_booking_blueprint(db):
    bp = Blueprint("booking_api", __name__, url_prefix="/api")

    @bp.get("/pricing")
    def pricing():
        """Retrieve ticket pricing by category, booking fee, and sales tax rate."""
        try:
            return jsonify(get_pricing(db)), 200
        except Exception:
            current_app.logger.exception("Unable to load pricing")
            return jsonify({"error": "Unable to load ticket pricing."}), 500

    @bp.get("/showtimes/<showtime_id>")
    def showtime_details(showtime_id):
        """Retrieve details of a single showtime."""
        try:
            st = get_showtime(db, showtime_id)
            if not st:
                return jsonify({"error": "Showtime not found."}), 404
            return jsonify({"showtime": st}), 200
        except Exception:
            current_app.logger.exception("Unable to load showtime")
            return jsonify({"error": "Unable to load showtime details."}), 500

    @bp.get("/showtimes/<showtime_id>/seats")
    def seat_map(showtime_id):
        """Retrieve the seat layout and availability for a showtime.
        
        Seats marked 'selected' belong to holder_id (passed as a query parameter
        or resolved from the active user session). Other taken seats are 'booked'.
        """
        try:
            holder_id = request.args.get("holder_id")
            if not holder_id:
                auth_user = read_authenticated_user(db["users"])
                if auth_user:
                    holder_id = auth_user.get("userId")

            layout = get_seat_map(db, showtime_id, holder_id=holder_id)
            if layout is None:
                return jsonify({"error": "Showtime not found."}), 404
            return jsonify(layout), 200
        except Exception:
            current_app.logger.exception("Unable to load seat map")
            return jsonify({"error": "Unable to load seat map."}), 500

    @bp.post("/showtimes/<showtime_id>/hold")
    def hold_seats_endpoint(showtime_id):
        """Reserve seats for a guest or authenticated user session."""
        data = request.get_json(silent=True) or {}
        seat_ids = data.get("seat_ids")
        holder_id = data.get("holder_id")

        if not holder_id:
            auth_user = read_authenticated_user(db["users"])
            if auth_user:
                holder_id = auth_user.get("userId")

        if not holder_id:
            return jsonify({"error": "A holder_id or active user session is required."}), 400

        if not isinstance(seat_ids, list) or not seat_ids:
            return jsonify({"error": "Please select at least one seat.", "reason": "no_seats"}), 400

        try:
            res = hold_seats(db, showtime_id, holder_id, seat_ids)
            if res.get("ok"):
                return jsonify({"ok": True, "seats": res.get("seats", [])}), 200

            reason = res.get("reason")
            reason_map = {
                "seats_taken": ("One or more selected seats have already been taken.", 409),
                "too_many": ("You can select up to 8 seats per booking.", 422),
                "invalid_seat": ("One or more selected seats do not exist in this showroom.", 422),
                "showtime_started": ("This showtime has already started.", 422),
                "showtime_not_found": ("Showtime not found.", 404),
                "no_seats": ("Please select at least one seat.", 400),
            }
            msg, status_code = reason_map.get(reason, ("Unable to reserve seats.", 400))
            return jsonify({
                "error": msg,
                "reason": reason,
                "seats": res.get("seats", [])
            }), status_code
        except Exception:
            current_app.logger.exception("Unable to hold seats")
            return jsonify({"error": "Unable to reserve seats right now."}), 500

    @bp.post("/showtimes/<showtime_id>/release")
    def release_seats_endpoint(showtime_id):
        """Release held seats for this session/user."""
        data = request.get_json(silent=True) or {}
        holder_id = data.get("holder_id")
        seat_ids = data.get("seat_ids")

        if not holder_id:
            auth_user = read_authenticated_user(db["users"])
            if auth_user:
                holder_id = auth_user.get("userId")

        if not holder_id:
            return jsonify({"error": "A holder_id or active user session is required."}), 400

        try:
            count = release_holds(db, showtime_id, holder_id, seat_ids)
            return jsonify({"ok": True, "released": count}), 200
        except Exception:
            current_app.logger.exception("Unable to release holds")
            return jsonify({"error": "Unable to release holds right now."}), 500

    @bp.post("/booking/transfer-holds")
    def transfer_holds_endpoint():
        """Transfer holds created by a guest session to the authenticated user."""
        user = read_authenticated_user(db["users"])
        if user is None:
            return jsonify({"error": "Please sign in to transfer held seats."}), 401

        data = request.get_json(silent=True) or {}
        showtime_id = data.get("showtime_id")
        guest_session_id = data.get("guest_session_id")

        if not showtime_id or not guest_session_id:
            return jsonify({"error": "showtime_id and guest_session_id are required."}), 400

        try:
            count = transfer_holds(db, showtime_id, guest_session_id, user["userId"])
            return jsonify({
                "ok": True,
                "message": f"Successfully transferred {count} seat(s) to your account.",
                "transferred": count
            }), 200
        except Exception:
            current_app.logger.exception("Unable to transfer holds")
            return jsonify({"error": "Unable to transfer seat holds."}), 500

    @bp.post("/booking/summary")
    def order_summary():
        """Calculate and return checkout order summary.
        
        Requires authentication. Validates ticket counts, calculate subtotals,
        fees, taxes, and attaches user info so the user can confirm or modify email.
        """
        user = read_authenticated_user(db["users"])
        if user is None:
            return jsonify({"error": "Please log in to proceed to checkout."}), 401

        data = request.get_json(silent=True) or {}
        showtime_id = data.get("showtime_id")
        seat_ids = data.get("seat_ids") or []
        tickets = data.get("tickets") or {}

        if not showtime_id:
            return jsonify({"error": "showtime_id is required."}), 400

        if not isinstance(seat_ids, list) or not seat_ids:
            return jsonify({"error": "Please select at least one seat."}), 400

        if not isinstance(tickets, dict):
            return jsonify({"error": "Tickets breakdown must be provided."}), 400

        total_tickets = sum(int(v) for v in tickets.values() if isinstance(v, (int, float)) and v > 0)
        if total_tickets != len(seat_ids):
            return jsonify({
                "error": f"Selected seats ({len(seat_ids)}) must match the total number of tickets ({total_tickets})."
            }), 422

        try:
            st = get_showtime(db, showtime_id)
            if not st:
                return jsonify({"error": "Showtime not found."}), 404

            movie = db["movies"].find_one({"tmdb_id": st["tmdb_id"]}, {"_id": 0}) or {}
            pricing = get_pricing(db)
            prices = pricing.get("prices", {})

            breakdown = []
            subtotal = 0.0
            for category, count in tickets.items():
                count = int(count)
                if count <= 0:
                    continue
                price_per_ticket = float(prices.get(category, prices.get("Adult", 14.50)))
                cat_subtotal = round(count * price_per_ticket, 2)
                subtotal += cat_subtotal
                breakdown.append({
                    "type": category,
                    "count": count,
                    "price_per_ticket": price_per_ticket,
                    "subtotal": cat_subtotal
                })

            subtotal = round(subtotal, 2)
            booking_fee = round(float(pricing.get("booking_fee", 1.50)), 2)
            tax_rate = float(pricing.get("tax_rate", 0.07))
            sales_tax = round(subtotal * tax_rate, 2)
            grand_total = round(subtotal + booking_fee + sales_tax, 2)

            return jsonify({
                "movie": {
                    "tmdb_id": movie.get("tmdb_id"),
                    "title": movie.get("title", ""),
                    "poster_url": movie.get("poster_url", ""),
                    "rating": movie.get("rating", "NR"),
                    "runtime": movie.get("runtime", 120)
                },
                "showtime": {
                    "showtime_id": st.get("showtime_id"),
                    "showroom_id": st.get("showroom_id"),
                    "showroom_name": st.get("showroom_name", ""),
                    "start_time": st.get("start_time"),
                    "end_time": st.get("end_time")
                },
                "selected_seats": seat_ids,
                "tickets": tickets,
                "ticket_breakdown": breakdown,
                "total_before_tax": subtotal,
                "booking_fee": booking_fee,
                "sales_tax": sales_tax,
                "grand_total": grand_total,
                "user": {
                    "user_id": user.get("userId"),
                    "email": user.get("email"),
                    "first_name": user.get("firstName", ""),
                    "last_name": user.get("lastName", "")
                }
            }), 200
        except Exception:
            current_app.logger.exception("Unable to generate order summary")
            return jsonify({"error": "Unable to calculate order summary right now."}), 500

    return bp
