import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, ShieldCheck, HelpCircle, KeyRound } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { auth, setAuth } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [adminMode, setAdminMode] = useState(false);
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  useEffect(() => {
    if (auth && auth !== false) navigate("/dashboard", { replace: true });
  }, [auth, navigate]);

  const submitMember = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/member-login", { password });
      setAuth(data);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitAdmin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/admin-login", { email: adminEmail, password: adminPassword });
      setAuth(data);
      navigate("/dashboard", { replace: true });
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
            Private reunion, family business, payment, meeting, and document information for authorized family members.
          </p>

          <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            {error && (
              <div className="mb-4 bg-red-50 border-2 border-red-300 text-red-800 rounded-lg p-3 text-base" data-testid="login-error">
                {error}
              </div>
            )}

            {!adminMode ? (
              <form onSubmit={submitMember}>
                <label className="block text-base font-semibold text-slate-700 mb-2" htmlFor="family-password">
                  Family Password
                </label>
                <input
                  id="family-password"
                  data-testid="family-password-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass}
                  placeholder="Enter family password"
                  autoComplete="current-password"
                />
                <button
                  type="submit"
                  data-testid="member-login-btn"
                  disabled={loading}
                  className="mt-5 w-full min-h-[56px] text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 focus:outline-none transition-colors disabled:opacity-60"
                >
                  {loading ? "Signing in…" : "Log In"}
                </button>
              </form>
            ) : (
              <form onSubmit={submitAdmin}>
                <label className="block text-base font-semibold text-slate-700 mb-2" htmlFor="admin-email">
                  Administrator Email
                </label>
                <input
                  id="admin-email"
                  data-testid="admin-email-input"
                  type="email"
                  value={adminEmail}
                  onChange={(e) => setAdminEmail(e.target.value)}
                  className={inputClass}
                  placeholder="admin@fisherfamily.portal"
                  autoComplete="username"
                />
                <label className="block text-base font-semibold text-slate-700 mb-2 mt-4" htmlFor="admin-password">
                  Password
                </label>
                <input
                  id="admin-password"
                  data-testid="admin-password-input"
                  type="password"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  className={inputClass}
                  autoComplete="current-password"
                />
                <button
                  type="submit"
                  data-testid="admin-login-btn"
                  disabled={loading}
                  className="mt-5 w-full min-h-[56px] text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 focus:outline-none transition-colors disabled:opacity-60"
                >
                  {loading ? "Signing in…" : "Administrator Log In"}
                </button>
              </form>
            )}

            <button
              type="button"
              data-testid="toggle-admin-mode"
              onClick={() => {
                setAdminMode(!adminMode);
                setError("");
              }}
              className="mt-4 w-full inline-flex items-center justify-center gap-2 text-blue-900 font-semibold hover:underline"
            >
              <KeyRound className="w-4 h-4" />
              {adminMode ? "Back to Family Login" : "Administrator sign in"}
            </button>
          </div>

          <div className="mt-6 bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-start gap-3">
              <ShieldCheck className="w-6 h-6 text-blue-900 flex-shrink-0 mt-0.5" />
              <p className="text-base text-slate-700 leading-relaxed">
                Information in this portal is intended only for authorized Fisher family members. Do not forward
                passwords, private documents, financial information, or meeting materials outside the family.
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
              Need Access or Login Help?
            </button>
          </div>

          {showHelp && (
            <div className="mt-4 bg-slate-100 border border-slate-200 rounded-xl p-5 text-base text-slate-700" data-testid="help-panel">
              <p className="mb-2">
                <span className="font-semibold text-slate-900">Need access?</span> Contact the Portal Administrator at{" "}
                <a className="text-blue-900 underline" href="mailto:admin@fisherfamily.portal">
                  admin@fisherfamily.portal
                </a>
                .
              </p>
              <p>
                <span className="font-semibold text-slate-900">Technical help:</span>{" "}
                <a className="text-blue-900 underline" href="mailto:help@fisherfamily.portal">
                  help@fisherfamily.portal
                </a>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
