import React, { useEffect, useState } from "react";
import { ArrowLeft, Heart, Film } from "lucide-react";
import HeartButton from "./HeartButton.jsx";
import "./account-pages.css";

// Shows the logged-in user's favorite movies (GET /users/<id>/favorites).
export default function FavoritesPage({ auth, navigate, onToggleFavorite }) {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const userId = auth.user?.user_id;
  // Re-fetch whenever the user's favorites change (e.g. after un-hearting).
  const favoriteKey = (auth.user?.favorites || []).join(",");
  const { authFetch } = auth;

  useEffect(() => {
    if (!userId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError("");

    authFetch(`/users/${encodeURIComponent(userId)}/favorites`)
      .then((data) => {
        if (!cancelled) setMovies(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Could not load your favorites.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [userId, favoriteKey, authFetch]);

  return (
    <div className="account-screen">
      <header className="account-header">
        <button type="button" className="account-back" onClick={() => navigate("/")}>
          <ArrowLeft size={17} />
          Movies
        </button>
        <span className="account-wordmark">CINEMA</span>
      </header>

      <main className="account-panel account-panel-wide">
        <div className="account-panel-icon">
          <Heart size={24} />
        </div>

        <h1>My Favorites</h1>
        <p className="account-subtitle">Movies you have saved, whether or not you bought tickets.</p>

        {error && (
          <p role="alert" className="account-alert account-alert-error">
            {error}
          </p>
        )}

        {loading ? (
          <p className="page-loading">Loading your favorites…</p>
        ) : movies.length === 0 && !error ? (
          <div className="fav-empty">
            <Film size={26} />
            <p>No favorites yet. Tap the heart on any movie to save it here.</p>
            <button type="button" className="account-action" onClick={() => navigate("/")}>
              Browse movies
            </button>
          </div>
        ) : (
          <div className="fav-grid">
            {movies.map((movie) => (
              <article className="movie-card" key={movie.tmdb_id}>
                <div className="poster-wrap fav-poster">
                  <img src={movie.poster_url} alt={movie.title} />
                  <span className="rating">{movie.rating}</span>
                </div>
                <HeartButton active onClick={() => onToggleFavorite(movie)} />
                <div className="movie-info">
                  <h3 title={movie.title}>{movie.title}</h3>
                  <div className="movie-sub">
                    <span>{movie.genre}</span>
                    <span className="dot">•</span>
                    <span>{movie.status === "Coming Soon" ? "Coming soon" : "Now showing"}</span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
