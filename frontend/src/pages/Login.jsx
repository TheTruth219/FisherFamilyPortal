import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, ShieldCheck, HelpCircle, Mail, CheckCircle2, KeyRound, ArrowRight } from "lucide-react";
import { FamilyMark } from "@/components/FamilyArtwork";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { auth, setAuth } = useAuth();
  const [mode, setMode] = useState("password"); // "password" | "link"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    if (auth && auth !== false) navigate("/dashboard", { replace: true });
  }, [auth, navigate]);

  const submitPassword = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setAuth(data);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitLink = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/request-link", { email });
      setSent(true);
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "portal-input";

  return (
    <div className="login-experience" data-testid="login-page">
      <section className="login-story">
        <div className="portal-brand login-brand"><FamilyMark testId="login-brand-logo" /></div>
        <div className="login-story-content">
          <span className="eyebrow">CONNECTED BY MORE.</span>
          <h2>A family.<br />A feeling.<br /><span>A place to belong.</span></h2>
          <p>For the moments we share.<br />And everything we’re building together.</p>
        </div>
        <div className="login-story-footer"><span>OUR ROOTS RUN DEEP.</span><span>OUR STORY CONTINUES.</span></div>
      </section>
      <div className="login-form-side">
        <div className="login-mobile-brand portal-brand"><FamilyMark testId="mobile-login-logo" /></div>
        <div className="login-form-wrap">
          <span className="eyebrow login-eyebrow">YOUR FAMILY. ALL HERE.</span>
          <h1 data-testid="login-title">Welcome home.</h1>
          <p className="login-subtitle" data-testid="login-subtitle">Your family’s private space to stay close,<br className="desktop-break" /> catch up, and move forward together.</p>

          <div className="login-form-card">
            {error && (
              <div className="mb-4 bg-red-50 border-2 border-red-300 text-red-800 rounded-lg p-3 text-base" data-testid="login-error">
                {error}
              </div>
            )}

            {sent ? (
              <div className="text-center py-4" data-testid="link-sent">
                <CheckCircle2 className="w-14 h-14 text-green-600 mx-auto mb-4" />
                <p className="text-xl font-semibold text-slate-900">Check your email</p>
                <p className="mt-2 text-base text-slate-600 leading-relaxed">
                  If <span className="font-semibold">{email}</span> belongs to an authorized family member,
                  we've sent a secure sign-in link. It expires in 20 minutes.
                </p>
                <button
                  data-testid="send-again-btn"
                  onClick={() => { setSent(false); setEmail(""); setMode("password"); }}
                  className="mt-5 min-h-[52px] px-6 text-lg font-bold rounded-lg bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors"
                >
                  Back to sign in
                </button>
              </div>
            ) : mode === "password" ? (
              <form onSubmit={submitPassword}>
                <label className="block text-base font-semibold text-slate-700 mb-2" htmlFor="email">Email address</label>
                <input id="email" data-testid="email-input" type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="you@example.com" autoComplete="email" />
                <label className="block text-base font-semibold text-slate-700 mb-2 mt-4" htmlFor="password">Password</label>
                <input id="password" data-testid="password-input" type="password" required value={password}
                  onChange={(e) => setPassword(e.target.value)} className={inputClass} autoComplete="current-password" />
                <button type="submit" data-testid="password-login-btn" disabled={loading}
                  className="portal-button primary login-submit">
                  {loading ? "Signing in…" : "Sign in"}<ArrowRight className="w-5 h-5" />
                </button>
                <button type="button" data-testid="switch-to-link" onClick={() => { setMode("link"); setError(""); }}
                  className="mt-4 w-full inline-flex items-center justify-center gap-2 text-blue-900 font-semibold hover:underline">
                  <Mail className="w-4 h-4" /> Use an email sign-in link instead
                </button>
                <p className="mt-3 text-sm text-slate-500 text-center">
                  First time here? Use an email sign-in link, then set a password from your Account page.
                </p>
              </form>
            ) : (
              <form onSubmit={submitLink}>
                <label className="block text-base font-semibold text-slate-700 mb-2" htmlFor="email-link">Email address</label>
                <input id="email-link" data-testid="email-input" type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="you@example.com" autoComplete="email" />
                <button type="submit" data-testid="send-link-btn" disabled={loading}
                  className="mt-5 w-full min-h-[56px] text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 focus:outline-none transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60">
                  <Mail className="w-5 h-5" />
                  {loading ? "Sending…" : "Send Login Link"}
                </button>
                <button type="button" data-testid="switch-to-password" onClick={() => { setMode("password"); setError(""); }}
                  className="mt-4 w-full inline-flex items-center justify-center gap-2 text-blue-900 font-semibold hover:underline">
                  <KeyRound className="w-4 h-4" /> Sign in with a password instead
                </button>
                <p className="mt-3 text-sm text-slate-500 text-center">
                  Access is limited to authorized Fisher family members.
                </p>
              </form>
            )}
          </div>

          <div className="login-privacy" data-testid="login-privacy-notice">
            <ShieldCheck size={19} />
            <p>A private space, just for family. Keep sign-in links, documents, and financial information within our circle.</p>
          </div>

          <div className="mt-4 text-center">
            <button type="button" data-testid="need-access-link" onClick={() => setShowHelp(!showHelp)}
              className="inline-flex items-center gap-2 text-blue-900 font-semibold hover:underline">
              <HelpCircle className="w-5 h-5" />
              Need help accessing the family portal?
            </button>
          </div>

          {showHelp && (
            <div className="mt-4 bg-slate-100 border border-slate-200 rounded-xl p-5 text-base text-slate-700" data-testid="help-panel">
              <p className="mb-2">
                <span className="font-semibold text-slate-900">Need access?</span> The portal is invite-only.
                Ask the Portal Administrator to add your email:{" "}
                <a data-testid="login-help-email" className="text-blue-900 underline" href="mailto:stephen@cloudpoweredtech.com">stephen@cloudpoweredtech.com</a>.
              </p>
              <p>
                <span className="font-semibold text-slate-900">Forgot your password?</span> Use an email sign-in link
                to get in, then set a new password from your Account page.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
