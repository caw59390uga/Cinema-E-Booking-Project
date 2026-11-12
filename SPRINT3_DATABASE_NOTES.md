# Sprint 3 - Database notes

Run `python seed.py` before every demo. It rebuilds everything (users, movies, showrooms,
showtimes, bookings, prices, promo) and prints the demo logins and test hints.

## What changed for everyone
- `movie.showtimes` is now a list of objects, no longer `["2:00 PM", ...]`:
  `{showtime_id, tmdb_id, showroom_id, showroom_name, start_time, end_time}`.
  Times are ISO text in UTC ending in `Z`. Show them with `new Date(start_time)` (browser local time).
- Movies also have `runtime`, `cast`, `director`, `producer`, `reviews`.
- `rating` is an MPAA code (PG-13). `format_movie(m)` still works alone (empty `showtimes`);
  pass the showtimes in as `format_movie(m, showtimes)`.
- Sending a time to the backend: use `new Date("2026-11-20T19:00").toISOString()` so the
  server gets an unambiguous UTC value, then `datetime.fromisoformat(s.replace("Z", "+00:00"))`.

## Backend cheat sheet (all in models.py, all take `db`)
| Need | Call |
|---|---|
| Movies with showtimes | `g = showtimes_by_movie(db, [m["tmdb_id"] for m in movies])` then `format_movie(m, g.get(m["tmdb_id"]))` |
| Add Movie validation | `check_movie_fields(data)` -> `{field: message}`; `create_movie(db, data)` -> `(movie, errors)` |
| Allowed values for dropdowns | `MOVIE_GENRES`, `MPAA_RATINGS`, `MOVIE_STATUSES` |
| Showroom list | `list_showrooms(db)` |
| Rooms free at a time (admin form) | `list_available_showrooms(db, tmdb_id, start)` -> each room has `available` |
| Add showtime | `create_showtime(db, tmdb_id, showroom_id, start)` -> `(showtime, None)` or `(None, {code, message, conflict})`; codes: `movie_not_found`, `showroom_not_found`, `invalid_time`, `conflict` |
| One showtime | `get_showtime(db, showtime_id)` |
| Seat map | `get_seat_map(db, showtime_id, holder_id)`; seats are `available`, `booked`, `selected` |
| Reserve seats | `hold_seats(db, showtime_id, holder_id, seat_ids)` -> `{ok, reason, seats}`; reasons: `no_seats`, `too_many`, `showtime_not_found`, `showtime_started`, `invalid_seat`, `seats_taken` |
| Free seats | `release_holds(db, showtime_id, holder_id)` |
| Guest logs in at checkout | `transfer_holds(db, showtime_id, guest_session_id, user_id)` |
| Prices | `get_pricing(db)` -> `{prices:{Adult,Child,Senior}, booking_fee, tax_rate}` |
| Final demo | `hold_seats(..., hold_minutes=5)` for the 5 minute unlock, `mark_booked(...)` after payment |
| Bonus | `create_promotion(db, ...)` (raises ValueError), `get_promo_subscribers(db)` |

`holder_id` = the user's `user_id`, or a random session id (made by the frontend) for a guest.
Max seats per booking is `MAX_SEATS_PER_BOOKING` (8). Rules about who may call what stay in `app.py`.

## Test cases (Test Readiness: conflicts, visibility, booking flow, seat selection)
Seed data: 3 rooms (Screen 1: 60 seats, Screen 2: 40, Screen 3: 96), 6 running movies with showings
at 11:00, 2:30, 6:00 and 9:30 PM in every room for 7 days, 2 coming-soon movies with none.

**Scheduling conflicts**
1. Add any movie to Screen 1 tomorrow at 11:00 AM -> rejected (same room, same time).
2. Add any movie to Screen 1 tomorrow at 11:30 AM -> rejected (overlaps a running show).
3. Add a movie to Screen 1 and Screen 2 at the same free time -> both accepted.
4. Add a movie on the day after the seeded week (the seed prints the date) at 7:00 PM -> accepted.

**Showtime visibility**
5. Add a movie, then schedule it -> it appears in the user portal with its showtimes.
6. Open a Currently Running movie -> showtimes list matches the database, grouped by day.
7. Open a Coming Soon movie -> no showtimes.

**Booking flow**
8. Movie -> showtime -> 2 Adult + 1 Child -> seat map -> 3 seats -> Proceed to Checkout.
9. Logged out at checkout -> asked to log in, then continues with the same seats still held.
10. Order summary shows movie, showtime, seats, ticket counts and types, price per ticket, total before tax.

**Seat selection**
11. Tomorrow's first Screen 1 showing has A1-A4, C5-C6, D5-D6 booked -> they show as taken and can't be clicked.
12. Pick fewer or more seats than tickets -> rejected.
13. Two browsers pick the same seat -> the second gets "seat already taken".

**Invalid input**
14. Add Movie with empty fields, bad rating, bad poster URL, runtime 5 -> each field flagged.
15. Add a movie with a title that already exists -> rejected.
