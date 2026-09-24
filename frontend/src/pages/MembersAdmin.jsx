import React, { useEffect, useState } from "react";
import { UserPlus, Mail, ShieldAlert, Send } from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const ROLES = [
  { value: "member", label: "Member" },
  { value: "business_member", label: "Business Member" },
  { value: "committee_member", label: "Committee Member" },
  { value: "admin", label: "Administrator" },
];

const roleLabel = (v) => ROLES.find((r) => r.value === v)?.label || v;

export default function MembersAdmin() {
  const { auth, isAdmin } = useAuth();
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
    </Layout>
  );
}
