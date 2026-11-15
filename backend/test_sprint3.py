"""Automated Sprint 3 Test Suite.

Verifies:
1. Admin Add Movie & Validation
2. Admin Showrooms & Conflict-aware Showtime Scheduling (409 on overlap)
3. Showtime visibility attached to movies
4. Pricing endpoint
5. Seat map layout & booking holds
6. Concurrency / seat collision handling
7. Hold transfer on login
8. Order summary calculations & authentication guard
"""
import json
import unittest
from datetime import datetime, timezone, timedelta

from app import app, db
from models import utcnow


class Sprint3BackendTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # Log in as admin
        res = self.client.post("/api/auth/login", json={
            "email": "admin@cinema.com",
            "password": "Admin!2026"
        })
        self.assertEqual(res.status_code, 200, "Admin login must succeed")
        self.admin_token = res.get_json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        # Log in as normal user (Alex)
        res_alex = self.client.post("/api/auth/login", json={
            "email": "alex.rivera@example.com",
            "password": "Customer!2026"
        })
        self.assertEqual(res_alex.status_code, 200, "Alex login must succeed")
        self.alex_token = res_alex.get_json()["access_token"]
        self.alex_headers = {"Authorization": f"Bearer {self.alex_token}"}
        self.alex_user = res_alex.get_json()["user"]

    def test_01_admin_list_showrooms(self):
        """Admin can list all showrooms."""
        res = self.client.get("/api/admin/showrooms", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("showrooms", data)
        self.assertGreaterEqual(len(data["showrooms"]), 3)

    def test_02_showtimes_attached_to_movies(self):
        """User portal: movies include attached showtimes."""
        res = self.client.get("/api/movies")
        self.assertEqual(res.status_code, 200)
        movies = res.get_json()
        self.assertGreater(len(movies), 0)
        
        # Check running movies have showtime objects
        running = [m for m in movies if m.get("status") == "Currently Running"]
        self.assertGreater(len(running), 0)
        first_movie = running[0]
        self.assertIn("showtimes", first_movie)
        self.assertIsInstance(first_movie["showtimes"], list)
        if first_movie["showtimes"]:
            st = first_movie["showtimes"][0]
            self.assertIn("showtime_id", st)
            self.assertIn("start_time", st)
            self.assertIn("showroom_name", st)

    def test_03_pricing_endpoint(self):
        """Pricing endpoint returns prices, booking fee, and tax rate."""
        res = self.client.get("/api/pricing")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("prices", data)
        self.assertIn("Adult", data["prices"])
        self.assertIn("Child", data["prices"])
        self.assertIn("Senior", data["prices"])
        self.assertIn("booking_fee", data)
        self.assertIn("tax_rate", data)

    def test_04_seat_map_and_booking_holds(self):
        """User can view seat map and hold seats."""
        # Find an upcoming showtime
        res_movies = self.client.get("/api/movies")
        movies = res_movies.get_json()
        st_id = None
        for m in movies:
            if m.get("showtimes"):
                st_id = m["showtimes"][0]["showtime_id"]
                break
        self.assertIsNotNone(st_id, "Must have at least one seeded showtime")

        # Get seat map as guest
        guest_holder = "guest_test_session_1"
        res_map = self.client.get(f"/api/showtimes/{st_id}/seats?holder_id={guest_holder}")
        self.assertEqual(res_map.status_code, 200)
        map_data = res_map.get_json()
        self.assertIn("seats", map_data)
        self.assertIn("showtime", map_data)
        self.assertIn("showroom", map_data)

        # Pick two available seats
        available_seats = [s["seat_id"] for s in map_data["seats"] if s["status"] == "available"]
        self.assertGreaterEqual(len(available_seats), 2)
        chosen_seats = available_seats[:2]

        # Hold seats
        res_hold = self.client.post(f"/api/showtimes/{st_id}/hold", json={
            "holder_id": guest_holder,
            "seat_ids": chosen_seats
        })
        self.assertEqual(res_hold.status_code, 200)
        self.assertTrue(res_hold.get_json().get("ok"))

        # Re-fetch seat map: chosen seats should now be 'selected' for guest_holder
        res_map2 = self.client.get(f"/api/showtimes/{st_id}/seats?holder_id={guest_holder}")
        seats_by_id = {s["seat_id"]: s["status"] for s in res_map2.get_json()["seats"]}
        for s in chosen_seats:
            self.assertEqual(seats_by_id[s], "selected")

        # Concurrency check: another guest trying to take the same seats gets 409
        res_conflict = self.client.post(f"/api/showtimes/{st_id}/hold", json={
            "holder_id": "guest_test_session_2",
            "seat_ids": chosen_seats
        })
        self.assertEqual(res_conflict.status_code, 409)
        self.assertEqual(res_conflict.get_json().get("reason"), "seats_taken")

        # Transfer holds to Alex
        res_transfer = self.client.post("/api/booking/transfer-holds", headers=self.alex_headers, json={
            "showtime_id": st_id,
            "guest_session_id": guest_holder
        })
        self.assertEqual(res_transfer.status_code, 200)
        self.assertEqual(res_transfer.get_json().get("transferred"), 2)

        # Release holds
        res_release = self.client.post(f"/api/showtimes/{st_id}/release", headers=self.alex_headers, json={
            "seat_ids": chosen_seats
        })
        self.assertEqual(res_release.status_code, 200)

    def test_05_checkout_order_summary(self):
        """Order summary requires login and calculates pricing correctly."""
        res_movies = self.client.get("/api/movies")
        movies = res_movies.get_json()
        st_id = movies[0]["showtimes"][0]["showtime_id"]

        payload = {
            "showtime_id": st_id,
            "seat_ids": ["B1", "B2"],
            "tickets": {"Adult": 1, "Child": 1}
        }

        # Anonymous request fails with 401
        res_anon = self.client.post("/api/booking/summary", json=payload)
        self.assertEqual(res_anon.status_code, 401)

        # Logged-in request succeeds with 200
        res_auth = self.client.post("/api/booking/summary", headers=self.alex_headers, json=payload)
        self.assertEqual(res_auth.status_code, 200)
        data = res_auth.get_json()
        self.assertIn("movie", data)
        self.assertIn("showtime", data)
        self.assertIn("ticket_breakdown", data)
        self.assertIn("total_before_tax", data)
        self.assertIn("grand_total", data)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], "alex.rivera@example.com")
        self.assertGreater(data["grand_total"], data["total_before_tax"])

        # Mismatched seat count vs ticket count returns 422
        bad_payload = {
            "showtime_id": st_id,
            "seat_ids": ["B1"],
            "tickets": {"Adult": 2}
        }
        res_mismatch = self.client.post("/api/booking/summary", headers=self.alex_headers, json=bad_payload)
        self.assertEqual(res_mismatch.status_code, 422)

    def test_06_admin_showtime_conflict_detection(self):
        """Scheduling a showtime in an occupied screen/time returns 409 Conflict."""
        # Query an existing showtime to get movie, screen, and time
        res_movies = self.client.get("/api/movies")
        movie = res_movies.get_json()[0]
        st = movie["showtimes"][0]

        # Attempt to schedule overlapping showtime in the same screen
        conflict_payload = {
            "movie_id": movie["tmdb_id"],
            "showroom_id": st["showroom_id"],
            "start_time": st["start_time"]
        }
        res = self.client.post("/api/admin/showtimes", headers=self.admin_headers, json=conflict_payload)
        self.assertEqual(res.status_code, 409, "Must return 409 Conflict for overlapping showtime")
        data = res.get_json()
        self.assertEqual(data.get("code"), "conflict")

    def test_07_admin_add_movie_validation_and_creation(self):
        """Admin can add a movie; invalid data returns 422."""
        # Test validation failure on empty title / fields
        res_bad = self.client.post("/api/admin/movies", headers=self.admin_headers, json={
            "title": "",
            "genre": "InvalidGenre",
            "rating": "NOT_A_RATING",
            "runtime": 5
        })
        self.assertEqual(res_bad.status_code, 422)
        errors = res_bad.get_json().get("errors", {})
        self.assertIn("title", errors)
        self.assertIn("genre", errors)
        self.assertIn("rating", errors)
        self.assertIn("runtime", errors)

        # Test successful movie creation
        unique_title = f"Sprint 3 Demo Movie {int(datetime.now().timestamp())}"
        movie_payload = {
            "title": unique_title,
            "genre": "Action",
            "rating": "PG-13",
            "status": "Currently Running",
            "runtime": 125,
            "director": "Demo Director",
            "producer": "Demo Producer",
            "cast": ["Actor A", "Actor B"],
            "description": "An exciting action movie created for Sprint 3 demo testing.",
            "poster_url": "https://image.tmdb.org/t/p/w500/demo_poster.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        }
        res_good = self.client.post("/api/admin/movies", headers=self.admin_headers, json=movie_payload)
        self.assertEqual(res_good.status_code, 201)
        created_movie = res_good.get_json().get("movie")
        self.assertEqual(created_movie["title"], unique_title)
        self.assertIn("tmdb_id", created_movie)


if __name__ == "__main__":
    unittest.main()
