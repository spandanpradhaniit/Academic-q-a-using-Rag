import { useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Eye,
  EyeOff,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { demoCredentials, useMocks } from "../services/api";
import { Brand } from "./LandingPage";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const isRegister = mode === "register";
  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [terms, setTerms] = useState(false);
  const [remember, setRemember] = useState(true);
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [resetSent, setResetSent] = useState(false);
  const strength =
    password.length >= 12
      ? 3
      : password.length >= 8
      ? 2
      : password.length >= 5
      ? 1
      : 0;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (isRegister && password !== confirm)
      return setError("Those passwords do not match.");
    if (isRegister && !terms)
      return setError("Please accept the terms to create your account.");
    setBusy(true);
    try {
      if (isRegister) await signUp(name.trim(), email.trim(), password);
      else await signIn(email.trim(), password, remember);
      navigate(
        (location.state as { from?: { pathname?: string } } | null)?.from
          ?.pathname || "/app/dashboard",
        { replace: true }
      );
    } catch (requestError) {
      const response = (
        requestError as {
          response?: {
            data?: {
              detail?: unknown;
              error?: { message?: string };
            };
          };
        }
      ).response?.data;
      const detail = response?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(
          detail
            .map((item) =>
              typeof item === "object" && item !== null && "msg" in item
                ? String(item.msg)
                : ""
            )
            .filter(Boolean)
            .join(" ") || "Please check the submitted details and try again."
        );
      } else {
        setError(
          response?.error?.message ||
            "We could not connect to the account service. Please try again."
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-top">
        <Link to="/" aria-label="Back to Scholar home">
          <Brand />
        </Link>
        <Link className="auth-back" to="/">
          <ArrowLeft size={15} /> Back to home
        </Link>
      </div>
      <div className="auth-layout">
        <section className="auth-story">
          <div className="story-badge">
            <Sparkles size={13} /> A quieter way to do research
          </div>
          <h1>
            Make room for
            <br />
            <em>the good questions.</em>
          </h1>
          <p>
            Your academic reading, collected and ready to think with. Every
            answer points back to its source.
          </p>
          <div className="story-quote">
            <span className="quote-mark">“</span>
            <p>
              The ability to ask better questions is the beginning of wisdom.
            </p>
            <small>— Research notes, everywhere</small>
          </div>
          <div className="story-foot">
            <ShieldCheck size={16} /> Your documents stay yours.
          </div>
        </section>
        <section className="auth-card">
          <div className="auth-card-heading">
            <span className="auth-card-icon">
              <BookOpen size={18} />
            </span>
            <div>
              <h2>{isRegister ? "Create your account" : "Welcome back"}</h2>
              <p>
                {isRegister
                  ? "Start building your research library."
                  : "Your research library is ready when you are."}
              </p>
            </div>
          </div>
          <form className="auth-form" onSubmit={submit}>
            {isRegister && (
              <label>
                Full name
                <input
                  autoComplete="name"
                  placeholder="Alex Morgan"
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
            )}
            <label>
              Email address
              <input
                autoComplete="email"
                type="email"
                placeholder="you@university.edu"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              Password
              <div className="password-field">
                <input
                  autoComplete={
                    isRegister ? "new-password" : "current-password"
                  }
                  type={visible ? "text" : "password"}
                  placeholder={
                    isRegister ? "At least 8 characters" : "Enter your password"
                  }
                  minLength={8}
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  className="field-icon"
                  type="button"
                  onClick={() => setVisible(!visible)}
                  aria-label={visible ? "Hide password" : "Show password"}
                >
                  {visible ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>
            {isRegister && (
              <>
                <div
                  className="password-strength"
                  aria-label={`Password strength ${strength} of 3`}
                  aria-live="polite"
                >
                  <span
                    className={`strength-bar ${strength > 0 ? "active" : ""}`}
                  />
                  <span
                    className={`strength-bar ${strength > 1 ? "active" : ""}`}
                  />
                  <span
                    className={`strength-bar ${strength > 2 ? "active" : ""}`}
                  />
                  <small>
                    {
                      [
                        "Use 8 or more characters",
                        "Getting there",
                        "Good strength",
                        "Strong password",
                      ][strength]
                    }
                  </small>
                </div>
                <label>
                  Confirm password
                  <input
                    autoComplete="new-password"
                    type="password"
                    placeholder="Enter your password again"
                    required
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                  />
                </label>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={terms}
                    onChange={(event) => setTerms(event.target.checked)}
                  />
                  <span>
                    I agree to the{" "}
                    <a
                      href="#terms"
                      onClick={(event) => event.preventDefault()}
                    >
                      Terms of Service
                    </a>{" "}
                    and{" "}
                    <a
                      href="#privacy"
                      onClick={(event) => event.preventDefault()}
                    >
                      Privacy Policy
                    </a>
                    .
                  </span>
                </label>
              </>
            )}
            {!isRegister && (
              <div className="auth-options">
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(event) => setRemember(event.target.checked)}
                  />
                  <span>Remember me</span>
                </label>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => {
                    if (email.includes("@")) setResetSent(true);
                    else
                      setError(
                        "Enter your email address first to request a reset."
                      );
                  }}
                >
                  Forgot password?
                </button>
              </div>
            )}
            {resetSent && (
              <div className="auth-error" role="status">
                Password reset is not available through the connected account
                service. Contact support for help.
              </div>
            )}
            {error && (
              <div className="auth-error" role="alert">
                {error}
              </div>
            )}
            <button
              className="button button-primary auth-submit"
              type="submit"
              disabled={busy}
              aria-label={
                busy
                  ? isRegister
                    ? "Creating account"
                    : "Signing in"
                  : undefined
              }
            >
              {busy ? (
                <span className="spinner spinner-light" />
              ) : (
                <>
                  {isRegister ? "Create account" : "Log in"}{" "}
                  <ArrowRight size={16} />
                </>
              )}
            </button>
            {!isRegister && (
              <>
                <div className="auth-divider">
                  <span />
                  or continue with
                  <span />
                </div>
                <button
                  type="button"
                  className="google-button"
                  onClick={() =>
                    setError(
                      "Google sign-in will be available when an identity provider is connected."
                    )
                  }
                >
                  <span className="google-g">G</span> Continue with Google
                </button>
              </>
            )}
          </form>
          <p className="auth-switch">
            {isRegister ? "Already have an account?" : "New to Scholar?"}{" "}
            <Link to={isRegister ? "/login" : "/register"}>
              {isRegister ? "Log in" : "Create an account"}
            </Link>
          </p>
          <div className="demo-note">
            <span className="demo-pulse" />
            {useMocks ? (
              isRegister ? (
                <span>
                  Demo mode is on. New accounts are stored in this browser.
                </span>
              ) : (
                <>
                  <span className="demo-credentials">
                    Demo: <b>{demoCredentials.email}</b> ·{" "}
                    <b>{demoCredentials.password}</b>
                  </span>
                  <button
                    type="button"
                    className="text-button demo-fill-button"
                    onClick={() => {
                      setEmail(demoCredentials.email);
                      setPassword(demoCredentials.password);
                      setError("");
                    }}
                  >
                    Fill demo account
                  </button>
                </>
              )
            ) : (
              <span>Connected to the academic QA API.</span>
            )}
          </div>
        </section>
      </div>
      <footer className="auth-footer">
        <span>© 2026 Scholar AI</span>
        <span>Built for careful readers</span>
      </footer>
    </main>
  );
}
