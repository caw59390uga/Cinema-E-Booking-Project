import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Film, Percent, Users, CalendarClock, LogOut, ArrowLeft,
  ShieldCheck, Plus, CheckCircle2, AlertCircle, Clock3,
} from "lucide-react";
import "./account-pages.css";
import "./admin-home.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000/api";
const FALLBACK_GENRES = ["Action", "Comedy", "Drama", "Sci-Fi", "Horror", "Romance"];
const FALLBACK_RATINGS = ["G", "PG", "PG-13", "R", "NC-17", "NR"];
const FALLBACK_STATUSES = ["Currently Running", "Coming Soon"];
const MENU = [
  { key: "add", label: "Add Movie", icon: Plus, description: "Create a movie listing with field-by-field validation." },
  { key: "schedule", label: "Schedule a Movie", icon: CalendarClock, description: "Find an available screen and schedule a showtime." },
  { key: "promotions", label: "Manage Promotions", icon: Percent, description: "Promotion management is a separate admin feature." },
  { key: "users", label: "Manage Users", icon: Users, description: "Customer administration is a separate feature." },
];
const BLANK_MOVIE = {
  title: "", genre: "", rating: "", status: "Currently Running",
  runtime: "", description: "", cast: "", director: "", producer: "",
  poster_url: "", trailer_url: "", reviews: "",
};

function movieOptions(catalog) {
  return [...(catalog.movies || [])].sort((a, b) => a.title.localeCompare(b.title));
}

