import { useState } from "react";

import { loginUser, registerUser, setSession, clearSession } from "../services/api";

function AuthPanel({ username, onAuthenticated, onSignOut }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleChange = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      if (mode === "register") {
        await registerUser({ username: form.username, email: form.email, password: form.password });
      }
      const token = await loginUser({ username: form.username, password: form.password });
      setSession(token.access_token, form.username);
      onAuthenticated(form.username);
      setForm({ username: "", email: "", password: "" });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  if (username) {
    return (
      <div className="auth-panel auth-panel--signed-in">
        <div>
          <span className="auth-panel__label">Signed in as</span>
          <strong>{username}</strong>
        </div>
        <span className="auth-panel__hint">Scans are saved to your private history.</span>
        <button
          type="button"
          className="button button--ghost"
          onClick={() => {
            clearSession();
            onSignOut();
          }}
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <form className="auth-panel" onSubmit={handleSubmit}>
      <div className="auth-panel__intro">
        <strong>Save your scans</strong>
        <span>Sign in to keep a private prescription history.</span>
      </div>

      <div className="auth-panel__fields">
        <label className="field">
          <span>Username</span>
          <input name="username" value={form.username} onChange={handleChange} required />
        </label>
        {mode === "register" && (
          <label className="field">
            <span>Email</span>
            <input name="email" type="email" value={form.email} onChange={handleChange} required />
          </label>
        )}
        <label className="field">
          <span>Password</span>
          <input
            name="password"
            type="password"
            value={form.password}
            onChange={handleChange}
            minLength={8}
            required
          />
        </label>
      </div>

      <div className="auth-panel__actions">
        <button type="submit" className="button button--primary" disabled={busy}>
          {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "Create account" : "Back to sign in"}
        </button>
      </div>

      {error && <p className="auth-panel__error">{error}</p>}
    </form>
  );
}

export default AuthPanel;
