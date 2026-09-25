import React, { useEffect, useState } from "react";
import { UserPlus, Mail, ShieldAlert, Send, Bell, Database, Pencil, X } from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useContent } from "@/context/ContentContext";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";

const ROLES = [
  { value: "member", label: "Member" },
  { value: "business_member", label: "Business Member" },
  { value: "committee_member", label: "Committee Member" },
  { value: "admin", label: "Administrator" },
];

const roleLabel = (v) => ROLES.find((r) => r.value === v)?.label || v;

export default function MembersAdmin() {
  const { auth, isAdmin } = useAuth();
  const { content, update, save, dirty, saving, reload } = useContent();
  const [loadingSample, setLoadingSample] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", email: "" });
  const [savingEdit, setSavingEdit] = useState(false);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", role: "member" });
  const [inviting, setInviting] = useState(false);

  const inputClass =
    "min-h-[52px] text-lg p-3 border-2 border-slate-300 rounded-lg focus:border-blue-900 focus:ring-2 focus:ring-blue-900 focus:outline-none w-full bg-white text-slate-900";

  const load = async () => {
    try {
      const { data } = await api.get("/members");
      setMembers(data);
    } catch (e) {
      toast.error("Could not load members");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin]);

  const invite = async (e) => {
    e.preventDefault();
    setInviting(true);
    try {
      await api.post("/members", form);
      toast.success(`Invitation sent to ${form.email}`);
      setForm({ first_name: "", last_name: "", email: "", role: "member" });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not invite member");
    } finally {
      setInviting(false);
    }
  };

  const changeRole = async (id, role) => {
    try {
      await api.patch(`/members/${id}`, { role });
      toast.success("Role updated");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not update role");
    }
  };

  const toggleActive = async (m) => {
    try {
      await api.patch(`/members/${m.id}`, { is_active: !m.is_active });
      toast.success(m.is_active ? "Member deactivated" : "Member reactivated");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not update member");
    }
  };

  const resend = async (m) => {
    try {
      await api.post(`/members/${m.id}/resend-invite`);
      toast.success(`Sign-in link sent to ${m.email}`);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not send link");
    }
  };

  const openEdit = (m) => {
    setEditForm({ first_name: m.first_name || "", last_name: m.last_name || "", email: m.email });
    setEditing(m);
  };

  const saveEdit = async (e) => {
    e.preventDefault();
    setSavingEdit(true);
    try {
      await api.patch(`/members/${editing.id}`, editForm);
      toast.success("Member details updated");
      setEditing(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not update member");
    } finally {
      setSavingEdit(false);
    }
  };

  const loadSample = async () => {
    if (!window.confirm("Replace all current portal content with clearly-marked SAMPLE demo data? Your notification settings and members are kept. This is easy to overwrite later.")) return;
    setLoadingSample(true);
    try {
      await api.post("/content/load-sample");
      await reload();
      toast.success("Sample data loaded");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not load sample data");
    } finally {
      setLoadingSample(false);
    }
  };

  if (!isAdmin) {
    return (
      <Layout title="Members" testId="members-admin-page">
        <SectionCard testId="members-denied">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-6 h-6 text-red-700" />
            <p className="text-lg text-slate-800">This area is for administrators only.</p>
          </div>
        </SectionCard>
      </Layout>
    );
  }

  return (
    <Layout title="Members" subtitle="Invite family members, set roles, and manage access." testId="members-admin-page">
      <SectionCard title="Invite a Family Member" testId="invite-section">
        <form onSubmit={invite} className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-base font-semibold text-slate-700 mb-2">First Name</label>
            <input data-testid="invite-first-name" className={inputClass} value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
          </div>
          <div>
            <label className="block text-base font-semibold text-slate-700 mb-2">Last Name</label>
            <input data-testid="invite-last-name" className={inputClass} value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
          </div>
          <div>
            <label className="block text-base font-semibold text-slate-700 mb-2">Email</label>
            <input data-testid="invite-email" type="email" required className={inputClass} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="block text-base font-semibold text-slate-700 mb-2">Role</label>
            <select data-testid="invite-role" className={inputClass} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          <div className="sm:col-span-2">
            <button
              type="submit"
              data-testid="invite-submit-btn"
              disabled={inviting}
              className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <UserPlus className="w-5 h-5" />
              {inviting ? "Sending invite…" : "Invite & Send Sign-in Link"}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard title="Roles & Permissions" testId="roles-permissions-section">
        <p className="text-base text-slate-700 leading-relaxed mb-4">
          A member's role controls what they can open. Each level includes everything below it. Documents only open
          for members whose role meets the document's access level (enforced on the server).
        </p>
        <div className="space-y-3">
          {[
            { role: "Member", desc: "Reunion, meetings, payments and general information; documents marked \"All Members\"." },
            { role: "Business Member", desc: "Everything a Member sees, plus family business information and \"Business Members\" documents." },
            { role: "Committee Member", desc: "Everything above, plus \"Committee Members\" documents and Restricted business documents." },
            { role: "Administrator", desc: "Full access: edit all portal content, invite/manage members, and read help requests." },
          ].map((r) => (
            <div key={r.role} className="border border-slate-200 rounded-lg p-4">
              <div className="font-heading text-lg font-bold text-slate-900">{r.role}</div>
              <div className="text-base text-slate-600">{r.desc}</div>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Family Email Notifications" testId="notify-section">
        <div className="flex items-start gap-3 mb-4">
          <Bell className="w-6 h-6 text-blue-900 flex-shrink-0 mt-0.5" />
          <p className="text-base text-slate-700 leading-relaxed">
            When you post a new announcement, meeting, or document and save, the portal emails your
            family's distribution list. <span className="font-semibold">Meeting reminders now go out individually</span> —
            each family member gets their own reminder the day before a meeting, timed to their own time zone.
          </p>
        </div>
        <label className="block text-base font-semibold text-slate-700 mb-2">Family distribution list email <span className="font-normal text-slate-500">(for new-content announcements)</span></label>
        <input
          data-testid="notify-list-email"
          type="email"
          className={inputClass}
          placeholder="family@yourdomain.com"
          value={content?.notifications?.listEmail || ""}
          onChange={(e) => update("notifications.listEmail", e.target.value)}
        />
        <label className="block text-base font-semibold text-slate-700 mb-2 mt-4">Meeting reminder time <span className="font-normal text-slate-500">(each member's local time)</span></label>
        <select
          data-testid="notify-reminder-hour"
          className={inputClass}
          value={String(content?.notifications?.reminderHour ?? 9)}
          onChange={(e) => update("notifications.reminderHour", Number(e.target.value))}
        >
          {Array.from({ length: 24 }, (_, h) => {
            const label = h === 0 ? "12:00 AM" : h < 12 ? `${h}:00 AM` : h === 12 ? "12:00 PM" : `${h - 12}:00 PM`;
            return <option key={h} value={String(h)}>{label}</option>;
          })}
        </select>
        <p className="text-sm text-slate-500 mt-1">The day before each meeting, every member is emailed around this hour in <span className="font-semibold">their own</span> time zone (set on their Account page).</p>
        <label className="flex items-center gap-3 mt-4 text-base text-slate-800">
          <input
            type="checkbox"
            data-testid="notify-enabled"
            className="w-5 h-5"
            checked={content?.notifications?.enabled ?? true}
            onChange={(e) => update("notifications.enabled", e.target.checked)}
          />
          Send automatic notifications (new content + meeting reminders)
        </label>
        <button
          data-testid="notify-save-btn"
          onClick={save}
          disabled={saving || !dirty}
          className="mt-5 w-full sm:w-auto min-h-[52px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Notification Settings"}
        </button>
      </SectionCard>

      <SectionCard title={`Family Members (${members.length})`} testId="members-list">
        {loading ? (
          <p className="text-lg text-slate-600">Loading…</p>
        ) : (
          <div className="space-y-3">
            {members.map((m) => (
              <div key={m.id} data-testid={`member-row-${m.email}`} className="border-2 border-slate-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="font-heading text-lg font-bold text-slate-900">
                    {m.first_name || m.last_name ? `${m.first_name} ${m.last_name}`.trim() : m.email}
                    {!m.is_active && <span className="ml-2 text-xs font-bold uppercase bg-slate-200 text-slate-600 rounded px-2 py-1">Deactivated</span>}
                  </div>
                  <div className="text-base text-slate-600 flex items-center gap-1"><Mail className="w-4 h-4" /> {m.email}</div>
                </div>
                <select
                  data-testid={`member-role-${m.email}`}
                  className="min-h-[48px] text-base p-2 border-2 border-slate-300 rounded-lg bg-white text-slate-900"
                  value={m.role}
                  onChange={(e) => changeRole(m.id, e.target.value)}
                  disabled={m.id === auth?.id}
                >
                  {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
                <button
                  data-testid={`member-edit-${m.email}`}
                  onClick={() => openEdit(m)}
                  className="min-h-[48px] px-4 rounded-lg font-semibold border-2 border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-2"
                >
                  <Pencil className="w-4 h-4" /> Edit
                </button>
                <button
                  data-testid={`member-resend-${m.email}`}
                  onClick={() => resend(m)}
                  disabled={!m.is_active}
                  className="min-h-[48px] px-4 rounded-lg font-semibold border-2 border-blue-900 text-blue-900 hover:bg-blue-50 transition-colors inline-flex items-center gap-2 disabled:opacity-40"
                >
                  <Send className="w-4 h-4" /> Send link
                </button>
                <button
                  data-testid={`member-toggle-${m.email}`}
                  onClick={() => toggleActive(m)}
                  disabled={m.id === auth?.id}
                  className={`min-h-[48px] px-4 rounded-lg font-semibold border-2 transition-colors disabled:opacity-40 ${
                    m.is_active ? "border-red-300 text-red-700 hover:bg-red-50" : "border-green-400 text-green-700 hover:bg-green-50"
                  }`}
                >
                  {m.is_active ? "Deactivate" : "Reactivate"}
                </button>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard title="Demo Data" testId="demo-data-section">
        <p className="text-base text-slate-700 leading-relaxed mb-4">
          Load a fully-populated, clearly-marked <span className="font-semibold">SAMPLE</span> reunion, meetings,
          payments, business matters and documents so you can see how a filled-in portal looks. Everything is
          fictional and labelled "SAMPLE" — replace it with your real information anytime using Edit mode.
        </p>
        <button
          data-testid="load-sample-btn"
          onClick={loadSample}
          disabled={loadingSample}
          className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <Database className="w-5 h-5" />
          {loadingSample ? "Loading sample data…" : "Load Sample Reunion Data"}
        </button>
      </SectionCard>

      {editing && (
        <Dialog open={!!editing} onOpenChange={(open) => { if (!open) setEditing(null); }}>
          <DialogContent className="portal-modal page-content" data-testid="edit-member-modal" closeTestId="edit-member-close">
            <DialogTitle className="font-heading text-2xl font-bold text-slate-900">Edit Member</DialogTitle>
            <DialogDescription className="mb-5">Keep your family circle’s details up to date.</DialogDescription>
            <form onSubmit={saveEdit} className="space-y-4">
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">First Name</label>
                <input data-testid="edit-first-name" className={inputClass} value={editForm.first_name} onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })} />
              </div>
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Last Name</label>
                <input data-testid="edit-last-name" className={inputClass} value={editForm.last_name} onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })} />
              </div>
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Email</label>
                <input data-testid="edit-email" type="email" required className={inputClass} value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
                <p className="text-sm text-slate-500 mt-1">Future sign-in links will be sent to this address.</p>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" data-testid="edit-save-btn" disabled={savingEdit} className="flex-1 min-h-[52px] text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors disabled:opacity-60">
                  {savingEdit ? "Saving…" : "Save Changes"}
                </button>
                <button type="button" data-testid="edit-cancel-btn" onClick={() => setEditing(null)} className="min-h-[52px] px-6 text-lg font-bold rounded-lg bg-white text-slate-700 border-2 border-slate-300 hover:bg-slate-50 transition-colors">
                  Cancel
                </button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </Layout>
  );
}
