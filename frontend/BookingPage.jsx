import React, { useState } from "react";
import {
  Clapperboard,
  Check,
  CalendarDays,
  Clock3,
  Armchair,
  User,
  ArrowLeft
} from "lucide-react";
export default function BookingPage({ movie, onBack }) {
  
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
