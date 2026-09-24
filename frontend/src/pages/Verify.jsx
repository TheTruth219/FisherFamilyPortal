import React, { useEffect, useState, useRef } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { Loader2, XCircle } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function Verify() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setAuth } = useAuth();
  const [error, setError] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const token = params.get("token");
    if (!token) {
      setError("This sign-in link is missing its token. Please request a new one.");
      return;
    }
    (async () => {
      try {
        await api.post("/auth/verify", { token });
        // Hard redirect so AuthProvider remounts and reads the fresh session cookie
        // (avoids racing the initial /auth/me 401).
        window.location.replace("/dashboard");
      } catch (err) {
        setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
      }
    })();
  }, [params, navigate, setAuth]);

  return (
    <div className="min-h-screen bg-slate-50 font-body flex items-center justify-center px-4" data-testid="verify-page">
      <div className="w-full max-w-md text-center">
        {!error ? (
          <div data-testid="verify-loading">
            <Loader2 className="w-12 h-12 text-blue-900 animate-spin mx-auto mb-4" />
            <p className="text-xl font-semibold text-slate-900">Signing you in…</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm" data-testid="verify-error">
            <XCircle className="w-14 h-14 text-red-600 mx-auto mb-4" />
            <p className="text-xl font-semibold text-slate-900">We couldn't sign you in</p>
            <p className="mt-2 text-base text-slate-600 leading-relaxed">{error}</p>
            <Link
              to="/login"
              data-testid="back-to-login"
              className="mt-6 inline-flex items-center justify-center min-h-[52px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors"
            >
              Back to sign in
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
