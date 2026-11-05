import { useState, type FormEvent } from "react";
import { KeyRound, LoaderCircle, UserRoundPlus } from "lucide-react";
import { useAuth } from "../app/AuthContext";

export function AuthPanel() {
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") await register(email, password);
      else await signIn(email, password);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in. Please try again.");
    } finally { setBusy(false); }
  }

  return <section className="surface-card auth-card">
    <span className="auth-icon">{mode === "login" ? <KeyRound size={18} /> : <UserRoundPlus size={18} />}</span>
    <span className="section-kicker">YOUR PRIVATE WORKSPACE</span>
    <h2>{mode === "login" ? "Sign in to your portfolio" : "Create your account"}</h2>
    <p>Portfolio records are private to your account. Sign in or create an account to continue.</p>
    <form onSubmit={submit} className="auth-form">
      <label>Email address<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>Password<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 12 : 1} required value={password} onChange={(event) => setPassword(event.target.value)} />{mode === "register" && <small>Use at least 12 characters.</small>}</label>
      {error && <div className="inline-error" role="alert">{error}</div>}
      <button className="button button-primary auth-submit" type="submit" disabled={busy}>{busy && <LoaderCircle className="spin" size={15} />}{mode === "login" ? "Sign in" : "Create account"}</button>
    </form>
    <button className="auth-switch" type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
      {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
    </button>
  </section>;
}
