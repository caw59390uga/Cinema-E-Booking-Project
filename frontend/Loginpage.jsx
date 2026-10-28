import React, { useState } from 'react';
import { ArrowLeft, LockKeyhole } from 'lucide-react';
import './account-pages.css';

export default function LoginPage({
  onLogin,
  navigate,
  loading = false,
  authError = null
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);

    try {
      await onLogin(email.trim(), password);
    } catch (err) {
      setError(err.message || 'Unable to sign in.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-screen">
      <header className="account-header">
        <button
          type="button"
          className="account-back"
          onClick={() => navigate('/')}
        >
          <ArrowLeft size={17} />
          Movies
        </button>

        <span className="account-wordmark">
          CINEMA
        </span>
      </header>

      <main className="account-panel">
        <div className="account-panel-icon">
          <LockKeyhole size={24} />
        </div>

        <h1>Sign in</h1>

        <p className="account-subtitle">
          Welcome back to Cinema.
        </p>

        {(error || authError) && (
          <p
            role="alert"
            className="account-alert account-alert-error"
          >
            {error || authError}
          </p>
        )}

        <form
          className="account-form"
          onSubmit={handleSubmit}
        >
          <label className="account-field">
            Email address

            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
            />
          </label>

          <label className="account-field">
            Password

            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
            />
          </label>

          <button
            className="account-action"
            type="submit"
            disabled={busy || loading}
          >
            {busy || loading
              ? 'Signing in…'
              : 'Sign In'}
          </button>
        </form>

        <div className="account-links">
          <button
            className="account-text-link"
            type="button"
            onClick={() =>
              navigate('/account/forgot-password')
            }
          >
            Forgot password?
          </button>

          <button
            className="account-text-link"
            type="button"
            onClick={() =>
              navigate('/account/register')
            }
          >
            Create an account
          </button>
        </div>
      </main>
    </div>
  );
}
