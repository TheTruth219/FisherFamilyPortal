import React, { useState } from "react";
import { Mail, Send, CheckCircle2 } from "lucide-react";
import Layout, { SectionCard } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useContent } from "@/context/ContentContext";
import { toast } from "sonner";

const TOPICS = [
  "Login or access problem",
  "Reunion question",
  "Payment question",
  "Family business question",
  "Meeting question",
  "Document request",
  "Incorrect information",
  "Other",
];

export default function Contact() {
  const { content } = useContent();
  const [form, setForm] = useState({ name: "", email: "", phone: "", topic: TOPICS[0], message: "" });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/contact", form);
      setDone(true);
      toast.success("Your message has been sent");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not send message");
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "min-h-[56px] text-lg p-4 border-2 border-slate-300 rounded-lg focus:border-blue-900 focus:ring-2 focus:ring-blue-900 focus:outline-none w-full bg-white text-slate-900";

  const contacts = content?.contacts || [];

  return (
    <Layout title="Contact or Get Help" subtitle="Send a question to the right family contact." testId="contact-page">
      <div className="grid lg:grid-cols-2 gap-6">
        <SectionCard title="Send a Message" testId="contact-form-section">
          {done ? (
            <div className="text-center py-8" data-testid="contact-success">
              <CheckCircle2 className="w-14 h-14 text-green-600 mx-auto mb-4" />
              <p className="text-xl font-semibold text-slate-900">Thank you — your message has been sent.</p>
              <button
                data-testid="contact-send-another"
                onClick={() => {
                  setDone(false);
                  setForm({ name: "", email: "", phone: "", topic: TOPICS[0], message: "" });
                }}
                className="mt-5 min-h-[52px] px-6 text-lg font-bold rounded-lg bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors"
              >
                Send another message
              </button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Topic</label>
                <select data-testid="contact-topic" className={inputClass} value={form.topic} onChange={(e) => set("topic", e.target.value)}>
                  {TOPICS.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Name</label>
                <input data-testid="contact-name" required className={inputClass} value={form.name} onChange={(e) => set("name", e.target.value)} />
              </div>
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Email</label>
                <input data-testid="contact-email" type="email" required className={inputClass} value={form.email} onChange={(e) => set("email", e.target.value)} />
              </div>
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Phone (optional)</label>
                <input data-testid="contact-phone" className={inputClass} value={form.phone} onChange={(e) => set("phone", e.target.value)} />
              </div>
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Message</label>
                <textarea data-testid="contact-message" required rows={4} className="text-lg p-4 border-2 border-slate-300 rounded-lg focus:border-blue-900 focus:ring-2 focus:ring-blue-900 focus:outline-none w-full bg-white text-slate-900" value={form.message} onChange={(e) => set("message", e.target.value)} />
              </div>
              <button
                type="submit"
                data-testid="contact-submit-btn"
                disabled={submitting}
                className="w-full min-h-[56px] text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 focus:outline-none transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60"
              >
                <Send className="w-5 h-5" />
                {submitting ? "Sending…" : "Send Message"}
              </button>
            </form>
          )}
        </SectionCard>

        <SectionCard title="Who to Contact" testId="contact-roles-section">
          <p className="text-base text-slate-600 mb-4">Reach the right role directly by email.</p>
          <div className="space-y-3">
            {contacts.map((c, i) => (
              <div key={c.id} className="border border-slate-200 rounded-xl p-4" data-testid={`contact-role-${i}`}>
                <div className="font-heading text-lg font-bold text-slate-900">{c.role}</div>
                <div className="text-base text-slate-600">{c.description}</div>
                <a href={`mailto:${c.email}`} className="mt-2 inline-flex items-center gap-2 text-blue-900 font-semibold hover:underline" data-testid={`contact-email-${i}`}>
                  <Mail className="w-4 h-4" /> {c.email}
                </a>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </Layout>
  );
}
