import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Search, Play, X, Star, Clock3, Film, ChevronRight,
  Clapperboard, CalendarDays, SlidersHorizontal
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000/api";

const GENRES = ["All", "Action", "Comedy", "Drama", "Sci-Fi", "Horror", "Romance"];

function App() {
  const [movies, setMovies] = useState([]);
  const [status, setStatus] = useState("Currently Running");
  const [genre, setGenre] = useState("All");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function fetchMovies(url) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      setMovies(await res.json());
    } catch (err) {
      setError("Could not connect to the Flask API. Make sure app.py is running on port 5000.");
      setMovies([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (search.trim()) {
      const timer = setTimeout(() => {
        fetchMovies(`${API_BASE}/movies/search?title=${encodeURIComponent(search.trim())}`);
      }, 250);
      return () => clearTimeout(timer);
    }
    if (genre !== "All") {
      fetchMovies(`${API_BASE}/movies/filter?genre=${encodeURIComponent(genre)}`);
    } else {
      fetchMovies(`${API_BASE}/movies?status=${encodeURIComponent(status)}`);
    }
  }, [status, genre, search]);

  const featured = useMemo(() => movies[0], [movies]);

  function changeStatus(next) {
    setSearch("");
    setGenre("All");
    setStatus(next);
  }

  return (
    <div className="app">
      <header className="nav">
        <div className="nav-inner">
          <a className="brand" href="#" onClick={() => { setSearch(""); setGenre("All"); setStatus("Currently Running"); }}>
            <span className="brand-icon"><Clapperboard size={19} /></span>
            <span>CINEMA</span>
          </a>

          <nav className="nav-links">
            <button className={status === "Currently Running" && !search && genre === "All" ? "active" : ""} onClick={() => changeStatus("Currently Running")}>Now Playing</button>
            <button className={status === "Coming Soon" && !search && genre === "All" ? "active" : ""} onClick={() => changeStatus("Coming Soon")}>Coming Soon</button>
          </nav>

          <div className="search-box">
            <Search size={17} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search movies..."
              aria-label="Search movies"
            />
            {search && <button className="clear-search" onClick={() => setSearch("")}><X size={15} /></button>}
          </div>
        </div>
      </header>

      <main>
        {!search && genre === "All" && featured && (
          <section className="hero">
            <div className="hero-backdrop" style={{ backgroundImage: `url(${featured.poster_url})` }} />
            <div className="hero-overlay" />
            <div className="hero-content">
              <div className="eyebrow"><span className="live-dot" /> {status === "Currently Running" ? "NOW SHOWING" : "COMING SOON"}</div>
              <h1>{featured.title}</h1>
              <div className="hero-meta">
                <span><Star size={15} fill="currentColor" /> {featured.rating}</span>
                <span>{featured.genre}</span>
                <span><Clock3 size={15} /> 2h 10m</span>
              </div>
              <p>{featured.description}</p>
              <button className="primary-btn" onClick={() => setSelected(featured)}>
                <Play size={17} fill="currentColor" /> Watch Trailer
              </button>
            </div>
          </section>
        )}

        <section className="catalog">
          <div className="section-top">
            <div>
              <p className="section-kicker">{search ? "RESULTS" : "EXPLORE"}</p>
              <h2>{search ? `Search results for "${search}"` : status}</h2>
            </div>
            <div className="results-count"><Film size={16} /> {movies.length} movies</div>
          </div>

          <div className="filter-row">
            <div className="filter-label"><SlidersHorizontal size={16} /> Genre</div>
            {GENRES.map((g) => (
              <button key={g} className={`filter-chip ${genre === g ? "selected" : ""}`} onClick={() => { setGenre(g); setSearch(""); }}>
                {g}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="movie-grid">
              {Array.from({length: 6}).map((_, i) => <div className="skeleton-card" key={i}><div className="skeleton poster" /><div className="skeleton line" /><div className="skeleton small-line" /></div>)}
            </div>
          ) : error ? (
            <div className="empty-state error-state">
              <div className="empty-icon">!</div>
              <h3>API connection failed</h3>
              <p>{error}</p>
              <button className="secondary-btn" onClick={() => window.location.reload()}>Retry</button>
            </div>
          ) : movies.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon"><Film size={26} /></div>
              <h3>No movies found</h3>
              <p>Try another title, genre, or category.</p>
            </div>
          ) : (
            <div className="movie-grid">
              {movies.map((movie) => (
                <MovieCard key={movie.tmdb_id} movie={movie} onOpen={() => setSelected(movie)} />
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

      {selected && <MovieModal movie={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function MovieCard({ movie, onOpen }) {
  return (
    <article className="movie-card">
      <button className="poster-wrap" onClick={onOpen} aria-label={`Open ${movie.title}`}>
        <img src={movie.poster_url} alt={movie.title} />
        <div className="poster-shade" />
        <span className="rating"><Star size={12} fill="currentColor" /> {movie.rating}</span>
        <span className="play-circle"><Play size={19} fill="currentColor" /></span>
      </button>
      <div className="movie-info">
        <h3 title={movie.title}>{movie.title}</h3>
        <div className="movie-sub">
          <span>{movie.genre}</span>
          <span className="dot">•</span>
          <span>{movie.status === "Coming Soon" ? "Coming soon" : "Now showing"}</span>
        </div>
        <button className="showtimes-btn" onClick={onOpen}>
          Showtimes <ChevronRight size={15} />
        </button>
      </div>
    </article>
  );
}

function MovieModal({ movie, onClose }) {
  useEffect(() => {
    const handler = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <button className="modal-close" onClick={onClose}><X size={21} /></button>
        <div className="modal-media">
          <img src={movie.poster_url} alt={movie.title} />
          <div className="modal-gradient" />
          <div className="modal-title">
            <p>{movie.genre} · {movie.status}</p>
            <h2>{movie.title}</h2>
          </div>
        </div>
        <div className="modal-body">
          <div className="detail-meta">
            <span><Star size={15} fill="currentColor" /> {movie.rating}</span>
            <span><CalendarDays size={15} /> {movie.status}</span>
          </div>
          <p className="description">{movie.description || "No description available."}</p>

          <div className="showtimes">
            <h3>Today's Showtimes</h3>
            <div className="times">
              {(movie.showtimes || []).map((time) => <button key={time}>{time}</button>)}
            </div>
          </div>

          <a className="trailer-btn" href={movie.trailer_url} target="_blank" rel="noreferrer">
            <Play size={16} fill="currentColor" /> Watch Trailer
          </a>
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
