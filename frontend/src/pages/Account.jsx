import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { KeyRound, CheckCircle2, Globe, CreditCard, Clock, AlertCircle, ExternalLink, Loader2, UserCircle, Camera, Trash2, IdCard } from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { Avatar } from "@/components/Avatar";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const emptyProfile = {
  first_name: "", last_name: "", phone: "", street: "", city: "", state: "",
  zip: "", bio: "", birthday: "", family_branch: "", occupation: "",
};

const TZS = [
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Phoenix", "America/Anchorage", "Pacific/Honolulu", "America/Toronto",
  "Europe/London", "Europe/Paris", "Asia/Dubai", "Asia/Kolkata", "Asia/Singapore",
  "Asia/Tokyo", "Australia/Sydney", "UTC",
];
const STRIPE_STATE = {
  onboarded: { cls: "bg-green-100 text-green-800 border-green-300", Icon: CheckCircle2, label: "Onboarded" },
  pending: { cls: "bg-amber-100 text-amber-800 border-amber-300", Icon: Clock, label: "Pending Verification" },
  not_connected: { cls: "bg-slate-100 text-slate-600 border-slate-300", Icon: AlertCircle, label: "Not Connected" },
};
const inputClass = "min-h-[56px] text-lg p-4 border-2 border-slate-300 rounded-lg focus:border-blue-900 focus:ring-2 focus:ring-blue-900 focus:outline-none w-full bg-white text-slate-900";

