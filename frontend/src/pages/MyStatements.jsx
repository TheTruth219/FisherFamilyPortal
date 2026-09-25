import React, { useEffect, useState } from "react";
import { Download, CheckCircle2, FileText, Clock, XCircle } from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const money = (c = 0) => `$${(c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const STATUS = {
  paid: { cls: "bg-green-100 text-green-800 border-green-300", Icon: CheckCircle2, label: "Paid" },
  recorded: { cls: "bg-amber-100 text-amber-800 border-amber-300", Icon: Clock, label: "Recorded" },
  failed: { cls: "bg-rose-100 text-rose-800 border-rose-300", Icon: XCircle, label: "Failed" },
};

async function openPdf(path) {
  const resp = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(resp.data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export default function MyStatements() {
  const { auth } = useAuth();
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);

  const load = async () => {
    const [d, s] = await Promise.all([api.get("/disbursements"), api.get("/disbursements/summary")]);
    setRows(d.data); setSummary(s.data);
  };
  useEffect(() => { load(); }, []);

  const acknowledge = async (d) => {
    try { await api.post(`/disbursements/${d.id}/acknowledge`); toast.success("Receipt acknowledged"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <Layout title="My Statements" subtitle="Your disbursements and downloadable receipts." testId="my-statements-page">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div data-testid="statement-total-received" className="bg-white border-2 border-slate-200 rounded-xl p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Total Received</div>
          <div className="mt-2 text-3xl font-bold text-slate-900">{money(summary?.total_cents || 0)}</div>
        </div>
        <div data-testid="statement-paid-total" className="bg-white border-2 border-slate-200 rounded-xl p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Paid</div>
          <div className="mt-2 text-3xl font-bold text-green-700">{money(summary?.by_status?.paid || 0)}</div>
        </div>
        <div data-testid="statement-transaction-count" className="bg-white border-2 border-slate-200 rounded-xl p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Transactions</div>
          <div className="mt-2 text-3xl font-bold text-slate-900">{summary?.count || 0}</div>
        </div>
      </div>

      <div className="mb-4">
        <button data-testid="download-statement-button" onClick={() => openPdf(`/disbursements/statement/${auth?.id}`)}
          className="inline-flex items-center gap-2 min-h-[48px] px-5 font-bold rounded-lg bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <FileText className="w-5 h-5" /> Download full statement (PDF)
        </button>
      </div>

      <SectionCard testId="my-statements-table-section">
        <div className="overflow-x-auto">
          <table className="w-full text-left" data-testid="my-statements-table">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Date</th><th className="px-4 py-3">Category</th><th className="px-4 py-3">Method</th>
                <th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Receipt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-400">No disbursements yet</td></tr>
              ) : rows.map((d) => {
                const s = STATUS[d.status] || STATUS.recorded;
                return (
                  <tr key={d.id} data-testid={`statement-row-${d.id}`} className="hover:bg-slate-50">
                    <td data-label="Date" className="px-4 py-3 text-slate-500">{(d.date || "").slice(0, 10)}</td>
                    <td data-label="Category" className="px-4 py-3 font-semibold text-slate-900">{d.category}</td>
                    <td data-label="Method" className="px-4 py-3 capitalize text-slate-500">{d.method}</td>
                    <td data-label="Amount" className="px-4 py-3 text-right font-bold">{money(d.amount_cents)}</td>
                    <td data-label="Status" className="px-4 py-3"><span data-testid={`disbursement-status-badge-${d.id}`} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-bold ${s.cls}`}><s.Icon className="w-3.5 h-3.5" /> {s.label}</span></td>
                    <td data-label="Receipt" className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <button data-testid={`download-receipt-${d.id}`} onClick={() => openPdf(`/disbursements/${d.id}/receipt`)} className="inline-flex items-center gap-1 px-3 py-2 rounded-lg text-blue-900 hover:bg-slate-100 font-semibold"><Download className="w-4 h-4" /> PDF</button>
                        {d.acknowledged ? (
                          <span className="inline-flex items-center gap-1 text-xs text-green-700 font-semibold"><CheckCircle2 className="w-4 h-4" /> Acknowledged</span>
                        ) : (
                          <button data-testid={`member-statement-acknowledge-button-${d.id}`} onClick={() => acknowledge(d)} className="min-h-[40px] px-4 rounded-lg bg-blue-900 text-white text-sm font-bold hover:bg-blue-800">Acknowledge</button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </Layout>
  );
}
