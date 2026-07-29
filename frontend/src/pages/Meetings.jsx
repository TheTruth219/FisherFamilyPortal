import React from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Video, FileText, HelpCircle, ListChecks } from "lucide-react";
import Layout, { SectionCard } from "@/components/Layout";
import { useContent, newId } from "@/context/ContentContext";
import { EText, EArea, LinkButton, AddItemButton, DeleteItemButton } from "@/components/Editable";

export default function Meetings() {
  const { content, addItem, removeItem } = useContent();
  if (!content) return null;
  const m = content.meetings || { upcoming: [], past: [] };

  return (
    <Layout title="Meetings" subtitle="Upcoming and past family meetings, agendas, and minutes." testId="meetings-page">
      <SectionCard title="Upcoming Meetings" testId="upcoming-meetings-section">
        <div className="space-y-4">
          {(m.upcoming || []).map((u, i) => (
            <div key={u.id} className="border-2 border-slate-200 rounded-xl p-5" data-testid={`upcoming-meeting-${i}`}>
              <div className="flex items-start justify-between gap-3 mb-3">
                <EText path={`meetings.upcoming.${i}.name`} className="text-xl font-bold text-slate-900" />
                <DeleteItemButton testId={`delete-upcoming-${i}`} onClick={() => removeItem("meetings.upcoming", i)} />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Date</div><EText path={`meetings.upcoming.${i}.date`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Time &amp; Zone</div><EText path={`meetings.upcoming.${i}.time`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Who Should Attend</div><EText path={`meetings.upcoming.${i}.attendees`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">RSVP Deadline</div><EText path={`meetings.upcoming.${i}.rsvpDeadline`} /></div>
              </div>
              <div className="mt-3">
                <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Purpose</div>
                <EText path={`meetings.upcoming.${i}.purpose`} />
              </div>
              <div className="mt-3">
                <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Agenda</div>
                <EArea path={`meetings.upcoming.${i}.agenda`} rows={2} />
              </div>
              <div className="mt-4 flex flex-col sm:flex-row gap-3 flex-wrap">
                <LinkButton label="Join Meeting" path={`meetings.upcoming.${i}.location`} icon={Video} testId={`join-meeting-${i}`} />
                <LinkButton label="View Meeting Documents" path={`meetings.upcoming.${i}.documents`} icon={FileText} variant="secondary" testId={`upcoming-docs-${i}`} />
                <Link to="/contact" data-testid={`upcoming-question-${i}`} className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
                  <HelpCircle className="w-5 h-5" /> Submit a Question
                </Link>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-upcoming-btn"
            label="Add Upcoming Meeting"
            onClick={() => addItem("meetings.upcoming", { id: newId(), name: "New Meeting", date: "To be added", time: "To be added", location: "#", attendees: "", purpose: "", agenda: "", documents: "#", rsvpDeadline: "To be added" })}
          />
        </div>
      </SectionCard>

      <SectionCard title="Past Meetings" testId="past-meetings-section">
        <div className="space-y-4">
          {(m.past || []).map((pm, i) => (
            <div key={pm.id} className="border border-slate-200 rounded-xl p-5" data-testid={`past-meeting-${i}`}>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <EText path={`meetings.past.${i}.name`} className="text-xl font-bold text-slate-900" />
                  <div className="text-base text-slate-600"><EText path={`meetings.past.${i}.date`} className="text-base text-slate-600" /></div>
                </div>
                <DeleteItemButton testId={`delete-past-${i}`} onClick={() => removeItem("meetings.past", i)} />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Decisions Made</div><EArea path={`meetings.past.${i}.decisions`} rows={2} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Action Items</div><EArea path={`meetings.past.${i}.actionItems`} rows={2} /></div>
              </div>
              <div className="mt-4 flex flex-col sm:flex-row gap-3 flex-wrap">
                <LinkButton label="View Minutes" path={`meetings.past.${i}.minutes`} icon={ListChecks} variant="secondary" testId={`past-minutes-${i}`} />
                <LinkButton label="Supporting Documents" path={`meetings.past.${i}.documents`} icon={FileText} variant="secondary" testId={`past-docs-${i}`} />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-past-btn"
            label="Add Past Meeting"
            onClick={() => addItem("meetings.past", { id: newId(), date: "To be added", name: "Previous Meeting", minutes: "#", decisions: "", actionItems: "", documents: "#" })}
          />
        </div>
      </SectionCard>

      <div className="flex flex-col sm:flex-row gap-3">
        <Link to="/contact" data-testid="meetings-question-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <CalendarClock className="w-5 h-5" /> Submit a Question
        </Link>
      </div>
    </Layout>
  );
}
