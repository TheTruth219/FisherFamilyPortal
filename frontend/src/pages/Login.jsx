import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, ShieldCheck, HelpCircle, Mail, CheckCircle2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { auth } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    if (auth && auth !== false) navigate("/dashboard", { replace: true });
  }, [auth, navigate]);

  const submit = async (e) => {
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

  const inputClass =
    "min-h-[56px] text-lg p-4 border-2 border-slate-300 rounded-lg focus:border-blue-900 focus:ring-2 focus:ring-blue-900 focus:outline-none w-full bg-white text-slate-900";

  return (
    <div className="min-h-screen bg-slate-50 font-body flex flex-col" data-testid="login-page">
      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 text-white flex items-center justify-center">
              <Lock className="w-8 h-8" />
            </div>
          </div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold text-slate-950 text-center tracking-tight">
            Fisher Family Portal
          </h1>
          <p className="mt-3 text-lg text-slate-700 text-center leading-relaxed">
            Private information for authorized family members.
          </p>

          <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
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
                  onClick={() => { setSent(false); setEmail(""); }}
                  className="mt-5 min-h-[52px] px-6 text-lg font-bold rounded-lg bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors"
                >
                  Use a different email
                </button>
              </div>
            ) : (
              <form onSubmit={submit}>
                {error && (
                  <div className="mb-4 bg-red-50 border-2 border-red-300 text-red-800 rounded-lg p-3 text-base" data-testid="login-error">
                    {error}
                  </div>
                )}
                <label className="block text-base font-semibold text-slate-700 mb-2" htmlFor="email">
                  Email address
                </label>
                <input
                  id="email"
                  data-testid="email-input"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                  placeholder="you@example.com"
                  autoComplete="email"
                />
                <button
                  type="submit"
                  data-testid="send-link-btn"
                  disabled={loading}
                  className="mt-5 w-full min-h-[56px] text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 focus:outline-none transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60"
                >
                  <Mail className="w-5 h-5" />
                  {loading ? "Sending…" : "Send Login Link"}
                </button>
                <p className="mt-3 text-sm text-slate-500 text-center">
                  Access is limited to authorized Fisher family members.
                </p>
              </form>
            )}
          </div>

          <div className="mt-6 bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-start gap-3">
              <ShieldCheck className="w-6 h-6 text-blue-900 flex-shrink-0 mt-0.5" />
              <p className="text-base text-slate-700 leading-relaxed">
                Information in this portal is intended only for authorized Fisher family members. Do not forward
                sign-in links, private documents, financial information, or meeting materials outside the family.
              </p>
            </div>
          </div>

          <div className="mt-4 text-center">
            <button
              type="button"
              data-testid="need-access-link"
              onClick={() => setShowHelp(!showHelp)}
              className="inline-flex items-center gap-2 text-blue-900 font-semibold hover:underline"
            >
              <HelpCircle className="w-5 h-5" />
              Need help accessing the family portal?
            </button>
          </div>

          {showHelp && (
            <div className="mt-4 bg-slate-100 border border-slate-200 rounded-xl p-5 text-base text-slate-700" data-testid="help-panel">
              <p className="mb-2">
                <span className="font-semibold text-slate-900">Need access?</span> The portal is invite-only.
                Ask the Portal Administrator to add your email:{" "}
                <a className="text-blue-900 underline" href="mailto:stephen@cloudpoweredtech.com">
                  stephen@cloudpoweredtech.com
                </a>
                .
              </p>
              <p>
                <span className="font-semibold text-slate-900">Didn't get the link?</span> Check your spam folder,
                then request a new link — each link expires after 20 minutes.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
