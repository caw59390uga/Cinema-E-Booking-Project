import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Clapperboard, CalendarDays, Clock3, Armchair, User,
  ArrowLeft, CreditCard, Mail, AlertCircle, CheckCircle2,
} from "lucide-react";
import "./BookingPageExtras.css";
import "./BookingPageLive.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000/api";
const MAX_TICKETS = 8;
const TICKET_ORDER = ["Adult", "Child", "Senior"];
const DRAFT_KEY = "cinema_booking_draft";
const GUEST_KEY = "cinema_guest_id";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* ---------- small helpers ---------- */

const enc = encodeURIComponent;
const pad = (n) => String(n).padStart(2, "0");
const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const money = (n) => `$${(Number(n) || 0).toFixed(2)}`;
const dayKey = (iso) => {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const dayLabel = (iso) =>
  new Date(iso).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
const timeLabel = (iso) =>
  new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const sumCounts = (counts) => Object.values(counts).reduce((s, n) => s + n, 0);

function normalizeCounts(raw) {
  const counts = {
    Adult: Math.max(0, Math.floor(Number(raw?.Adult) || 0)),
    Child: Math.max(0, Math.floor(Number(raw?.Child) || 0)),
    Senior: Math.max(0, Math.floor(Number(raw?.Senior) || 0)),
  };
  const total = sumCounts(counts);
  return total >= 1 && total <= MAX_TICKETS ? counts : { Adult: 1, Child: 0, Senior: 0 };
}

// Browser storage can be unavailable or empty, so every access is wrapped.
function readDraft() {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
function writeDraft(value) {
  try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify(value)); } catch { /* ignore */ }
}
function clearDraft() {
  try { sessionStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
}

let memoryGuestId = null;
function randomId() {
  const raw = (typeof crypto !== "undefined" && crypto.randomUUID)
    ? crypto.randomUUID()
    : `${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
  return raw.replace(/[^a-zA-Z0-9-]/g, "");
}
// Guests reserve seats under a "guest_..." id that lasts for the browser tab.
function getGuestId() {
  if (memoryGuestId) return memoryGuestId;
  try {
    const saved = sessionStorage.getItem(GUEST_KEY);
    if (saved) { memoryGuestId = saved; return saved; }
  } catch { /* ignore */ }
  memoryGuestId = `guest_${randomId()}`;
  try { sessionStorage.setItem(GUEST_KEY, memoryGuestId); } catch { /* ignore */ }
  return memoryGuestId;
}

/* ---------- the page ---------- */

export default function BookingPage({ movie, onBack, auth, navigate, notify, initialShowtimeId }) {
  const token = auth?.token || null;
  const loggedIn = Boolean(auth?.isAuthenticated && token);
  const authReady = !auth?.initializing;
  const guestId = useMemo(() => getGuestId(), []);
  const ownerBody = useMemo(() => (loggedIn ? {} : { holder_id: guestId }), [loggedIn, guestId]);

  // A draft exists only when a guest was sent to the login page mid-booking.
  const draft = useMemo(() => {
    const saved = readDraft();
    return saved && saved.movieId === movie.tmdb_id ? saved : null;
  }, [movie.tmdb_id]);

  const showtimes = useMemo(
    () => (movie.showtimes || [])
      .filter((s) => s && typeof s === "object" && s.showtime_id && s.start_time
        && new Date(s.start_time).getTime() > Date.now())
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time)),
    [movie.showtimes],
  );

  const [showtimeId, setShowtimeId] = useState(() => {
    const wanted = initialShowtimeId || draft?.showtimeId;
    if (wanted && showtimes.some((s) => s.showtime_id === wanted)) return wanted;
    return showtimes[0]?.showtime_id || null;
  });
  const [ticketCounts, setTicketCounts] = useState(() => normalizeCounts(draft?.ticketCounts));
  const [selectedSeats, setSelectedSeatsState] = useState([]);
  const [seatData, setSeatData] = useState(null);
  const [seatLoading, setSeatLoading] = useState(false);
  const [seatError, setSeatError] = useState("");
  const [pricing, setPricing] = useState(null);
  const [pricingError, setPricingError] = useState("");
  const [step, setStep] = useState("select"); // select -> summary -> payment
  const [summary, setSummary] = useState(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [paymentNote, setPaymentNote] = useState(false);
  const [transferring, setTransferring] = useState(Boolean(draft?.pendingLogin));

  const selectedRef = useRef([]);
  const holdQueue = useRef(Promise.resolve());
  const transferRan = useRef(false);

  function setSeats(next) {
    selectedRef.current = next;
    setSelectedSeatsState(next);
  }

  const ticketCount = sumCounts(ticketCounts);
  const selectedShowtime = showtimes.find((s) => s.showtime_id === showtimeId) || null;
  const selectedDay = selectedShowtime ? dayKey(selectedShowtime.start_time) : null;
  const days = useMemo(() => {
    const seen = [];
    showtimes.forEach((s) => { const k = dayKey(s.start_time); if (!seen.includes(k)) seen.push(k); });
    return seen;
  }, [showtimes]);
  const timesForDay = showtimes.filter((s) => dayKey(s.start_time) === selectedDay);

  /* ----- API ----- */

  const request = useCallback(async (path, { method = "GET", body } = {}) => {
    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    } catch {
      throw new Error("Couldn't reach the cinema API. Check that Flask is running.");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || `Request failed (${response.status}).`);
      error.status = response.status;
      error.reason = data.reason;
      throw error;
    }
    return data;
  }, [token]);

  // Prices, booking fee and tax come from the database, never from this file.
  useEffect(() => {
    let alive = true;
    setPricingError("");
    request("/pricing")
      .then((data) => { if (alive) setPricing(data); })
      .catch((err) => { if (alive) setPricingError(err.message); });
    return () => { alive = false; };
  }, [request]);

  // Loads the seat map. Seats this visitor already holds come back as "selected".
  const loadSeats = useCallback(async (id) => {
    if (!id) return null;
    setSeatLoading(true);
    setSeatError("");
    try {
      const query = loggedIn ? "" : `?holder_id=${enc(guestId)}`;
      const data = await request(`/showtimes/${enc(id)}/seats${query}`);
      setSeatData(data);
      const mine = (data.seats || []).filter((s) => s.status === "selected").map((s) => s.seat_id);
      setSeats(mine);
      if (mine.length) {
        setTicketCounts((prev) => (sumCounts(prev) === mine.length
          ? prev : { Adult: mine.length, Child: 0, Senior: 0 }));
      }
      return data;
    } catch (err) {
      setSeatData(null);
      setSeatError(err.message);
      return null;
    } finally {
      setSeatLoading(false);
    }
  }, [request, loggedIn, guestId]);

  useEffect(() => {
    if (!authReady || transferring) return;
    loadSeats(showtimeId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showtimeId, authReady, transferring, loggedIn]);

  const goToSummary = useCallback(async (id, seats, counts) => {
    const tickets = Object.fromEntries(Object.entries(counts).filter(([, n]) => n > 0));
    const data = await request("/booking/summary", {
      method: "POST", body: { showtime_id: id, seat_ids: seats, tickets },
    });
    setSummary(data);
    setEmail(data.user?.email || "");
    setStep("summary");
    return data;
  }, [request]);

  // After login: move the guest's reserved seats to the account, then continue checkout.
  useEffect(() => {
    if (!transferring || !authReady || transferRan.current) return;
    transferRan.current = true;
    (async () => {
      if (!loggedIn) {
        writeDraft({ ...draft, pendingLogin: false });
        setTransferring(false);
        return;
      }
      let moved = 0;
      try {
        const res = await request("/booking/transfer-holds", {
          method: "POST", body: { showtime_id: draft.showtimeId, guest_session_id: draft.guestId },
        });
        moved = res.transferred || 0;
      } catch (err) {
        setNotice(err.message);
      }
      writeDraft({ ...draft, pendingLogin: false });
      setTransferring(false);
      const data = await loadSeats(draft.showtimeId);
      const mine = (data?.seats || []).filter((s) => s.status === "selected").map((s) => s.seat_id);
      if (moved > 0 && mine.length === moved && draft.showtimeId === showtimeId) {
        const counts = sumCounts(normalizeCounts(draft.ticketCounts)) === mine.length
          ? normalizeCounts(draft.ticketCounts)
          : { Adult: mine.length, Child: 0, Senior: 0 };
        try {
          await goToSummary(draft.showtimeId, mine, counts);
        } catch (err) {
          setNotice(err.message);
        }
      } else if (draft.seats?.length) {
        setNotice("Some of your reserved seats were released. Please choose your seats again.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transferring, authReady, loggedIn]);

  // Reserves the current selection (replacing earlier holds). Calls run one at a time.
  const syncHold = useCallback((next) => {
    holdQueue.current = holdQueue.current.then(async () => {
      try {
        if (next.length === 0) {
          await request(`/showtimes/${enc(showtimeId)}/release`, { method: "POST", body: ownerBody });
        } else {
          await request(`/showtimes/${enc(showtimeId)}/hold`, {
            method: "POST", body: { seat_ids: next, ...ownerBody },
          });
        }
      } catch (err) {
        setNotice(err.message);
        await loadSeats(showtimeId);
      }
    });
    return holdQueue.current;
  }, [request, showtimeId, ownerBody, loadSeats]);

  /* ----- actions ----- */

  function chooseShowtime(id) {
    if (id === showtimeId) return;
    if (selectedRef.current.length) {
      const old = showtimeId;
      holdQueue.current = holdQueue.current.then(() =>
        request(`/showtimes/${enc(old)}/release`, { method: "POST", body: ownerBody }).catch(() => {}));
    }
    setSeats([]);
    setNotice("");
    setShowtimeId(id);
  }

  function chooseDay(key) {
    const first = showtimes.find((s) => dayKey(s.start_time) === key);
    if (first) chooseShowtime(first.showtime_id);
  }

  function updateTicketCount(type, delta) {
    const next = ticketCounts[type] + delta;
    const nextTotal = ticketCount + delta;
    if (next < 0 || nextTotal > MAX_TICKETS || nextTotal < 1) return;
    setTicketCounts((current) => ({ ...current, [type]: next }));
    setNotice("");
    if (delta < 0 && selectedRef.current.length > nextTotal) {
      const trimmed = selectedRef.current.slice(0, nextTotal);
      setSeats(trimmed);
      syncHold(trimmed);
    }
  }

  function toggleSeat(seat) {
    if (busy || seat.status === "booked") return;
    setNotice("");
    const current = selectedRef.current;
    let next;
    if (current.includes(seat.seat_id)) {
      next = current.filter((id) => id !== seat.seat_id);
    } else {
      if (current.length >= ticketCount) {
        setNotice(`You chose ${ticketCount} ticket${ticketCount !== 1 ? "s" : ""}. Add tickets above to pick more seats.`);
        return;
      }
      next = [...current, seat.seat_id];
    }
    setSeats(next);
    syncHold(next);
  }

  async function proceedToCheckout() {
    setNotice("");
    if (!showtimeId) { setNotice("Choose a showtime first."); return; }
    setBusy(true);
    try {
      await holdQueue.current;
      const seats = selectedRef.current;
      if (seats.length !== ticketCount) {
        setNotice(`Select exactly ${ticketCount} seat${ticketCount !== 1 ? "s" : ""} to match your tickets.`);
        return;
      }
      if (!loggedIn) {
        writeDraft({
          movieId: movie.tmdb_id, showtimeId, ticketCounts,
          seats, guestId, pendingLogin: true,
        });
        notify?.("Please sign in to continue to checkout. Your seats stay reserved.", "info");
        if (navigate) navigate("/login");
        else setNotice("Please sign in to continue to checkout.");
        return;
      }
      await goToSummary(showtimeId, seats, ticketCounts);
    } catch (err) {
      setNotice(err.message);
      await loadSeats(showtimeId);
    } finally {
      setBusy(false);
    }
  }

  function continueToPayment(event) {
    event.preventDefault();
    if (!EMAIL_PATTERN.test(email.trim())) {
      setNotice("Enter a valid email address for your confirmation.");
      return;
    }
    setNotice("");
    setStep("payment");
  }

  function leave() {
    if (selectedRef.current.length && showtimeId) {
      holdQueue.current = holdQueue.current.then(() =>
        request(`/showtimes/${enc(showtimeId)}/release`, { method: "POST", body: ownerBody }).catch(() => {}));
    }
    clearDraft();
    onBack();
  }

  /* ----- derived display data ----- */

  const ticketTypes = pricing ? TICKET_ORDER.filter((t) => t in pricing.prices) : [];

  const rows = useMemo(() => {
    const byRow = new Map();
    (seatData?.seats || []).forEach((seat) => {
      if (!byRow.has(seat.row)) byRow.set(seat.row, []);
      byRow.get(seat.row).push(seat);
    });
    return [...byRow.entries()].map(([row, seats]) => ({
      row, seats: seats.sort((a, b) => a.number - b.number),
    }));
  }, [seatData]);

  const preview = useMemo(() => {
    if (!pricing) return null;
    const lines = ticketTypes
      .filter((t) => ticketCounts[t] > 0)
      .map((t) => ({
        type: t, count: ticketCounts[t], price: pricing.prices[t],
        subtotal: round2(ticketCounts[t] * pricing.prices[t]),
      }));
    const subtotal = round2(lines.reduce((s, l) => s + l.subtotal, 0));
    const fee = round2(pricing.booking_fee);
    const tax = round2(subtotal * pricing.tax_rate);
    return { lines, subtotal, fee, tax, total: round2(subtotal + fee + tax) };
  }, [pricing, ticketCounts]); // eslint-disable-line react-hooks/exhaustive-deps

  // After checkout starts, show the server's numbers so the screen always matches the backend.
  const view = summary && step !== "select"
    ? {
      lines: summary.ticket_breakdown.map((b) => ({
        type: b.type, count: b.count, price: b.price_per_ticket, subtotal: b.subtotal,
      })),
      subtotal: summary.total_before_tax, fee: summary.booking_fee,
      tax: summary.sales_tax, total: summary.grand_total,
    }
    : preview;

  const shownShowtime = summary && step !== "select" ? summary.showtime : selectedShowtime;
  const shownSeats = summary && step !== "select" ? summary.selected_seats : selectedSeats;

  /* ----- render ----- */

  return (
    <div className="booking-page">
      <header className="nav">
        <div className="nav-inner">
          <button className="brand" onClick={leave}>
            <span className="brand-icon"><Clapperboard size={19} /></span>
            <span>CINEMA</span>
          </button>
        </div>
      </header>

      <main className="booking-container">
        <button className="back-button" onClick={leave}>
          <ArrowLeft size={17} />
          Back to movies
        </button>

        <div className="booking-heading">
          <div>
            <p className="section-kicker">BOOK TICKETS</p>
            <h1>{movie.title}</h1>
            <p>{movie.genre} · {movie.rating}</p>
          </div>
        </div>

        {notice && (
          <p className="booking-notice booking-notice-error" role="alert">
            <AlertCircle size={16} /> {notice}
          </p>
        )}
        {pricingError && (
          <p className="booking-notice booking-notice-error" role="alert">
            <AlertCircle size={16} /> {pricingError}
          </p>
        )}

        {transferring ? (
          <p className="booking-muted" role="status">Restoring your reserved seats…</p>
        ) : showtimes.length === 0 ? (
          <div className="booking-section">
            <p className="booking-muted">
              No upcoming showtimes are scheduled for this movie yet. Please check back soon.
            </p>
          </div>
        ) : (
          <div className="booking-layout">
            <section className="booking-main">

              {step === "select" && <>
                <div className="booking-section">
                  <div className="booking-section-title">
                    <CalendarDays size={19} />
                    <div><h2>Choose a date</h2><p>Select your show date</p></div>
                  </div>
                  <div className="date-options">
                    {days.map((key) => {
                      const first = showtimes.find((s) => dayKey(s.start_time) === key);
                      return (
                        <button key={key} type="button"
                          className={selectedDay === key ? "date-card selected" : "date-card"}
                          onClick={() => chooseDay(key)}>
                          <span>{dayLabel(first.start_time)}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="booking-section">
                  <div className="booking-section-title">
                    <Clock3 size={19} />
                    <div><h2>Choose a showtime</h2><p>Select your preferred time</p></div>
                  </div>
                  <div className="booking-times">
                    {timesForDay.map((s) => (
                      <button key={s.showtime_id} type="button"
                        className={showtimeId === s.showtime_id ? "booking-time selected" : "booking-time"}
                        onClick={() => chooseShowtime(s.showtime_id)}>
                        {timeLabel(s.start_time)}
                        {s.showroom_name && <small className="booking-time-room">{s.showroom_name}</small>}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="booking-section">
                  <div className="booking-section-title">
                    <User size={19} />
                    <div><h2>Choose ticket types</h2><p>Select 1–8 Adult, Child, or Senior tickets</p></div>
                  </div>
                  <div className="ticket-types">
                    {ticketTypes.map((type) => (
                      <div className="ticket-type-row" key={type}>
                        <div><strong>{type}</strong><span>{money(pricing.prices[type])} each</span></div>
                        <div className="ticket-quantity">
                          <button type="button" aria-label={`Remove ${type} ticket`}
                            disabled={ticketCounts[type] === 0 || ticketCount === 1}
                            onClick={() => updateTicketCount(type, -1)}>−</button>
                          <strong>{ticketCounts[type]}</strong>
                          <button type="button" aria-label={`Add ${type} ticket`}
                            disabled={ticketCount >= MAX_TICKETS}
                            onClick={() => updateTicketCount(type, 1)}>+</button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="ticket-seat-hint">
                    {ticketCount} ticket{ticketCount !== 1 ? "s" : ""} — select {ticketCount} seat{ticketCount !== 1 ? "s" : ""} below.
                  </p>
                </div>

                <div className="booking-section">
                  <div className="booking-section-title">
                    <Armchair size={19} />
                    <div>
                      <h2>Choose your seats</h2>
                      <p>
                        Select exactly {ticketCount} seat{ticketCount !== 1 ? "s" : ""}
                        {seatData?.showroom?.name ? ` · ${seatData.showroom.name}` : ""}
                      </p>
                    </div>
                  </div>

                  {seatLoading && !seatData ? (
                    <p className="booking-muted" role="status">Loading seat map…</p>
                  ) : seatError ? (
                    <p className="booking-notice booking-notice-error" role="alert">
                      <AlertCircle size={16} /> {seatError}
                    </p>
                  ) : (
                    <>
                      <div className="screen">SCREEN</div>
                      <div className="seat-map">
                        {rows.map(({ row, seats }) => (
                          <div className="seat-row" key={row}>
                            <span className="row-label">{row}</span>
                            {seats.map((seat) => {
                              const chosen = selectedSeats.includes(seat.seat_id);
                              const taken = seat.status === "booked";
                              return (
                                <button key={seat.seat_id} type="button"
                                  className={chosen ? "seat selected" : taken ? "seat booked" : "seat"}
                                  disabled={taken}
                                  aria-label={`Seat ${seat.seat_id}${taken ? ", booked" : chosen ? ", selected" : ""}`}
                                  onClick={() => toggleSeat(seat)}>
                                  {seat.number}
                                </button>
                              );
                            })}
                          </div>
                        ))}
                      </div>
                      <div className="seat-legend">
                        <span><i className="legend available" />Available</span>
                        <span><i className="legend chosen" />Selected</span>
                        <span><i className="legend booked" />Booked</span>
                      </div>
                    </>
                  )}

                  <div className="booking-actions">
                    <button type="button" className="confirm-booking"
                      disabled={busy || seatLoading || !pricing || selectedSeats.length !== ticketCount}
                      onClick={proceedToCheckout}>
                      {busy ? "Please wait…" : "Proceed to Checkout"}
                    </button>
                    {!loggedIn && (
                      <p className="booking-muted">You can choose seats now. You'll be asked to sign in at checkout.</p>
                    )}
                  </div>
                </div>
              </>}

              {step === "summary" && summary && (
                <form className="booking-section" onSubmit={continueToPayment}>
                  <div className="booking-section-title">
                    <CheckCircle2 size={19} />
                    <div><h2>Order summary</h2><p>Review your order before payment</p></div>
                  </div>

                  <div className="order-lines">
                    <div className="summary-row"><span>Movie</span><strong>{summary.movie.title}</strong></div>
                    <div className="summary-row">
                      <span>Showtime</span>
                      <strong>{dayLabel(summary.showtime.start_time)} · {timeLabel(summary.showtime.start_time)}</strong>
                    </div>
                    {summary.showtime.showroom_name && (
                      <div className="summary-row"><span>Screen</span><strong>{summary.showtime.showroom_name}</strong></div>
                    )}
                    <div className="summary-row">
                      <span>Seats</span><strong>{[...summary.selected_seats].sort().join(", ")}</strong>
                    </div>
                    <div className="summary-divider" />
                    {summary.ticket_breakdown.map((b) => (
                      <div className="summary-row" key={b.type}>
                        <span>{b.type} × {b.count} @ {money(b.price_per_ticket)}</span>
                        <strong>{money(b.subtotal)}</strong>
                      </div>
                    ))}
                    <div className="summary-row"><span>Total before tax</span><strong>{money(summary.total_before_tax)}</strong></div>
                    <div className="summary-row"><span>Booking fee</span><strong>{money(summary.booking_fee)}</strong></div>
                    <div className="summary-row"><span>Sales tax</span><strong>{money(summary.sales_tax)}</strong></div>
                    <div className="summary-total"><span>Total</span><strong>{money(summary.grand_total)}</strong></div>
                  </div>

                  <div className="booking-section-title">
                    <Mail size={19} />
                    <div>
                      <h2>Confirmation email</h2>
                      <p>We'll send your order confirmation here. Change it if you'd like it sent elsewhere.</p>
                    </div>
                  </div>
                  <div className="input-grid">
                    <label>
                      Email address
                      <input type="email" value={email} required
                        onChange={(e) => { setEmail(e.target.value); setNotice(""); }}
                        placeholder="you@example.com" autoComplete="email" />
                    </label>
                  </div>

                  <div className="payment-actions">
                    <button type="button" className="back-button" onClick={() => setStep("select")}>
                      Back to seats
                    </button>
                    <button type="submit" className="confirm-booking" disabled={!email.trim()}>
                      Continue to Payment
                    </button>
                  </div>
                </form>
              )}

              {step === "payment" && summary && (
                <section className="booking-section payment-mockup">
                  <div className="booking-section-title">
                    <CreditCard size={19} />
                    <div><h2>Payment (Demo)</h2><p>Mockup only — no actual payment is processed.</p></div>
                  </div>
                  <p className="demo-warning">Use fictional test details only. Do not enter a real card number or CVV.</p>
                  <p className="booking-muted">Confirmation will be sent to <strong>{email.trim()}</strong>.</p>
                  <div className="payment-summary-line"><span>Amount due</span><strong>{money(summary.grand_total)}</strong></div>
                  <form onSubmit={(e) => { e.preventDefault(); setPaymentNote(true); }}>
                    <div className="input-grid">
                      <label>Cardholder name<input placeholder="Demo Customer" required autoComplete="off" /></label>
                      <label>Demo card number<input placeholder="4242 4242 4242 4242" inputMode="numeric" pattern="[0-9 ]{13,23}" required autoComplete="off" /></label>
                      <label>Expiration (MM/YY)<input placeholder="12/30" pattern="(0[1-9]|1[0-2])/[0-9]{2}" required autoComplete="off" /></label>
                      <label>Demo CVV<input placeholder="123" inputMode="numeric" pattern="[0-9]{3,4}" required autoComplete="off" /></label>
                    </div>
                    {paymentNote && (
                      <p className="booking-notice" role="status">
                        <CheckCircle2 size={16} /> Payment processing and the final order confirmation are part of the final demo.
                      </p>
                    )}
                    <div className="payment-actions">
                      <button type="button" className="back-button" onClick={() => { setPaymentNote(false); setStep("summary"); }}>
                        Back to order summary
                      </button>
                      <button type="submit" className="confirm-booking">
                        Submit Payment (Demo) — {money(summary.grand_total)}
                      </button>
                    </div>
                  </form>
                </section>
              )}
            </section>

            <aside className="booking-summary">
              <img src={movie.poster_url} alt={movie.title} />
              <div className="summary-content">
                <p className="section-kicker">YOUR ORDER</p>
                <h2>{movie.title}</h2>

                <div className="summary-row">
                  <span>Date</span>
                  <strong>{shownShowtime?.start_time ? dayLabel(shownShowtime.start_time) : "—"}</strong>
                </div>
                <div className="summary-row">
                  <span>Showtime</span>
                  <strong>{shownShowtime?.start_time ? timeLabel(shownShowtime.start_time) : "—"}</strong>
                </div>
                <div className="summary-row">
                  <span>Seats</span>
                  <strong>{shownSeats.length ? [...shownSeats].sort().join(", ") : "None selected"}</strong>
                </div>
                <div className="summary-row">
                  <span>Tickets / seats</span>
                  <strong>{ticketCount} / {shownSeats.length}</strong>
                </div>

                <div className="summary-divider" />

                {view?.lines.map((line) => (
                  <div className="summary-row" key={line.type}>
                    <span>{line.type} × {line.count}</span>
                    <strong>{money(line.subtotal)}</strong>
                  </div>
                ))}
                {view && <>
                  <div className="summary-row"><span>Booking fee</span><strong>{money(view.fee)}</strong></div>
                  <div className="summary-row"><span>Sales tax</span><strong>{money(view.tax)}</strong></div>
                  <div className="summary-total"><span>Total</span><strong>{money(view.total)}</strong></div>
                </>}
              </div>
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
