import { useEffect, useState, type FormEvent } from "react";
import { Eye, EyeOff, KeyRound, LoaderCircle, MailCheck, UserRoundPlus } from "lucide-react";
import { useAuth } from "../app/AuthContext";
import type { ApiError } from "../services/api";

export function AuthPanel() {
  const { signIn, register, verifyEmail, resendVerification } = useAuth();
  const [mode, setMode] = useState<"login" | "register" | "verify">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [code, setCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendAfter, setResendAfter] = useState(0);

  useEffect(() => {
    if (resendAfter <= 0) return;
    const timer = window.setTimeout(() => setResendAfter(value => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [resendAfter]);

  async function resend() {
    setBusy(true); setError(null); setMessage(null);
    try {
      const result = await resendVerification(email, password);
      setMessage(result.message); setResendAfter(result.resend_after_seconds); setCode("");
    } catch (cause) {
      const failure = cause as ApiError;
      if (failure.retryAfter) setResendAfter(failure.retryAfter);
      setError(failure.message || "Could not send a code. Please try again.");
    } finally { setBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null);
    if (mode === "register" && password !== confirmPassword) {
      setError("Passwords do not match. Please check both fields."); return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        const result = await register(email, password, confirmPassword);
        if (!result.verification_required) {
          setMode("login"); setMessage(result.message);
          setConfirmPassword(""); setShowPassword(false); setShowConfirmation(false);
          await signIn(email, password);
          return;
        }
        setMode("verify"); setMessage(result.message); setResendAfter(result.resend_after_seconds);
        setConfirmPassword(""); setShowPassword(false); setShowConfirmation(false);
      } else if (mode === "verify") await verifyEmail(email, password, code);
      else await signIn(email, password);
    } catch (cause) {
      const failure = cause as ApiError;
      if (mode === "login" && failure.code === "email_verification_required") {
        setMode("verify"); setShowPassword(false);
        setMessage("Your email needs verification. Enter your code, or request a new one below.");
      } else setError(failure.message || "Could not continue. Please try again.");
    } finally { setBusy(false); }
  }

  function switchMode() {
    setMode(mode === "login" ? "register" : "login");
    setPassword(""); setConfirmPassword(""); setCode("");
    setShowPassword(false); setShowConfirmation(false); setError(null); setMessage(null);
  }

  return <section className="surface-card auth-card">
    <span className="auth-icon">{mode === "verify" ? <MailCheck size={18} /> : mode === "login" ? <KeyRound size={18} /> : <UserRoundPlus size={18} />}</span>
    <span className="section-kicker">YOUR PRIVATE WORKSPACE</span>
    <h2>{mode === "verify" ? "Verify your email" : mode === "login" ? "Sign in to your portfolio" : "Create your account"}</h2>
    <p>{mode === "verify" ? `Verify ${email} to access your private portfolio.` : "Portfolio records are private to your account. Sign in or create an account to continue."}</p>
    {message && <p role="status">{message}</p>}
    <form onSubmit={submit} className="auth-form">
      {mode === "verify" ? <div className="auth-field">
        <label htmlFor="verification-code">Email verification code</label>
        <input id="verification-code" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required value={code} onChange={event => setCode(event.target.value)} aria-describedby="code-help" />
        <small id="code-help">Enter the six-digit code from your email. Codes expire after 10 minutes. Check your spam folder too.</small>
      </div> : <>
        <label htmlFor="auth-email">Email address<input id="auth-email" type="email" autoComplete="email" required maxLength={320} value={email} onChange={event => setEmail(event.target.value)} /></label>
        <div className="auth-field">
          <label htmlFor="auth-password">Password</label>
          <div className="password-input">
            <input id="auth-password" type={showPassword ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 12 : 1} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} aria-describedby={mode === "register" ? "password-help" : undefined} />
            <button type="button" className="password-toggle" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button>
          </div>
          {mode === "register" && <small id="password-help">Use 12-128 characters.</small>}
        </div>
        {mode === "register" && <div className="auth-field">
          <label htmlFor="auth-confirm-password">Confirm password</label>
          <div className="password-input">
            <input id="auth-confirm-password" type={showConfirmation ? "text" : "password"} autoComplete="new-password" minLength={12} maxLength={128} required value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} aria-invalid={confirmPassword.length > 0 && password !== confirmPassword} />
            <button type="button" className="password-toggle" aria-label={showConfirmation ? "Hide confirmed password" : "Show confirmed password"} aria-pressed={showConfirmation} onClick={() => setShowConfirmation(value => !value)}>{showConfirmation ? <EyeOff size={18} /> : <Eye size={18} />}</button>
          </div>
        </div>}
      </>}
      {error && <div className="inline-error" role="alert">{error}</div>}
      <button className="button button-primary auth-submit" type="submit" disabled={busy}>{busy && <LoaderCircle className="spin" size={15} />}{mode === "verify" ? "Verify email and continue" : mode === "login" ? "Sign in" : "Create account"}</button>
    </form>
    {mode === "verify" && <button className="auth-switch" type="button" disabled={busy || resendAfter > 0} onClick={() => void resend()}>{resendAfter > 0 ? `Resend code in ${resendAfter}s` : "Send a new code"}</button>}
    <button className="auth-switch" type="button" disabled={busy} onClick={switchMode}>
      {mode === "verify" ? "Back to sign in / change email" : mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
    </button>
  </section>;
}
