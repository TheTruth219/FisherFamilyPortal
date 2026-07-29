import React from "react";
import { Link } from "react-router-dom";
import { Ticket, CreditCard, BedDouble, CalendarDays, Mail } from "lucide-react";
import Layout, { SectionCard } from "@/components/Layout";
import { useContent, newId } from "@/context/ContentContext";
import { EText, EArea, Field, LinkButton, AddItemButton, DeleteItemButton } from "@/components/Editable";

export default function Reunion() {
  const { content, addItem, removeItem } = useContent();
  if (!content) return null;
  const r = content.reunion || {};

  return (
    <Layout title="Reunion" subtitle="Family reunion details, dates, registration, fees, and travel." testId="reunion-page">
      <SectionCard title="Reunion Overview" testId="reunion-overview">
        <div className="grid sm:grid-cols-2 gap-4 mb-4">
          <Field label="Reunion Year" path="reunion.year" />
          <Field label="Location" path="reunion.location" />
        </div>
        <EArea path="reunion.overview" rows={3} />
      </SectionCard>

      <SectionCard title="Important Dates" testId="reunion-dates">
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Dates" path="reunion.dates" />
          <Field label="Registration Deadline" path="reunion.registrationDeadline" />
          <Field label="Payment Deadline" path="reunion.paymentDeadline" />
        </div>
      </SectionCard>

      <SectionCard title="Registration" testId="reunion-registration">
        <p className="text-lg text-slate-800 mb-4">Register your household for the reunion.</p>
        <div className="flex flex-col sm:flex-row gap-3">
          <LinkButton label="Register" path="reunion.registrationLink" icon={Ticket} testId="reunion-register-btn" />
        </div>
      </SectionCard>

      <SectionCard title="Fees and Payments" testId="reunion-fees">
        <div className="grid sm:grid-cols-2 gap-4 mb-4">
          <Field label="Adult Fee" path="reunion.adultFee" />
          <Field label="Child Fee" path="reunion.childFee" />
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <LinkButton label="Make a Reunion Payment" path="reunion.paymentLink" icon={CreditCard} testId="reunion-payment-btn" />
        </div>
      </SectionCard>

      <SectionCard title="Hotel and Travel" testId="reunion-hotel">
        <div className="mb-4">
          <Field label="Hotel" path="reunion.hotel" />
        </div>
        <LinkButton label="Reserve Hotel" path="reunion.hotelLink" icon={BedDouble} variant="secondary" testId="reunion-hotel-btn" />
      </SectionCard>

      <SectionCard title="Weekend Schedule" testId="reunion-schedule">
        <div className="space-y-3">
          {(r.schedule || []).map((s, i) => (
            <div key={s.id} className="flex flex-col sm:flex-row sm:items-center gap-2 border-b border-slate-100 pb-3">
              <div className="sm:w-40 font-semibold text-slate-900">
                <EText path={`reunion.schedule.${i}.time`} />
              </div>
              <div className="flex-1">
                <EText path={`reunion.schedule.${i}.item`} />
              </div>
              <DeleteItemButton testId={`delete-schedule-${i}`} onClick={() => removeItem("reunion.schedule", i)} />
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-schedule-btn"
            label="Add Schedule Item"
            onClick={() => addItem("reunion.schedule", { id: newId(), time: "", item: "" })}
          />
        </div>
      </SectionCard>

      <SectionCard title="Reunion Documents" testId="reunion-documents">
        <div className="space-y-3">
          {(r.documents || []).map((d, i) => (
            <div key={d.id} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div className="flex-1">
                <EText path={`reunion.documents.${i}.title`} className="text-lg font-semibold text-slate-900" />
              </div>
              <LinkButton label="View" path={`reunion.documents.${i}.link`} variant="secondary" testId={`reunion-doc-${i}`} />
              <DeleteItemButton testId={`delete-reunion-doc-${i}`} onClick={() => removeItem("reunion.documents", i)} />
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-reunion-doc-btn"
            label="Add Document"
            onClick={() => addItem("reunion.documents", { id: newId(), title: "Document Link To Be Added", link: "#" })}
          />
        </div>
      </SectionCard>

      <SectionCard title="Frequently Asked Questions" testId="reunion-faqs">
        <div className="space-y-4">
          {(r.faqs || []).map((f, i) => (
            <div key={f.id} className="border-b border-slate-100 pb-4">
              <div className="font-semibold text-slate-900 mb-1">
                <EText path={`reunion.faqs.${i}.q`} className="text-lg font-semibold text-slate-900" />
              </div>
              <EArea path={`reunion.faqs.${i}.a`} rows={2} />
              <div className="mt-2">
                <DeleteItemButton testId={`delete-faq-${i}`} onClick={() => removeItem("reunion.faqs", i)} />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-faq-btn"
            label="Add FAQ"
            onClick={() => addItem("reunion.faqs", { id: newId(), q: "", a: "" })}
          />
        </div>
      </SectionCard>

      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        <Link
          to="/reunion"
          data-testid="reunion-view-schedule-btn"
          className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors"
        >
          <CalendarDays className="w-5 h-5" />
          View Reunion Schedule
        </Link>
        <Link
          to="/contact"
          data-testid="reunion-contact-btn"
          className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors"
        >
          <Mail className="w-5 h-5" />
          Contact the Reunion Committee
        </Link>
      </div>
    </Layout>
  );
}