function humanDate(value) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function futureLocalMin() {
  const d = new Date();
  const pad = (v) => String(v).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function futureISO(local) {
  if (!local) return null;
  const date = new Date(local);
  return Number.isFinite(date.getTime()) && date.getTime() > Date.now() ? date.toISOString() : null;
}

function validUrl(input) {
  try { return ["https:", "http:"].includes(new URL(input).protocol); }
  catch { return false; }
}

function checkMovie(form, catalog) {
  const errors = {};
  if (!form.title.trim()) errors.title = "Movie title is required.";
  else if (form.title.trim().length > 200) errors.title = "Keep the title within 200 characters.";
  if (!(catalog.genres || FALLBACK_GENRES).includes(form.genre)) errors.genre = "Choose a genre.";
  if (!(catalog.ratings || FALLBACK_RATINGS).includes(form.rating)) errors.rating = "Choose an MPAA rating.";
  if (!(catalog.statuses || FALLBACK_STATUSES).includes(form.status)) errors.status = "Choose a valid release status.";
  const runtime = Number(form.runtime);
  if (!form.runtime || !Number.isInteger(runtime) || runtime < 30 || runtime > 400) {
    errors.runtime = "Runtime must be a whole number from 30 to 400 minutes.";
  }
  if (!form.description.trim()) errors.description = "Synopsis is required.";
  else if (form.description.trim().length > 3000) errors.description = "Keep the synopsis within 3,000 characters.";
  if (!form.cast.trim()) errors.cast = "Enter at least one cast member.";
  for (const [key, label] of [["director", "Director"], ["producer", "Producer"]]) {
    if (!form[key].trim()) errors[key] = `${label} is required.`;
    else if (form[key].trim().length > 200) errors[key] = `${label} must be 200 characters or fewer.`;
  }
  if (!validUrl(form.poster_url.trim())) errors.poster_url = "Enter a valid http(s) poster URL.";
  if (!validUrl(form.trailer_url.trim())) errors.trailer_url = "Enter a valid http(s) trailer URL.";
  return errors;
}

function Field({ id, label, value, error, onChange, options, type = "text", multiline = false, hint, required = true, ...rest }) {
  const props = {
    id: `admin-${id}`, value, onChange, "aria-invalid": Boolean(error),
    "aria-describedby": error ? `admin-${id}-error` : undefined,
    required, ...rest,
  };
  return (
    <div className={`admin-field ${multiline ? "admin-field-wide" : ""}`}>
      <label htmlFor={`admin-${id}`}>{label}{required && <span className="admin-required"> *</span>}</label>
      {options ? (
        <select {...props}><option value="">Choose {label.toLowerCase()}</option>
          {options.map((v) => { const item = typeof v === "string" ? { value: v, label: v } : v;
            return <option key={item.value} value={item.value}>{item.label}</option>; })}
        </select>
      ) : multiline ? <textarea {...props} rows={4} /> : <input {...props} type={type} />}
      {hint && !error && <small className="admin-hint">{hint}</small>}
      {error && <small id={`admin-${id}-error`} role="alert" className="admin-error">{error}</small>}
    </div>
  );
}

function Feedback({ error, success }) {
  if (error) return <p className="admin-feedback admin-feedback-error" role="alert"><AlertCircle size={16} /> {error}</p>;
  if (success) return <p className="admin-feedback admin-feedback-success" role="status"><CheckCircle2 size={16} /> {success}</p>;
  return null;
}

function AddMovieForm({ catalog, request, onMovieCreated }) {
  const [form, setForm] = useState(BLANK_MOVIE);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [created, setCreated] = useState(null);

  function change(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
    setFailure("");
    setCreated(null);
  }

  async function submit(event) {
    event.preventDefault();
    const invalid = checkMovie(form, catalog);
    setErrors(invalid);
    setFailure("");
    setCreated(null);
    if (Object.keys(invalid).length) return;
    setBusy(true);
    const payload = {
      ...form,
      title: form.title.trim(), description: form.description.trim(),
      runtime: Number(form.runtime),
      cast: form.cast.split(/[,\n]/).map((s) => s.trim()).filter(Boolean),
      reviews: form.reviews.split(/\n/).map((s) => s.trim()).filter(Boolean),
    };
    try {
      const result = await request("/admin/movies", { method: "POST", body: payload });
      setCreated(result.movie);
      onMovieCreated(result.movie);
      setForm(BLANK_MOVIE);
    } catch (err) {
      setErrors(err.fields || {});
      setFailure(err.message || "Couldn't add this movie.");
    } finally {
      setBusy(false);
    }
  }

  const props = (field) => ({
    value: form[field], error: errors[field],
    onChange: (e) => change(field, e.target.value),
  });

  return <section className="admin-workspace" aria-labelledby="admin-add-title">
    <div className="admin-workspace-heading"><Film size={21} /><div>
      <h2 id="admin-add-title">Add Movie</h2>
      <p>Enter the movie details. Any invalid fields will be highlighted before saving.</p>
    </div></div>
    <form onSubmit={submit} noValidate>
      <div className="admin-form-grid">
        <Field id="title" label="Movie title" autoComplete="off" maxLength={201} {...props("title")} />
        <Field id="runtime" label="Runtime (minutes)" type="number" min="30" max="400" step="1" {...props("runtime")} />
        <Field id="genre" label="Genre" options={catalog.genres || FALLBACK_GENRES} {...props("genre")} />
        <Field id="rating" label="MPAA rating" options={catalog.ratings || FALLBACK_RATINGS} {...props("rating")} />
        <Field id="status" label="Release status" options={catalog.statuses || FALLBACK_STATUSES} {...props("status")} />
        <Field id="director" label="Director" {...props("director")} />
        <Field id="producer" label="Producer" {...props("producer")} />
        <Field id="cast" label="Cast" hint="Separate names with commas." {...props("cast")} />
        <Field id="poster_url" label="Poster URL" type="url" placeholder="https://..." {...props("poster_url")} />
        <Field id="trailer_url" label="Trailer URL" type="url" placeholder="https://..." {...props("trailer_url")} />
        <Field id="description" label="Synopsis" multiline maxLength={3001} {...props("description")} />
        <Field id="reviews" label="Reviews (optional)" multiline required={false}
          hint="One review per line, if available." {...props("reviews")} />
      </div>
      <Feedback error={failure} success={created && `${created.title} was added to the database.`} />
      <div className="admin-actions">
        <button className="admin-primary" type="submit" disabled={busy}>{busy ? "Adding movie…" : "Add Movie"}</button>
        {created && <button className="admin-secondary" type="button" onClick={() => onMovieCreated(created, true)}>
          Schedule this movie
        </button>}
      </div>
    </form>
  </section>;
}

function ScheduleMovieForm({ catalog, request, initialMovieId, refreshCatalog }) {
  const movies = useMemo(() => movieOptions(catalog), [catalog]);
  const [movieId, setMovieId] = useState(initialMovieId ? String(initialMovieId) : "");
  const [localTime, setLocalTime] = useState("");
  const [roomId, setRoomId] = useState("");
  const [rooms, setRooms] = useState([]);
  const [loadingRooms, setLoadingRooms] = useState(false);
  const [roomError, setRoomError] = useState("");
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [saved, setSaved] = useState(null);
  const [checkVersion, setCheckVersion] = useState(0);

  useEffect(() => {
    if (initialMovieId) setMovieId(String(initialMovieId));
  }, [initialMovieId]);

  const startISO = futureISO(localTime);
  useEffect(() => {
    let cancelled = false;
    if (!movieId || !startISO) {
      setRooms([]);
      setRoomError("");
      setLoadingRooms(false);
      return undefined;
    }
    setLoadingRooms(true);
    setRoomError("");
    const timer = setTimeout(async () => {
      try {
        const data = await request(`/admin/showrooms/availability?movie_id=${encodeURIComponent(movieId)}&start_time=${encodeURIComponent(startISO)}`);
        if (!cancelled) setRooms(data.showrooms || []);
      } catch (err) {
        if (!cancelled) { setRooms([]); setRoomError(err.message || "Could not check available screens."); }
      } finally {
        if (!cancelled) setLoadingRooms(false);
      }
    }, 250);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [movieId, startISO, request, checkVersion]);

  const availableRooms = rooms.filter((room) => room.available);
  const pickedRoom = rooms.find((room) => room.showroom_id === roomId);
  const selectedMovie = movies.find((movie) => String(movie.tmdb_id) === movieId);

  function resetSelection(field, value) {
    if (field === "movie") setMovieId(value);
    if (field === "time") setLocalTime(value);
    setRoomId(""); setRooms([]); setFailure(""); setSaved(null);
    setErrors({});
  }

  async function submit(event) {
    event.preventDefault();
    const invalid = {};
    if (!movieId) invalid.movie_id = "Select the movie to schedule.";
    if (!startISO) invalid.start_time = "Choose a future date and time.";
    if (!roomId || !pickedRoom?.available) invalid.showroom_id = "Choose a free screen.";
    setErrors(invalid); setFailure(""); setSaved(null);
    if (Object.keys(invalid).length) return;
    setBusy(true);
    try {
      const result = await request("/admin/showtimes", {
        method: "POST", body: { movie_id: Number(movieId), showroom_id: roomId, start_time: startISO },
      });
      setSaved(result.showtime);
      setRoomId("");
      setCheckVersion((value) => value + 1); // re-query so the newly reserved room is disabled
      refreshCatalog();
    } catch (err) {
      setErrors(err.fields || {});
      const conflictTime = err.conflict?.start_time ? ` Existing show: ${humanDate(err.conflict.start_time)}.` : "";
      setFailure(`${err.message || "Unable to schedule the movie."}${conflictTime}`);
      setCheckVersion((value) => value + 1);
    } finally { setBusy(false); }
  }

  return <section className="admin-workspace" aria-labelledby="admin-schedule-title">
    <div className="admin-workspace-heading"><CalendarClock size={21} /><div>
      <h2 id="admin-schedule-title">Schedule a Movie</h2>
      <p>Choose a movie and start time, then select an available room. Conflicts are checked again when you save.</p>
    </div></div>
    <form onSubmit={submit} noValidate>
      <div className="admin-form-grid">
        <Field id="movie_id" label="Movie" options={movies.map((movie) => ({ value: String(movie.tmdb_id), label: movie.title }))} value={movieId}
          onChange={(e) => resetSelection("movie", e.target.value)} error={errors.movie_id} />
        <Field id="start_time" label="Start date and time" type="datetime-local" min={futureLocalMin()}
          value={localTime} onChange={(e) => resetSelection("time", e.target.value)} error={errors.start_time} />
      </div>
      {selectedMovie && <p className="admin-muted">Selected: <strong>{selectedMovie.title}</strong> ({selectedMovie.runtime || 120} min)
        {localTime && startISO && <> · {humanDate(startISO)}</>}</p>}
      {!startISO && localTime && <p className="admin-error" role="alert">Select a future showtime.</p>}
      <div className="admin-room-section">
        <h3>Available screens</h3>
        {!movieId || !startISO ? <p className="admin-muted">Choose a movie and future start time to check room availability.</p>
          : loadingRooms ? <p className="admin-muted" role="status">Checking screens…</p>
          : roomError ? <p className="admin-error" role="alert">{roomError}</p>
          : !rooms.length ? <p className="admin-muted">No showrooms are configured.</p>
          : <div className="admin-room-list" role="radiogroup" aria-label="Choose an available screen">
            {rooms.map((room) => <label key={room.showroom_id}
              className={`admin-room ${room.available ? "admin-room-free" : "admin-room-taken"} ${roomId === room.showroom_id ? "admin-room-picked" : ""}`}>
              <input type="radio" name="showroom" value={room.showroom_id} checked={roomId === room.showroom_id}
                disabled={!room.available || busy} onChange={() => { setRoomId(room.showroom_id); setErrors((old) => ({ ...old, showroom_id: undefined })); setFailure(""); setSaved(null); }} />
              <span><strong>{room.name}</strong>{room.seat_count && <small>{room.seat_count} seats</small>}</span>
              <em>{room.available ? "Available" : "Conflict · Occupied"}</em>
            </label>)}
          </div>}
        {!loadingRooms && rooms.length > 0 && availableRooms.length === 0 &&
          <p className="admin-error" role="alert">All screens conflict with this time. Choose a different date or start time.</p>}
        {errors.showroom_id && <p className="admin-error" role="alert">{errors.showroom_id}</p>}
      </div>
      <Feedback error={failure} success={saved && `Showtime scheduled for ${selectedMovie?.title || "the movie"} on ${humanDate(saved.start_time || startISO)}.`} />
      <button className="admin-primary" type="submit" disabled={busy || loadingRooms || !roomId || !pickedRoom?.available}>
        {busy ? "Saving showtime…" : "Schedule Movie"}
      </button>
    </form>
  </section>;
}

// Sprint 3 admin portal. The existing main.jsx owns the route/auth hook;
// this component only accepts the token the hook already authenticated.
export default function AdminHome({ user, navigate, onLogout, token }) {
  const [active, setActive] = useState("home");
  const [catalog, setCatalog] = useState({ movies: [], genres: FALLBACK_GENRES, ratings: FALLBACK_RATINGS, statuses: FALLBACK_STATUSES });
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [scheduleMovieId, setScheduleMovieId] = useState(null);

  const request = useCallback(async (path, { method = "GET", body } = {}) => {
    if (!token) throw new Error("Sign in again to manage cinema listings.");
    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}`, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    } catch {
      throw new Error("Couldn't connect to the cinema API. Check that Flask is running.");
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(result.error || `Request failed (${response.status}).`);
      error.status = response.status;
      error.fields = result.errors || {};
      error.conflict = result.conflict;
      throw error;
    }
    return result;
  }, [token]);

  const refreshCatalog = useCallback(async () => {
    try {
      setCatalogError("");
      const result = await request("/admin/catalog");
      setCatalog(result);
    } catch (err) { setCatalogError(err.message); }
    finally { setLoadingCatalog(false); }
  }, [request]);

  useEffect(() => { refreshCatalog(); }, [refreshCatalog]);

  function onMovieCreated(movie, schedule = false) {
    if (movie) setCatalog((old) => ({ ...old, movies: [...old.movies.filter((m) => m.tmdb_id !== movie.tmdb_id), movie] }));
    if (schedule) { setScheduleMovieId(movie.tmdb_id); setActive("schedule"); }
  }

  return (
    <div className="account-screen">
      <header className="account-header">
        <button type="button" className="account-back" onClick={() => navigate("/")}>
          <ArrowLeft size={17} /> View site
        </button>
        <div className="header-actions">
          <span className="account-wordmark">CINEMA ADMIN</span>
          <button type="button" className="header-logout" onClick={onLogout}><LogOut size={14} /> Logout</button>
        </div>
      </header>
      <main className="account-panel account-panel-wide admin-panel">
        <div className="admin-intro">
          <div className="account-panel-icon"><ShieldCheck size={24} /></div>
          <div><h1>Admin Portal</h1>
            <p className="account-subtitle">Signed in as {user?.first_name} {user?.last_name} ({user?.email}).</p>
          </div>
        </div>
        {active !== "home" && <button type="button" className="admin-back" onClick={() => setActive("home")}>
          <ArrowLeft size={15} /> Back to admin menu</button>}
        {active === "home" && <div className="admin-grid">
          {MENU.map(({ key, label, icon: Icon, description }) => (
            <button key={key} type="button" className="admin-tile" onClick={() => setActive(key)}>
              <Icon size={22} /><strong>{label}</strong><span>{description}</span>
            </button>
          ))}
        </div>}
        {(active === "add" || active === "schedule") && <>
          {loadingCatalog ? <p className="admin-muted" role="status">Loading movie catalog…</p> :
            catalogError ? <div className="admin-feedback admin-feedback-error" role="alert">{catalogError} <button type="button" onClick={refreshCatalog}>Retry</button></div> :
            active === "add" ? <AddMovieForm catalog={catalog} request={request} onMovieCreated={onMovieCreated} /> :
              <ScheduleMovieForm catalog={catalog} request={request} initialMovieId={scheduleMovieId} refreshCatalog={refreshCatalog} />}
        </>}
        {(active === "promotions" || active === "users") && <section className="admin-workspace">
          <h2>{MENU.find((m) => m.key === active)?.label}</h2>
          <p className="admin-muted">This area is outside the Add Movie and Schedule a Movie assignment and is not implemented yet.</p>
        </section>}
      </main>
    </div>
  );
}
