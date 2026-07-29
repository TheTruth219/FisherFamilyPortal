import React from "react";
import { Link } from "react-router-dom";
import { CreditCard, Receipt, AlertTriangle, HelpCircle, ShieldAlert } from "lucide-react";
import Layout, { SectionCard } from "@/components/Layout";
import { useContent, newId } from "@/context/ContentContext";
import { EText, EArea, LinkButton, AddItemButton, DeleteItemButton } from "@/components/Editable";

function PaymentItem({ base, index, onDelete }) {
  return (
    <div className="border-2 border-slate-200 rounded-xl p-5" data-testid={`payment-item-${base}-${index}`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <EText path={`payments.${base}.${index}.name`} className="text-xl font-bold text-slate-900" />
        <DeleteItemButton testId={`delete-payment-${base}-${index}`} onClick={onDelete} />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Purpose</div><EText path={`payments.${base}.${index}.purpose`} /></div>
        <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Amount</div><EText path={`payments.${base}.${index}.amount`} /></div>
        <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Who Should Pay</div><EText path={`payments.${base}.${index}.whoPays`} /></div>
        <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Due Date</div><EText path={`payments.${base}.${index}.dueDate`} /></div>
      </div>
      <div className="mt-3">
        <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Instructions</div>
        <EArea path={`payments.${base}.${index}.instructions`} rows={2} />
      </div>
      <div className="mt-3 grid sm:grid-cols-2 gap-4">
        <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Confirmation Process</div><EText path={`payments.${base}.${index}.confirmation`} /></div>
        <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Contact</div><EText path={`payments.${base}.${index}.contactRole`} /></div>
      </div>
      <div className="mt-4 flex flex-col sm:flex-row gap-3">
        <LinkButton label="Make Payment" path={`payments.${base}.${index}.link`} icon={CreditCard} testId={`make-payment-${base}-${index}`} />
        <Link to="/contact" data-testid={`payment-question-${base}-${index}`} className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <HelpCircle className="w-5 h-5" /> Ask a Payment Question
        </Link>
      </div>
    </div>
  );
}

export default function Payments() {
  const { content, addItem, removeItem } = useContent();
  if (!content) return null;
  const p = content.payments || { reunion: [], business: [] };

  const emptyItem = () => ({
    id: newId(), name: "New Payment", purpose: "", amount: "To be added", whoPays: "",
    dueDate: "To be added", link: "#", instructions: "", confirmation: "You will receive a confirmation.", contactRole: "Family Treasurer",
  });

  return (
    <Layout title="Payments" subtitle="Reunion and family business payments in one place." testId="payments-page">
      <div className="bg-amber-50 border-2 border-amber-300 rounded-xl p-5 mb-6 flex items-start gap-3" data-testid="payment-security-notice">
        <ShieldAlert className="w-6 h-6 text-amber-700 flex-shrink-0 mt-0.5" />
        <p className="text-base text-amber-900 leading-relaxed">
          Do not submit bank account numbers, Social Security numbers, passwords, or other sensitive financial
          information through an unsecured form.
        </p>
      </div>

      <SectionCard title="Reunion Payments" testId="reunion-payments-section">
        <div className="space-y-4">
          {(p.reunion || []).map((item, i) => (
            <PaymentItem key={item.id} base="reunion" index={i} onDelete={() => removeItem("payments.reunion", i)} />
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton testId="add-reunion-payment-btn" label="Add Reunion Payment" onClick={() => addItem("payments.reunion", emptyItem())} />
        </div>
      </SectionCard>

      <SectionCard title="Family Business Payments" testId="business-payments-section">
        <div className="space-y-4">
          {(p.business || []).map((item, i) => (
            <PaymentItem key={item.id} base="business" index={i} onDelete={() => removeItem("payments.business", i)} />
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton testId="add-business-payment-btn" label="Add Business Payment" onClick={() => addItem("payments.business", emptyItem())} />
        </div>
      </SectionCard>

      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        <Link to="/contact" data-testid="request-receipt-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <Receipt className="w-5 h-5" /> Request Receipt
        </Link>
        <Link to="/contact" data-testid="report-problem-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <AlertTriangle className="w-5 h-5" /> Report Payment Problem
        </Link>
      </div>
    </Layout>
  );
}
