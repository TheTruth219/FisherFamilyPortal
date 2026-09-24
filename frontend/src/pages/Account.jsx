import React, { useEffect, useState } from "react";
import { KeyRound, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function Account() {
  const { auth } = useAuth();
  const [hasPassword, setHasPassword] = useState(false);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/auth/me").then(({ data }) => setHasPassword(!!data.has_password)).catch(() => {});
  }, []);

  const inputClass =
    "min-h-[56px] text-lg p-4 border-2 border-slate-300 rounded-lg focus:border-blue-900 focus:ring-2 focus:ring-blue-900 focus:outline-none w-full bg-white text-slate-900";

  const submit = async (e) => {
    e.preventDefault();
    if (pw.length < 8) return toast.error("Password must be at least 8 characters.");
    if (pw !== confirm) return toast.error("Passwords do not match.");
    setSaving(true);
    try {
      await api.post("/auth/set-password", { password: pw });
      setHasPassword(true);
      setPw(""); setConfirm("");
      toast.success("Password saved — you can now log in with your email and password.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not save password");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout title="Account" subtitle="Manage how you sign in to the portal." testId="account-page">
      <SectionCard title={hasPassword ? "Change Your Password" : "Set a Password"} testId="set-password-section">
        <div className="flex items-start gap-3 mb-4">
          <KeyRound className="w-6 h-6 text-blue-900 flex-shrink-0 mt-0.5" />
          <p className="text-base text-slate-700 leading-relaxed">
            {hasPassword
              ? "You can sign in with your email and password, or anytime with an email sign-in link."
              : "Set a password so you can sign in with just your email and password. You can always use an email sign-in link instead."}
            {" "}Signed in as <span className="font-semibold">{auth?.email}</span>.
          </p>
        </div>
        <form onSubmit={submit} className="max-w-md">
          <label className="block text-base font-semibold text-slate-700 mb-2">New password</label>
          <input data-testid="new-password" type="password" className={inputClass} value={pw}
            onChange={(e) => setPw(e.target.value)} autoComplete="new-password" placeholder="At least 8 characters" />
          <label className="block text-base font-semibold text-slate-700 mb-2 mt-4">Confirm password</label>
          <input data-testid="confirm-password" type="password" className={inputClass} value={confirm}
            onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
          <button type="submit" data-testid="save-password-btn" disabled={saving}
            className="mt-5 w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60">
            <CheckCircle2 className="w-5 h-5" />
            {saving ? "Saving…" : hasPassword ? "Update Password" : "Set Password"}
          </button>
        </form>
      </SectionCard>
    </Layout>
  );
}