export default function Account() {
  const { auth, refresh } = useAuth();
  const [hasPassword, setHasPassword] = useState(false);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [tz, setTz] = useState(auth?.timezone || "America/Chicago");
  const [savingTz, setSavingTz] = useState(false);
  const [stripe, setStripe] = useState(null);
  const [stripeBusy, setStripeBusy] = useState(false);
  const [params] = useSearchParams();

  const [profile, setProfile] = useState(emptyProfile);
  const [savingProfile, setSavingProfile] = useState(false);
  const [photo, setPhoto] = useState(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    api.get("/auth/me").then(({ data }) => {
      setHasPassword(!!data.has_password);
      setTz(data.timezone || "America/Chicago");
      setProfile({ ...emptyProfile, ...Object.fromEntries(Object.keys(emptyProfile).map((k) => [k, data[k] || ""])) });
      setPhoto({ photo_url: data.photo_url, first_name: data.first_name, last_name: data.last_name, email: data.email });
    }).catch(() => {});
    api.get("/stripe/connect/status").then(({ data }) => setStripe(data)).catch(() => {});
    if (params.get("stripe") === "return") toast.success("Returned from Stripe — refreshing your onboarding status.");
  }, []); // eslint-disable-line

  const setP = (k, v) => setProfile((p) => ({ ...p, [k]: v }));

  const saveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      const { data } = await api.patch("/auth/profile", profile);
      await refresh();
      setPhoto((prev) => ({ ...prev, first_name: data.first_name, last_name: data.last_name }));
      toast.success("Profile saved. Your family can find you in the address book.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not save your profile");
    } finally { setSavingProfile(false); }
  };

  const onPhotoPick = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) { toast.error("Photo is too large (max 5 MB)."); return; }
    const fd = new FormData();
    fd.append("file", f);
    setUploadingPhoto(true);
    try {
      const { data } = await api.post("/auth/profile/photo", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setPhoto((prev) => ({ ...prev, photo_url: data.photo_url }));
      await refresh();
      toast.success("Photo updated.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not upload photo");
    } finally { setUploadingPhoto(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const removePhoto = async () => {
    setUploadingPhoto(true);
    try {
      const { data } = await api.delete("/auth/profile/photo");
      setPhoto((prev) => ({ ...prev, photo_url: data.photo_url }));
      await refresh();
      toast.success("Photo removed.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not remove photo");
    } finally { setUploadingPhoto(false); }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (pw.length < 8) return toast.error("Password must be at least 8 characters.");
    if (pw !== confirm) return toast.error("Passwords do not match.");
    setSaving(true);
    try {
      await api.post("/auth/set-password", { password: pw });
      setHasPassword(true); setPw(""); setConfirm("");
      toast.success("Password saved.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not save password");
    } finally { setSaving(false); }
  };

  const saveTz = async () => {
    setSavingTz(true);
    try {
      await api.patch("/auth/timezone", { timezone: tz, confirm: true });
      await refresh();
      toast.success("Timezone updated. Meeting times will show in your timezone.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not update timezone");
    } finally { setSavingTz(false); }
  };

  const startOnboarding = async () => {
    setStripeBusy(true);
    try {
      const { data } = await api.post("/stripe/connect/onboard");
      window.location.assign(data.url);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Stripe Connect unavailable");
      setStripeBusy(false);
    }
  };

  const nowLocal = new Date().toLocaleString("en-US", { timeZone: tz, dateStyle: "medium", timeStyle: "short" });
  const st = STRIPE_STATE[stripe?.onboarding_status || "not_connected"];

  return (
    <Layout title="Your Account" subtitle="A few details that make this space yours." testId="account-page">
      <div className="account-profile" data-testid="account-profile">
        <div className="account-avatar" aria-hidden="true">{auth?.first_name?.[0] || "F"}{auth?.last_name?.[0] || ""}</div>
        <div><h2 data-testid="account-name">{[auth?.first_name, auth?.last_name].filter(Boolean).join(" ") || "Family member"}</h2><p data-testid="account-email">{auth?.email}</p></div>
        <span className="account-role" data-testid="account-role">{auth?.role?.replaceAll("_", " ")}</span>
      </div>

      <SectionCard testId="profile-section">
        <div className="flex items-center gap-2 mb-4"><UserCircle className="w-6 h-6 text-blue-900" /><h2 className="font-heading text-2xl font-semibold text-slate-900">Your Profile</h2></div>
        <p className="text-base text-slate-700 mb-6">This information appears in the <span className="font-semibold">Family Address Book</span> so relatives can reach you.</p>

        <div className="flex flex-col sm:flex-row sm:items-center gap-5 mb-8">
          <Avatar member={photo || {}} size="lg" testId="profile-photo-preview" />
          <div className="flex flex-col gap-2">
            <input ref={fileRef} type="file" accept="image/*" className="hidden" data-testid="profile-photo-input" onChange={onPhotoPick} />
            <div className="flex flex-wrap gap-3">
              <button type="button" data-testid="profile-photo-upload-btn" onClick={() => fileRef.current?.click()} disabled={uploadingPhoto} className="min-h-[48px] px-5 rounded-lg font-bold border-2 border-blue-900 text-blue-900 hover:bg-blue-50 transition-colors inline-flex items-center gap-2 disabled:opacity-60">
                {uploadingPhoto ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />} {photo?.photo_url ? "Change photo" : "Upload photo"}
              </button>
              {photo?.photo_url && (
                <button type="button" data-testid="profile-photo-remove-btn" onClick={removePhoto} disabled={uploadingPhoto} className="min-h-[48px] px-5 rounded-lg font-bold border-2 border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors inline-flex items-center gap-2 disabled:opacity-60">
                  <Trash2 className="w-5 h-5" /> Remove
                </button>
              )}
            </div>
            <p className="text-sm text-slate-500">JPG, PNG, GIF or WEBP · up to 5 MB. If you don't add one, we'll show your initials.</p>
          </div>
        </div>

        <form onSubmit={saveProfile} className="grid sm:grid-cols-2 gap-x-5 gap-y-4">
          <div><label className="block text-base font-semibold text-slate-700 mb-2">First name</label><input data-testid="profile-first-name" className={inputClass} value={profile.first_name} onChange={(e) => setP("first_name", e.target.value)} /></div>
          <div><label className="block text-base font-semibold text-slate-700 mb-2">Last name</label><input data-testid="profile-last-name" className={inputClass} value={profile.last_name} onChange={(e) => setP("last_name", e.target.value)} /></div>
          <div><label className="block text-base font-semibold text-slate-700 mb-2">Phone</label><input data-testid="profile-phone" type="tel" className={inputClass} placeholder="(555) 123-4567" value={profile.phone} onChange={(e) => setP("phone", e.target.value)} /></div>
          <div><label className="block text-base font-semibold text-slate-700 mb-2">Birthday</label><input data-testid="profile-birthday" className={inputClass} placeholder="e.g. March 14 or 1990-03-14" value={profile.birthday} onChange={(e) => setP("birthday", e.target.value)} /></div>
          <div className="sm:col-span-2"><label className="block text-base font-semibold text-slate-700 mb-2">Street address</label><input data-testid="profile-street" className={inputClass} value={profile.street} onChange={(e) => setP("street", e.target.value)} /></div>
          <div><label className="block text-base font-semibold text-slate-700 mb-2">City</label><input data-testid="profile-city" className={inputClass} value={profile.city} onChange={(e) => setP("city", e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-5">
            <div><label className="block text-base font-semibold text-slate-700 mb-2">State</label><input data-testid="profile-state" className={inputClass} value={profile.state} onChange={(e) => setP("state", e.target.value)} /></div>
            <div><label className="block text-base font-semibold text-slate-700 mb-2">ZIP</label><input data-testid="profile-zip" className={inputClass} value={profile.zip} onChange={(e) => setP("zip", e.target.value)} /></div>
          </div>
          <div><label className="block text-base font-semibold text-slate-700 mb-2">Family branch / household</label><input data-testid="profile-family-branch" className={inputClass} placeholder="e.g. The James Fisher family" value={profile.family_branch} onChange={(e) => setP("family_branch", e.target.value)} /></div>
          <div><label className="block text-base font-semibold text-slate-700 mb-2">Occupation</label><input data-testid="profile-occupation" className={inputClass} value={profile.occupation} onChange={(e) => setP("occupation", e.target.value)} /></div>
          <div className="sm:col-span-2"><label className="block text-base font-semibold text-slate-700 mb-2">About you</label><textarea data-testid="profile-bio" rows={3} className={inputClass} placeholder="A short note for the family — where you live, what you're up to, anything you'd like to share." value={profile.bio} onChange={(e) => setP("bio", e.target.value)} /></div>
          <div className="sm:col-span-2">
            <button type="submit" data-testid="save-profile-btn" disabled={savingProfile} className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60">
              {savingProfile ? <Loader2 className="w-5 h-5 animate-spin" /> : <IdCard className="w-5 h-5" />} {savingProfile ? "Saving…" : "Save Profile"}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard title={hasPassword ? "Change Your Password" : "Set a Password"} testId="set-password-section">
        <div className="flex items-start gap-3 mb-4">
          <KeyRound className="w-6 h-6 text-blue-900 flex-shrink-0 mt-0.5" />
          <p className="text-base text-slate-700 leading-relaxed">
            {hasPassword
              ? "You can sign in with your email and password, or anytime with an email sign-in link."
              : "Set a password so you can sign in with just your email and password."}
            {" "}Signed in as <span className="font-semibold">{auth?.email}</span>.
          </p>
        </div>
        <form onSubmit={submit} className="max-w-md">
          <label className="block text-base font-semibold text-slate-700 mb-2">New password</label>
          <input data-testid="new-password" type="password" className={inputClass} value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" placeholder="At least 8 characters" />
          <label className="block text-base font-semibold text-slate-700 mb-2 mt-4">Confirm password</label>
          <input data-testid="confirm-password" type="password" className={inputClass} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
          <button type="submit" data-testid="save-password-btn" disabled={saving} className="mt-5 w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60">
            <CheckCircle2 className="w-5 h-5" />{saving ? "Saving…" : hasPassword ? "Update Password" : "Set Password"}
          </button>
        </form>
      </SectionCard>

      <SectionCard testId="timezone-section">
        <div className="flex items-center gap-2 mb-4"><Globe className="w-6 h-6 text-blue-900" /><h2 className="font-heading text-2xl font-semibold text-slate-900">Your Timezone</h2></div>
        <p className="text-base text-slate-700 mb-4">Meeting times and reminders are shown in your timezone.</p>
        <div className="flex flex-col sm:flex-row sm:items-end gap-4 max-w-xl">
          <div className="flex-1">
            <label className="block text-base font-semibold text-slate-700 mb-2">Timezone</label>
            <select data-testid="member-timezone-select" className={inputClass} value={tz} onChange={(e) => setTz(e.target.value)}>
              {TZS.includes(tz) ? null : <option value={tz}>{tz}</option>}
              {TZS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <button data-testid="save-timezone-btn" onClick={saveTz} disabled={savingTz || tz === auth?.timezone} className="min-h-[56px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 disabled:opacity-50 inline-flex items-center justify-center gap-2">
            {savingTz ? <Loader2 className="w-5 h-5 animate-spin" /> : "Save"}
          </button>
        </div>
        <div className="mt-3 bg-slate-100 rounded-lg px-4 py-2 text-base text-slate-700">Current local time: <span className="font-semibold">{nowLocal}</span></div>
      </SectionCard>

      <SectionCard testId="stripe-section">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2"><CreditCard className="w-6 h-6 text-blue-900" /><h2 className="font-heading text-2xl font-semibold text-slate-900">Payout Setup</h2></div>
          <span data-testid="stripe-connect-status-badge" className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-bold ${st.cls}`}><st.Icon className="w-4 h-4" /> {st.label}</span>
        </div>
        <p className="text-base text-slate-700 mb-4">Complete Stripe Connect onboarding (identity verification + bank account) to receive real payouts for recorded disbursements.</p>
        {stripe?.error && <p className="text-sm text-rose-600 mb-3">Stripe note: {stripe.error}</p>}
        <button data-testid="stripe-connect-button" onClick={startOnboarding} disabled={stripeBusy} className="min-h-[56px] px-6 text-lg font-bold rounded-lg bg-[#635BFF] text-white hover:bg-[#4b45cc] transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60">
          {stripeBusy ? <Loader2 className="w-5 h-5 animate-spin" /> : <ExternalLink className="w-5 h-5" />}
          {stripe?.onboarding_status === "onboarded" ? "Manage Stripe account" : "Set up payouts with Stripe"}
        </button>
      </SectionCard>
    </Layout>
  );
}
