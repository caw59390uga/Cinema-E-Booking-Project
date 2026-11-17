import React, { useState } from "react";
import {
  Clapperboard,
  Check,
  CalendarDays,
  Clock3,
  Armchair,
  User,
  ArrowLeft, CreditCard
} from "lucide-react";
import "./BookingPageExtras.css";

export default function BookingPage({ movie, onBack }) {
  
  const [date, setDate] = useState("Today");
  const [time, setTime] = useState(movie.showtimes?.[0] || "2:00 PM");
  const [selectedSeats, setSelectedSeats] = useState([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [step, setStep] = useState("checkout");
  const [ticketCounts, setTicketCounts] = useState({ Adult: 1, Child: 0, Senior: 0 });
  const ticketPrices = { Adult: 13.5, Child: 9.5, Senior: 10.5 };
  const ticketCount = Object.values(ticketCounts).reduce((sum, n) => sum + n, 0);

  function updateTicketCount(type, delta) {
    const next = ticketCounts[type] + delta;
    const nextTotal = ticketCount + delta;
    if (next < 0 || nextTotal > 8 || nextTotal < 1) return;
    setTicketCounts((current) => ({ ...current, [type]: next }));
    if (delta < 0 && selectedSeats.length > nextTotal) {
      setSelectedSeats((current) => current.slice(0, nextTotal));
    }
  }

  const rows = ["A", "B", "C", "D", "E", "F"];
  const seatsPerRow = 10;

  const subtotal = Object.entries(ticketCounts).reduce(
    (sum, [type, count]) => sum + ticketPrices[type] * count, 0
  );
  const fee = ticketCount > 0 ? 2.5 : 0;
  const total = subtotal + fee;

  function toggleSeat(seat) {
    setSelectedSeats((current) => {
      if (current.includes(seat)) {
        return current.filter((s) => s !== seat);
      }

      if (current.length >= ticketCount) {
        return current;
      }

      return [...current, seat];
    });
  }

  function submitBooking(e) {
    e.preventDefault();

    if (
      selectedSeats.length !== ticketCount ||
      !time ||
      !name.trim() ||
      !email.trim()
    ) {
      return;
    }

    setStep("payment");
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
                {[...selectedSeats].sort().join(", ")}
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
                <User size={19} />
                <div>
                  <h2>Choose ticket types</h2>
                  <p>Select 1–8 Adult, Child, or Senior tickets</p>
                </div>
              </div>
              <div className="ticket-types">
                {Object.keys(ticketPrices).map((type) => (
                  <div className="ticket-type-row" key={type}>
                    <div><strong>{type}</strong><span>${ticketPrices[type].toFixed(2)} each</span></div>
                    <div className="ticket-quantity">
                      <button type="button" aria-label={`Remove ${type} ticket`}
                        disabled={ticketCounts[type] === 0 || ticketCount === 1}
                        onClick={() => updateTicketCount(type, -1)}>−</button>
                      <strong>{ticketCounts[type]}</strong>
                      <button type="button" aria-label={`Add ${type} ticket`}
                        disabled={ticketCount >= 8}
                        onClick={() => updateTicketCount(type, 1)}>+</button>
                    </div>
                  </div>
                ))}
              </div>
              <p className="ticket-seat-hint">{ticketCount} ticket{ticketCount !== 1 ? "s" : ""} — select {ticketCount} seat{ticketCount !== 1 ? "s" : ""} below.</p>
            </div>

            <div className="booking-section">

              <div className="booking-section-title">
                <Armchair size={19} />

                <div>
                  <h2>Choose your seats</h2>
                  <p>Select exactly {ticketCount} seat{ticketCount !== 1 ? "s" : ""}</p>
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


            {step === "checkout" && <form
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
                  selectedSeats.length !== ticketCount ||
                  !time ||
                  !name.trim() ||
                  !email.trim()
                }
              >
                Continue to Payment
              </button>

            </form>}

            {step === "payment" && (
              <section className="booking-section payment-mockup">
                <div className="booking-section-title">
                  <CreditCard size={19} />
                  <div><h2>Payment (Demo)</h2><p>Simulation only — no actual payment is processed.</p></div>
                </div>
                <p className="demo-warning">Use fictional test details only. Do not enter a real card number or CVV.</p>
                <div className="payment-summary-line"><span>Amount due</span><strong>${total.toFixed(2)}</strong></div>
                <form onSubmit={(e) => { e.preventDefault(); setConfirmed(true); }}>
                  <div className="input-grid">
                    <label>Cardholder name<input placeholder="Demo Customer" required autoComplete="off" /></label>
                    <label>Demo card number<input placeholder="4242 4242 4242 4242" inputMode="numeric" pattern="[0-9 ]{13,23}" required autoComplete="off" /></label>
                    <label>Expiration (MM/YY)<input placeholder="12/30" pattern="(0[1-9]|1[0-2])/[0-9]{2}" required autoComplete="off" /></label>
                    <label>Demo CVV<input placeholder="123" inputMode="numeric" pattern="[0-9]{3,4}" required autoComplete="off" /></label>
                  </div>
                  <div className="payment-actions">
                    <button type="button" className="back-button" onClick={() => setStep("checkout")}>Back to checkout</button>
                    <button type="submit" className="confirm-booking">Simulate Payment — ${total.toFixed(2)}</button>
                  </div>
                </form>
              </section>
            )}

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

              <div className="summary-row">
                <span>Tickets / seats</span>
                <strong>{ticketCount} / {selectedSeats.length}</strong>
              </div>

              <div className="summary-divider" />

              {Object.entries(ticketCounts).filter(([, count]) => count > 0).map(([type, count]) => (
                <div className="summary-row" key={type}>
                  <span>{type} × {count}</span>
                  <strong>${(ticketPrices[type] * count).toFixed(2)}</strong>
                </div>
              ))}

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
