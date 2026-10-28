import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Search, Play, X, Star, Clock3, Film, ChevronRight,
  Clapperboard, CalendarDays, SlidersHorizontal,
  ArrowLeft, Check, User, Mail, Armchair
} from "lucide-react";
import "./styles.css";
import AccountPages from "./AccountPages.jsx";
import LoginPage from "./LoginPage.jsx";
import useAuth from "./hooks/useAuth.js";

const API_BASE =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:5000/api";

const GENRES = [
  "All",
  "Action",
  "Comedy",
  "Drama",
  "Sci-Fi",
  "Horror",
  "Romance"
];

function App() {
  const { accessToken, user, isAuthenticated, signIn, logout, loading: authLoading, error: authError } = useAuth();
  const accountToken = accessToken;

  // Keep React navigation synchronized with the browser's history.
  const [accountPath, setAccountPath] = useState(() => {
    const path = window.location.pathname;
    return path === '/login' || path.startsWith('/account/') ? path : null;
  });

  useEffect(() => {
    const sync = () => {
      const path = window.location.pathname;
      setAccountPath(path === '/login' || path.startsWith('/account/') ? path : null);
    };
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);

  function navigateAccount(path) {
    window.history.pushState({}, '', path);
    setAccountPath(path === '/login' || path.startsWith('/account/') ? path : null);
  }

  async function handleLogin(email, password) {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `Login failed (${response.status})`);
    }
    if (!data.access_token) {
      throw new Error('Login response did not contain an access token.');
    }
    await signIn(data.access_token);
    navigateAccount('/account/profile');
  }

  function handleLogout() {
    logout();
    navigateAccount('/login');
  }

  const [movies, setMovies] = useState([]);
  const [status, setStatus] = useState("Currently Running");
  const [genre, setGenre] = useState("All");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [bookingMovie, setBookingMovie] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function fetchMovies(url) {
    setLoading(true);
    setError("");

    try {
      const res = await fetch(url);

      if (!res.ok) {
        throw new Error(`Request failed (${res.status})`);
      }

      setMovies(await res.json());
    } catch (err) {
      setError(
        "Could not connect to the Flask API. Make sure app.py is running on port 5000."
      );
      setMovies([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (search.trim()) {
      const timer = setTimeout(() => {
        fetchMovies(
          `${API_BASE}/movies/search?title=${encodeURIComponent(
            search.trim()
          )}`
        );
      }, 250);

      return () => clearTimeout(timer);
    }

    if (genre !== "All") {
      fetchMovies(
        `${API_BASE}/movies/filter?genre=${encodeURIComponent(genre)}`
      );
    } else {
      fetchMovies(
        `${API_BASE}/movies?status=${encodeURIComponent(status)}`
      );
    }
  }, [status, genre, search]);

  const featured = useMemo(() => movies[0], [movies]);

  function changeStatus(next) {
    setSearch("");
    setGenre("All");
    setStatus(next);
  }

  if (accountPath === '/login') {
    return <LoginPage onLogin={handleLogin} navigate={navigateAccount}
      loading={authLoading} authError={authError} />;
  }
  if (accountPath) {
    return <AccountPages path={accountPath} navigate={navigateAccount}
      token={accountToken} onPasswordChanged={handleLogout} />;
  }
  if (bookingMovie) {
    return (
      <BookingPage
        movie={bookingMovie}
        onBack={() => setBookingMovie(null)}
      />
    );
  }

  return (
    <div className="app">
      <header className="nav">
        <div className="nav-inner">

          <button
            className="brand"
            onClick={() => {
              setSearch("");
              setGenre("All");
              setStatus("Currently Running");
            }}
          >
            <span className="brand-icon">
              <Clapperboard size={19} />
            </span>
            <span>CINEMA</span>
          </button>

          <nav className="nav-links">
            <button
              className={
                status === "Currently Running" &&
                !search &&
                genre === "All"
                  ? "active"
                  : ""
              }
              onClick={() => changeStatus("Currently Running")}
            >
              Now Playing
            </button>

            <button
              className={
                status === "Coming Soon" &&
                !search &&
                genre === "All"
                  ? "active"
                  : ""
              }
              onClick={() => changeStatus("Coming Soon")}
            >
              Coming Soon
            </button>
          </nav>

          {isAuthenticated ? (
            <>
              <button className="account-navbar-link" type="button"
                onClick={() => navigateAccount('/account/profile')}>
                {user?.first_name ? `My Account (${user.first_name})` : 'My Account'}
              </button>
              <button className="account-navbar-link" type="button"
                onClick={handleLogout}>Sign Out</button>
            </>
          ) : (
            <>
              <button className="account-navbar-link" type="button"
                onClick={() => navigateAccount('/login')}>Sign In</button>
              <button className="account-navbar-link" type="button"
                onClick={() => navigateAccount('/account/register')}>Create Account</button>
            </>
          )}
          <div className="search-box">
            <Search size={17} />

            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search movies..."
            />

            {search && (
              <button
                className="clear-search"
                onClick={() => setSearch("")}
              >
                <X size={15} />
              </button>
            )}
          </div>
        </div>
      </header>

      <main>

        {!search && genre === "All" && featured && (
          <section className="hero">
            <div
              className="hero-backdrop"
              style={{
                backgroundImage: `url(${featured.poster_url})`
              }}
            />

            <div className="hero-overlay" />

            <div className="hero-content">

              <div className="eyebrow">
                <span className="live-dot" />

                {status === "Currently Running"
                  ? "NOW SHOWING"
                  : "COMING SOON"}
              </div>

              <h1>{featured.title}</h1>

              <div className="hero-meta">
                <span>
                  <Star size={15} fill="currentColor" />
                  {featured.rating}
                </span>

                <span>{featured.genre}</span>

                <span>
                  <Clock3 size={15} />
                  2h 10m
                </span>
              </div>

              <p>{featured.description}</p>

              <button
                className="primary-btn"
                onClick={() => setBookingMovie(featured)}
              >
                <CalendarDays size={17} />
                Book Tickets
              </button>

            </div>
          </section>
        )}

        <section className="catalog">

          <div className="section-top">
            <div>
              <p className="section-kicker">
                {search ? "RESULTS" : "EXPLORE"}
              </p>

              <h2>
                {search
                  ? `Search results for "${search}"`
                  : status}
              </h2>
            </div>

            <div className="results-count">
              <Film size={16} />
              {movies.length} movies
            </div>
          </div>

          <div className="filter-row">

            <div className="filter-label">
              <SlidersHorizontal size={16} />
              Genre
            </div>

            {GENRES.map((g) => (
              <button
                key={g}
                className={`filter-chip ${
                  genre === g ? "selected" : ""
                }`}
                onClick={() => {
                  setGenre(g);
                  setSearch("");
                }}
              >
                {g}
              </button>
            ))}

          </div>

          {loading ? (
            <div className="movie-grid">

              {Array.from({ length: 6 }).map((_, i) => (
                <div className="skeleton-card" key={i}>
                  <div className="skeleton poster" />
                  <div className="skeleton line" />
                  <div className="skeleton small-line" />
                </div>
              ))}

            </div>

          ) : error ? (

            <div className="empty-state error-state">
              <div className="empty-icon">!</div>

              <h3>API connection failed</h3>

              <p>{error}</p>

              <button
                className="secondary-btn"
                onClick={() => window.location.reload()}
              >
                Retry
              </button>
            </div>

          ) : movies.length === 0 ? (

            <div className="empty-state">
              <div className="empty-icon">
                <Film size={26} />
              </div>

              <h3>No movies found</h3>

              <p>
                Try another title, genre, or category.
              </p>
            </div>

          ) : (

            <div className="movie-grid">

              {movies.map((movie) => (
                <MovieCard
                  key={movie.tmdb_id}
                  movie={movie}
                  onOpen={() => setSelected(movie)}
                  onBook={() => setBookingMovie(movie)}
                />
              ))}

            </div>
          )}

        </section>
      </main>

      <footer>
        <div className="footer-inner">
          <span>© 2026 Cinema</span>
          <span>Powered by TMDb data</span>
        </div>
      </footer>

      {selected && (
        <MovieModal
          movie={selected}
          onClose={() => setSelected(null)}
          onBook={() => {
            setSelected(null);
            setBookingMovie(selected);
          }}
        />
      )}
    </div>
  );
}


function MovieCard({ movie, onOpen, onBook }) {
  return (
    <article className="movie-card">

      <button
        className="poster-wrap"
        onClick={onOpen}
      >
        <img
          src={movie.poster_url}
          alt={movie.title}
        />

        <div className="poster-shade" />

        <span className="rating">
          <Star size={12} fill="currentColor" />
          {movie.rating}
        </span>

        <span className="play-circle">
          <Play size={19} fill="currentColor" />
        </span>
      </button>

      <div className="movie-info">

        <h3 title={movie.title}>
          {movie.title}
        </h3>

        <div className="movie-sub">
          <span>{movie.genre}</span>

          <span className="dot">•</span>

          <span>
            {movie.status === "Coming Soon"
              ? "Coming soon"
              : "Now showing"}
          </span>
        </div>

        <button
          className="showtimes-btn"
          onClick={onBook}
        >
          Book Tickets
          <ChevronRight size={15} />
        </button>

      </div>
    </article>
  );
}


function MovieModal({ movie, onClose, onBook }) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handler);

    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="modal">

        <button
          className="modal-close"
          onClick={onClose}
        >
          <X size={21} />
        </button>

        <div className="modal-media">

          <img
            src={movie.poster_url}
            alt={movie.title}
          />

          <div className="modal-gradient" />

          <div className="modal-title">
            <p>
              {movie.genre} · {movie.status}
            </p>

            <h2>{movie.title}</h2>
          </div>

        </div>

        <div className="modal-body">

          <div className="detail-meta">

            <span>
              <Star size={15} fill="currentColor" />
              {movie.rating}
            </span>

            <span>
              <CalendarDays size={15} />
              {movie.status}
            </span>

          </div>

          <p className="description">
            {movie.description ||
              "No description available."}
          </p>

          <div className="showtimes">

            <h3>Today's Showtimes</h3>

            <div className="times">

              {(movie.showtimes || []).map((time) => (
                <button
                  key={time}
                  onClick={onBook}
                >
                  {time}
                </button>
              ))}

            </div>

          </div>

          <button
            className="trailer-btn"
            onClick={onBook}
          >
            <CalendarDays size={16} />
            Continue to Booking
          </button>

        </div>
      </div>
    </div>
  );
}


