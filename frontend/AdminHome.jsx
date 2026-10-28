import React, { useState } from "react";
import { Film, Percent, Users, CalendarClock, LogOut, ArrowLeft, ShieldCheck } from "lucide-react";
import "./account-pages.css";

const MENU = [
  { key: "movies", label: "Manage Movies", icon: Film, text: "Add, update, and delete movie listings." },
  { key: "promotions", label: "Promotions", icon: Percent, text: "Create promo codes and send promotions." },
  { key: "users", label: "Users", icon: Users, text: "Manage, suspend, and add user accounts." },
  { key: "showtimes", label: "Showtimes", icon: CalendarClock, text: "Schedule showtimes and set ticket prices." },
];

// Admin portal home (prototype only for Sprint 2).
export default function AdminHome({ user, navigate, onLogout }) {
  const [note, setNote] = useState("");

  return (
    <div className="account-screen">
      <header className="account-header">
        <button type="button" className="account-back" onClick={() => navigate("/")}>
          <ArrowLeft size={17} />
          View site
        </button>

        <div className="header-actions">
          <span className="account-wordmark">CINEMA ADMIN</span>
          <button type="button" className="header-logout" onClick={onLogout}>
            <LogOut size={14} />
            Logout
          </button>
        </div>
      </header>

      <main className="account-panel account-panel-wide">
        <div className="account-panel-icon">
          <ShieldCheck size={24} />
        </div>

        <h1>Admin Portal</h1>
        <p className="account-subtitle">
          Signed in as {user?.first_name} {user?.last_name} ({user?.email}).
        </p>

        <div className="admin-grid">
          {MENU.map(({ key, label, icon: Icon, text }) => (
            <button
              key={key}
              type="button"
              className="admin-tile"
              onClick={() => setNote(`${label} is a prototype in this sprint and will be built in a later sprint.`)}
            >
              <Icon size={22} />
              <strong>{label}</strong>
              <span>{text}</span>
            </button>
          ))}
        </div>

        {note && (
          <p role="status" className="account-alert account-alert-success admin-note">
            {note}
          </p>
        )}
      </main>
    </div>
  );
}
