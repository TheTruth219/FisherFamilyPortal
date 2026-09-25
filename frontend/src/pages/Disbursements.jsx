import React, { useEffect, useMemo, useState } from "react";
import {
  Wallet, TrendingUp, CheckCircle2, Clock, XCircle, Plus, Download, Mail,
  Pencil, History, Banknote, Loader2, Filter,
} from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DatePicker } from "@/components/DatePicker";

const money = (c = 0) => `$${(c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const METHODS = ["check", "zelle", "wire", "ach", "cash", "stripe"];
const STATUS_BADGE = {
  paid: { cls: "bg-green-100 text-green-800 border-green-300", Icon: CheckCircle2, label: "Paid" },
  recorded: { cls: "bg-amber-100 text-amber-800 border-amber-300", Icon: Clock, label: "Recorded" },
  failed: { cls: "bg-rose-100 text-rose-800 border-rose-300", Icon: XCircle, label: "Failed" },
};

function Badge({ status, id }) {
  const s = STATUS_BADGE[status] || STATUS_BADGE.recorded;
  return (
    <span data-testid={`disbursement-status-badge-${id}`} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-bold ${s.cls}`}>
      <s.Icon className="w-3.5 h-3.5" /> {s.label}
    </span>
  );
}

async function openPdf(path) {
  const resp = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(resp.data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

const EMPTY = { member_id: "", amount: "", date: new Date().toISOString().slice(0, 10), category: "", customCategory: "", reason: "", method: "check", notes: "", send_email: true };
const inputCls = "min-h-[48px] text-base p-3 border-2 border-slate-300 rounded-lg focus:border-blue-900 focus:outline-none w-full bg-white text-slate-900";

export default function Disbursements() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState([]);
  const [members, setMembers] = useState([]);
  const [categories, setCategories] = useState([]);
  const [fund, setFund] = useState(null);
  const [filters, setFilters] = useState({ member_id: "", status: "", date_from: "", date_to: "" });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [audit, setAudit] = useState(null);

  const load = async () => {
    setLoading(true);
    const params = {};
    Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
    try {
      const [d, f] = await Promise.all([api.get("/disbursements", { params }), api.get("/fund").catch(() => ({ data: null }))]);
      setRows(d.data); setFund(f.data);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    api.get("/members").then((r) => setMembers(r.data)).catch(() => {});
    api.get("/categories").then((r) => setCategories(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [filters]); // eslint-disable-line

  const total = useMemo(() => rows.reduce((a, r) => a + r.amount_cents, 0), [rows]);

  const openCreate = () => { setEditing(null); setForm(EMPTY); setShowForm(true); };
  const openEdit = (d) => {
    setEditing(d);
    setForm({ member_id: d.member_id, amount: (d.amount_cents / 100).toString(), date: (d.date || "").slice(0, 10), category: d.category, customCategory: "", reason: d.reason || "", method: d.method, notes: d.notes || "", status: d.status, send_email: false });
    setShowForm(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const category = form.category === "__custom__" ? form.customCategory.trim() : form.category;
      if (!editing) {
        if (!form.member_id) throw { response: { data: { detail: "Select a member" } } };
        if (!category) throw { response: { data: { detail: "Category is required" } } };
        await api.post("/disbursements", { member_id: form.member_id, amount: parseFloat(form.amount), date: form.date, category, reason: form.reason, method: form.method, notes: form.notes, send_email: form.send_email });
        toast.success("Disbursement recorded" + (form.send_email ? " and emailed" : ""));
      } else {
        await api.patch(`/disbursements/${editing.id}`, { amount: parseFloat(form.amount), date: form.date, category, reason: form.reason, method: form.method, status: form.status, notes: form.notes });
        toast.success("Disbursement updated");
      }
      setShowForm(false);
      api.get("/categories").then((r) => setCategories(r.data));
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Failed to save");
    } finally { setSaving(false); }
  };

  const act = async (fn, ok) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };

  const stat = (label, value, Icon) => (
    <div className="bg-white border-2 border-slate-200 rounded-xl p-5" data-testid={`disb-stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
        <Icon className="w-5 h-5 text-blue-900" />
      </div>
      <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
    </div>
  );

  return (
    <Layout title="Disbursements" subtitle="Ledger of all disbursements from the family business account." testId="disbursements-page">
      {fund && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {stat("Account Balance", money(fund.remaining_cents), Wallet)}
          {stat("Total Dispersed", money(fund.total_dispersed_cents), TrendingUp)}
          {stat("Paid Out", money(fund.total_paid_cents), CheckCircle2)}
          {stat("Records", fund.disbursement_count, History)}
        </div>
      )}

      {isAdmin && (
        <div className="mb-4">
          <button data-testid="disbursement-create-button" onClick={openCreate}
            className="inline-flex items-center gap-2 min-h-[48px] px-5 font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors">
            <Plus className="w-5 h-5" /> New Disbursement
          </button>
        </div>
      )}

      <SectionCard testId="disbursement-filters">
        <div className="flex items-center gap-2 mb-3 text-slate-700"><Filter className="w-4 h-4" /><span className="font-semibold">Filters</span></div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <select data-testid="disbursement-filter-member-select" className={inputCls} value={filters.member_id} onChange={(e) => setFilters({ ...filters, member_id: e.target.value })}>
            <option value="">All members</option>
            {members.map((m) => <option key={m.id} value={m.id}>{`${m.first_name} ${m.last_name}`}</option>)}
          </select>
          <select data-testid="disbursement-filter-status-select" className={inputCls} value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
            <option value="">All statuses</option>
            <option value="recorded">Recorded</option>
            <option value="paid">Paid</option>
            <option value="failed">Failed</option>
          </select>
          <input data-testid="disbursement-filter-from" type="date" className={inputCls} value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
          <input data-testid="disbursement-filter-to" type="date" className={inputCls} value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
        </div>
      </SectionCard>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
          <span className="text-sm text-slate-500">{rows.length} record{rows.length !== 1 ? "s" : ""}</span>
          <span className="text-sm font-bold text-slate-900">Total {money(total)}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left" data-testid="disbursement-ledger-table">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Member</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Method</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin mx-auto" /></td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-400">No disbursements found</td></tr>
              ) : rows.map((d) => (
                <tr key={d.id} data-testid={`disbursement-row-${d.id}`} className="hover:bg-slate-50">
                  <td data-label="Member" className="px-4 py-3 font-semibold text-slate-900">{d.member_name}</td>
                  <td data-label="Date" className="px-4 py-3 text-slate-500">{(d.date || "").slice(0, 10)}</td>
                  <td data-label="Category" className="px-4 py-3">{d.category}</td>
                  <td data-label="Method" className="px-4 py-3 capitalize text-slate-500">{d.method}</td>
                  <td data-label="Amount" className="px-4 py-3 text-right font-bold">{money(d.amount_cents)}</td>
                  <td data-label="Status" className="px-4 py-3"><Badge status={d.status} id={d.id} /></td>
                  <td data-label="Actions" className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button title="Download receipt" data-testid={`download-receipt-${d.id}`} onClick={() => openPdf(`/disbursements/${d.id}/receipt`)} className="p-2 rounded-lg hover:bg-slate-100 text-slate-600"><Download className="w-4 h-4" /></button>
                      {isAdmin && <>
                        <button title="Resend email" data-testid={`resend-email-${d.id}`} onClick={() => act(() => api.post(`/disbursements/${d.id}/send-email`), "Receipt emailed")} className="p-2 rounded-lg hover:bg-slate-100 text-slate-600"><Mail className="w-4 h-4" /></button>
                        <button title="Edit" data-testid={`edit-disbursement-${d.id}`} onClick={() => openEdit(d)} className="p-2 rounded-lg hover:bg-slate-100 text-slate-600"><Pencil className="w-4 h-4" /></button>
                        <button title="Audit log" data-testid={`audit-disbursement-${d.id}`} onClick={async () => setAudit((await api.get(`/audit/${d.id}`)).data)} className="p-2 rounded-lg hover:bg-slate-100 text-slate-600"><History className="w-4 h-4" /></button>
                        {d.status !== "paid" && <button title="Trigger Stripe payout" data-testid={`payout-disbursement-${d.id}`} onClick={() => act(() => api.post(`/stripe/payouts/${d.id}`), "Payout triggered")} className="p-2 rounded-lg hover:bg-slate-100 text-blue-900"><Banknote className="w-4 h-4" /></button>}
                      </>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showForm && (
        <Dialog open={showForm} onOpenChange={setShowForm}>
          <DialogContent className="portal-modal page-content" data-testid="disbursement-dialog" closeTestId="disbursement-dialog-close">
          <form onSubmit={submit}>
            <DialogTitle className="font-heading text-2xl font-bold text-slate-900 mb-2">{editing ? "Edit disbursement" : "New disbursement"}</DialogTitle>
            <DialogDescription className="mb-5">Keep a clear record of your family’s funds.</DialogDescription>
            {!editing && (
              <label className="block mb-3"><span className="text-sm font-semibold text-slate-700">Member</span>
                <select data-testid="disbursement-member-select" className={inputCls} value={form.member_id} onChange={(e) => setForm({ ...form, member_id: e.target.value })}>
                  <option value="">Select member</option>
                  {members.map((m) => <option key={m.id} value={m.id}>{`${m.first_name} ${m.last_name} — ${m.role.replaceAll("_", " ")}`}</option>)}
                </select>
              </label>
            )}
            <div className="grid grid-cols-2 gap-3">
              <label><span className="text-sm font-semibold text-slate-700">Amount (USD)</span>
                <input data-testid="disbursement-amount-input" type="number" step="0.01" min="0" className={inputCls} value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></label>
              <label><span className="text-sm font-semibold text-slate-700">Date</span>
                <DatePicker value={form.date} onChange={(v) => setForm({ ...form, date: v })} testId="disbursement-date-input" className="w-full mt-1" /></label>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <label><span className="text-sm font-semibold text-slate-700">Category</span>
                <select data-testid="disbursement-category-select" className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                  <option value="">Select</option>
                  {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                  <option value="__custom__">+ Custom…</option>
                </select></label>
              <label><span className="text-sm font-semibold text-slate-700">Method</span>
                <select data-testid="disbursement-method-select" className={inputCls} value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>
                  {METHODS.map((m) => <option key={m} value={m} className="capitalize">{m}</option>)}
                </select></label>
            </div>
            {form.category === "__custom__" && (
              <input data-testid="disbursement-custom-category-input" className={`${inputCls} mt-3`} placeholder="Custom category" value={form.customCategory} onChange={(e) => setForm({ ...form, customCategory: e.target.value })} />
            )}
            {editing && (
              <label className="block mt-3"><span className="text-sm font-semibold text-slate-700">Status</span>
                <select data-testid="disbursement-status-select" className={inputCls} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  <option value="recorded">Recorded</option><option value="paid">Paid</option><option value="failed">Failed</option>
                </select></label>
            )}
            <label className="block mt-3"><span className="text-sm font-semibold text-slate-700">Reason</span>
              <input data-testid="disbursement-reason-input" className={inputCls} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></label>
            <label className="block mt-3"><span className="text-sm font-semibold text-slate-700">Notes</span>
              <textarea data-testid="disbursement-notes-input" className={inputCls} rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
            {!editing && (
              <label className="flex items-center gap-3 mt-4 bg-slate-50 border border-slate-200 rounded-lg p-3">
                <input data-testid="disbursement-send-email-switch" type="checkbox" checked={form.send_email} onChange={(e) => setForm({ ...form, send_email: e.target.checked })} className="w-5 h-5" />
                <span className="text-sm text-slate-700">Email the receipt to the member</span>
              </label>
            )}
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" data-testid="disbursement-cancel-button" onClick={() => setShowForm(false)} className="min-h-[48px] px-5 font-bold rounded-lg border-2 border-slate-300 text-slate-700">Cancel</button>
              <button type="submit" data-testid="disbursement-save-button" disabled={saving} className="min-h-[48px] px-5 font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 disabled:opacity-60 inline-flex items-center gap-2">
                {saving && <Loader2 className="w-4 h-4 animate-spin" />}{editing ? "Save changes" : "Record"}
              </button>
            </div>
          </form>
          </DialogContent>
        </Dialog>
      )}

      {audit && (
        <Dialog open={!!audit} onOpenChange={(open) => { if (!open) setAudit(null); }}>
          <DialogContent className="portal-modal page-content" data-testid="audit-dialog" closeTestId="audit-dialog-close">
            <DialogTitle className="font-heading text-2xl font-bold text-slate-900 mb-2">Audit trail</DialogTitle>
            <DialogDescription className="mb-5">A transparent history of this disbursement.</DialogDescription>
            {audit.length === 0 ? <p className="text-slate-500">No history.</p> : audit.map((l) => (
              <div key={l.id} className="border border-slate-200 rounded-lg p-3 mb-2 text-sm">
                <div className="flex justify-between"><span className="font-bold capitalize">{l.action}</span><span className="text-slate-400 text-xs">{new Date(l.at).toLocaleString()}</span></div>
                <div className="text-slate-500 text-xs">by {l.actor_name}</div>
                <pre className="mt-1 whitespace-pre-wrap text-xs text-slate-600">{JSON.stringify(l.changes, null, 1)}</pre>
              </div>
            ))}
            <div className="flex justify-end mt-3"><button data-testid="audit-close-button" onClick={() => setAudit(null)} className="min-h-[44px] px-5 font-bold rounded-lg border-2 border-slate-300">Close</button></div>
          </DialogContent>
        </Dialog>
      )}
    </Layout>
  );
}
