import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CalendarHeart, Briefcase, CreditCard, Users, FileText, UserCog,
  Inbox, ShieldAlert, Mail, Phone, Bell,
} from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const MANAGE = [
  { key: "reunion", label: "Reunion", to: "/reunion", icon: CalendarHeart },
  { key: "business", label: "Family Business", to: "/family-business", icon: Briefcase },
  { key: "payments", label: "Payments", to: "/payments", icon: CreditCard },
  { key: "meetings", label: "Meetings", to: "/meetings", icon: Users },
  { key: "documents", label: "Documents", to: "/documents", icon: FileText },
  { key: "members", label: "Members", to: "/members", icon: UserCog },
];

const STATUS = {
  new: { label: "New", cls: "bg-red-100 text-red-800 border-red-300" },
  in_progress: { label: "In progress", cls: "bg-amber-100 text-amber-800 border-amber-300" },
  resolved: { label: "Resolved", cls: "bg-green-100 text-green-800 border-green-300" },
};
const FILTERS = ["all", "new", "in_progress", "resolved"];

export default function AdminHome() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const load = async () => {
    try {
      const { data } = await api.get("/help-requests");
      setRequests(data);
    } catch {
      toast.error("Could not load help requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin]);

  const setStatus = async (id, status) => {
    setRequests((rs) => rs.map((r) => (r.id === id ? { ...r, status } : r)));
    try {
      await api.patch(`/help-requests/${id}`, { status });
      toast.success("Status updated");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not update");
      load();
    }
  };

  if (!isAdmin) {
    return (
      <Layout title="Admin Console" testId="admin-home-page">
        <SectionCard testId="admin-denied">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-6 h-6 text-red-700" />
            <p className="text-lg text-slate-800">This area is for administrators only.</p>
          </div>
        </SectionCard>
      </Layout>
    );
  }

  const newCount = requests.filter((r) => (r.status || "new") === "new").length;
  const shown = requests.filter((r) => filter === "all" || (r.status || "new") === filter);

  return (
    <Layout title="Admin Console" subtitle="Manage portal content and read member help requests." testId="admin-home-page">
      <SectionCard title="Manage Portal Content" testId="admin-manage-section">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {MANAGE.map((m) => {
            const Icon = m.icon;
            return (
              <button
                key={m.key}
                data-testid={`admin-link-${m.key}`}
                onClick={() => navigate(m.to)}
                className="bg-white border-2 border-slate-200 rounded-xl p-5 hover:border-blue-900 hover:shadow-md transition-all flex flex-col items-center text-center gap-3"
              >
                <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center">
                  <Icon className="w-6 h-6 text-blue-900" />
                </div>
                <div className="font-heading text-base font-bold text-slate-900">{m.label}</div>
              </button>
            );
          })}
        </div>
        <p className="text-sm text-slate-500 mt-4">
          Open any area, press <span className="font-semibold">Edit</span> in the header, make changes, then Save.
        </p>
      </SectionCard>

      <SectionCard testId="help-inbox-section" title={undefined}>
        <div className="flex items-center gap-3 mb-4">
          <Inbox className="w-7 h-7 text-blue-900" />
          <h2 className="font-heading text-2xl font-semibold text-slate-900">Help Requests</h2>
          {newCount > 0 && (
            <span data-testid="help-new-count" className="bg-red-600 text-white text-sm font-bold rounded-full px-3 py-1">
              {newCount} new
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2 mb-5">
          {FILTERS.map((f) => (
            <button
              key={f}
              data-testid={`help-filter-${f}`}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 min-h-[44px] rounded-lg font-semibold border-2 transition-colors ${
                filter === f ? "bg-blue-900 text-white border-blue-900" : "bg-white text-blue-900 border-blue-200 hover:border-blue-900"
              }`}
            >
              {f === "all" ? "All" : STATUS[f].label}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="text-lg text-slate-600">Loading…</p>
        ) : shown.length === 0 ? (
          <div className="text-center py-10" data-testid="help-empty">
            <Inbox className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-lg text-slate-600">No help requests {filter !== "all" ? `marked "${STATUS[filter].label}"` : "yet"}.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {shown.map((r) => {
              const st = STATUS[r.status || "new"];
              return (
                <div key={r.id} data-testid={`help-request-${r.id}`} className="border-2 border-slate-200 rounded-xl p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-heading text-lg font-bold text-slate-900">{r.topic}</span>
                        <span className={`text-xs font-bold uppercase tracking-wide border rounded px-2 py-1 ${st.cls}`}>{st.label}</span>
                      </div>
                      <div className="text-base text-slate-700 mt-1">{r.name}</div>
                      <div className="text-sm text-slate-500 flex flex-wrap gap-x-4 gap-y-1 mt-1">
                        <a href={`mailto:${r.email}`} className="inline-flex items-center gap-1 text-blue-900 hover:underline">
                          <Mail className="w-4 h-4" /> {r.email}
                        </a>
                        {r.phone ? <span className="inline-flex items-center gap-1"><Phone className="w-4 h-4" /> {r.phone}</span> : null}
                        {r.created_at ? <span>{new Date(r.created_at).toLocaleString()}</span> : null}
                      </div>
                    </div>
                    <select
                      data-testid={`help-status-${r.id}`}
                      value={r.status || "new"}
                      onChange={(e) => setStatus(r.id, e.target.value)}
                      className="min-h-[48px] text-base p-2 border-2 border-slate-300 rounded-lg bg-white text-slate-900"
                    >
                      <option value="new">New</option>
                      <option value="in_progress">In progress</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </div>
                  <p className="mt-3 text-base text-slate-800 whitespace-pre-wrap bg-slate-50 rounded-lg p-3">{r.message}</p>
                </div>
              );
            })}
          </div>
        )}
      </SectionCard>
    </Layout>
  );
}