/* =========================================================
   BOOKING PAGE
========================================================= */

function BookingPage({ movie, onBack }) {

  const [date, setDate] = useState("Today");
  const [time, setTime] = useState(movie.showtimes?.[0] || "2:00 PM");
  const [selectedSeats, setSelectedSeats] = useState([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  const rows = ["A", "B", "C", "D", "E", "F"];
  const seatsPerRow = 10;

  const ticketPrice = 13.5;
  const subtotal = selectedSeats.length * ticketPrice;
  const fee = selectedSeats.length ? 2.5 : 0;
  const total = subtotal + fee;

  function toggleSeat(seat) {
    setSelectedSeats((current) => {
      if (current.includes(seat)) {
        return current.filter((s) => s !== seat);
      }

      if (current.length >= 8) {
        return current;
      }

      return [...current, seat];
    });
  }

  function submitBooking(e) {
    e.preventDefault();

    if (
      selectedSeats.length === 0 ||
      !name.trim() ||
      !email.trim()
    ) {
      return;
    }

    setConfirmed(true);
  }

  if (confirmed) {
    return (
      <div className="booking-page">

        <header className="nav">
          <div className="nav-inner">

            <button
              className="brand"
              onClick={onBack}
            >
              <span className="brand-icon">
                <Clapperboard size={19} />
              </span>

              <span>CINEMA</span>
            </button>

          </div>
        </header>

        <main className="confirmation-page">

          <div className="confirmation-icon">
            <Check size={38} />
          </div>

          <p className="section-kicker">
            BOOKING CONFIRMED
          </p>

          <h1>Your tickets are booked.</h1>

          <p className="confirmation-text">
            Your reservation for{" "}
            <strong>{movie.title}</strong>{" "}
            is confirmed.
          </p>

          <div className="confirmation-card">

            <div>
              <span>DATE</span>
              <strong>{date}</strong>
            </div>

            <div>
              <span>SHOWTIME</span>
              <strong>{time}</strong>
            </div>

            <div>
              <span>SEATS</span>
              <strong>
                {selectedSeats.sort().join(", ")}
              </strong>
            </div>

            <div>
              <span>TOTAL</span>
              <strong>${total.toFixed(2)}</strong>
            </div>

          </div>

          <button
            className="primary-btn"
            onClick={onBack}
          >
            Back to Movies
          </button>

        </main>
      </div>
    );
  }

  return (
    <div className="booking-page">

      <header className="nav">
        <div className="nav-inner">

          <button
            className="brand"
            onClick={onBack}
          >
            <span className="brand-icon">
              <Clapperboard size={19} />
            </span>

            <span>CINEMA</span>
          </button>

        </div>
      </header>

      <main className="booking-container">

        <button
          className="back-button"
          onClick={onBack}
        >
          <ArrowLeft size={17} />
          Back to movies
        </button>

        <div className="booking-heading">
          <div>
            <p className="section-kicker">
              BOOK TICKETS
            </p>

            <h1>{movie.title}</h1>

            <p>
              {movie.genre} · {movie.rating}
            </p>
          </div>
        </div>

        <div className="booking-layout">

          <section className="booking-main">

            <div className="booking-section">

              <div className="booking-section-title">
                <CalendarDays size={19} />
                <div>
                  <h2>Choose a date</h2>
                  <p>Select your show date</p>
                </div>
              </div>

              <div className="date-options">

                {["Today", "Tomorrow", "Friday", "Saturday"].map(
                  (d) => (
                    <button
                      key={d}
                      className={
                        date === d
                          ? "date-card selected"
                          : "date-card"
                      }
                      onClick={() => setDate(d)}
                    >
                      <span>{d}</span>
                    </button>
                  )
                )}

              </div>

            </div>


            <div className="booking-section">

              <div className="booking-section-title">
                <Clock3 size={19} />

                <div>
                  <h2>Choose a showtime</h2>
                  <p>Select your preferred time</p>
                </div>
              </div>

              <div className="booking-times">

                {(movie.showtimes || []).map((t) => (
                  <button
                    key={t}
                    className={
                      time === t
                        ? "booking-time selected"
                        : "booking-time"
                    }
                    onClick={() => setTime(t)}
                  >
                    {t}
                  </button>
                ))}

              </div>

            </div>


            <div className="booking-section">

              <div className="booking-section-title">
                <Armchair size={19} />

                <div>
                  <h2>Choose your seats</h2>
                  <p>Maximum 8 seats per booking</p>
                </div>
              </div>

              <div className="screen">
                SCREEN
              </div>

              <div className="seat-map">

                {rows.map((row) => (
                  <div
                    className="seat-row"
                    key={row}
                  >

                    <span className="row-label">
                      {row}
                    </span>

                    {Array.from({
                      length: seatsPerRow
                    }).map((_, i) => {

                      const seat = `${row}${i + 1}`;

                      const selected =
                        selectedSeats.includes(seat);

                      return (
                        <button
                          key={seat}
                          className={
                            selected
                              ? "seat selected"
                              : "seat"
                          }
                          onClick={() =>
                            toggleSeat(seat)
                          }
                        >
                          {i + 1}
                        </button>
                      );
                    })}

                  </div>
                ))}

              </div>

              <div className="seat-legend">
                <span>
                  <i className="legend available" />
                  Available
                </span>

                <span>
                  <i className="legend chosen" />
                  Selected
                </span>
              </div>

            </div>


            <form
              className="booking-section"
              onSubmit={submitBooking}
            >

              <div className="booking-section-title">
                <User size={19} />

                <div>
                  <h2>Your information</h2>
                  <p>We'll send your booking confirmation here</p>
                </div>
              </div>

              <div className="input-grid">

                <label>
                  Full name

                  <input
                    value={name}
                    onChange={(e) =>
                      setName(e.target.value)
                    }
                    placeholder="John Doe"
                    required
                  />
                </label>

                <label>
                  Email address

                  <input
                    type="email"
                    value={email}
                    onChange={(e) =>
                      setEmail(e.target.value)
                    }
                    placeholder="john@example.com"
                    required
                  />
                </label>

              </div>

              <button
                className="confirm-booking"
                type="submit"
                disabled={
                  selectedSeats.length === 0 ||
                  !name.trim() ||
                  !email.trim()
                }
              >
                Confirm Booking
              </button>

            </form>

          </section>


          <aside className="booking-summary">

            <img
              src={movie.poster_url}
              alt={movie.title}
            />

            <div className="summary-content">

              <p className="section-kicker">
                YOUR ORDER
              </p>

              <h2>{movie.title}</h2>

              <div className="summary-row">
                <span>Date</span>
                <strong>{date}</strong>
              </div>

              <div className="summary-row">
                <span>Showtime</span>
                <strong>{time}</strong>
              </div>

              <div className="summary-row">
                <span>Seats</span>
                <strong>
                  {selectedSeats.length
                    ? selectedSeats.join(", ")
                    : "None selected"}
                </strong>
              </div>

              <div className="summary-divider" />

              <div className="summary-row">
                <span>
                  Tickets × {selectedSeats.length}
                </span>

                <strong>
                  ${subtotal.toFixed(2)}
                </strong>
              </div>

              <div className="summary-row">
                <span>Booking fee</span>

                <strong>
                  ${fee.toFixed(2)}
                </strong>
              </div>

              <div className="summary-total">
                <span>Total</span>

                <strong>
                  ${total.toFixed(2)}
                </strong>
              </div>

            </div>

          </aside>

        </div>

      </main>
    </div>
  );
}


createRoot(
  document.getElementById("root")
).render(<App />);
